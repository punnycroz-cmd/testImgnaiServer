import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, List

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

import star_api
from core.vault import R2Vault


class GenerateRequest:
    def __init__(
        self,
        prompt: str,
        model: str = "Gen",
        count: int = 4,
        aspect: str = "1:1",
        quality: str = "Fast",
        seed: Optional[int] = None,
        nsfw: bool = False,
        negative_prompt: str = "",
        client_id: Optional[str] = None,
        realm: str = "day",
    ):
        self.prompt = prompt
        self.model = model
        self.count = count
        self.aspect = aspect
        self.quality = quality
        self.seed = seed
        self.nsfw = nsfw
        self.negative_prompt = negative_prompt
        self.client_id = client_id
        self.realm = realm


class StarManager:
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault, db=None, cancelled_jobs=None):
        self.browser = None
        self.context = None
        self.page = None
        self._lock = asyncio.Lock()
        self.cookie_dir = cookie_dir
        self.vault = vault
        self.db = db
        self.cancelled_jobs = cancelled_jobs or set()
        self.cookies_file = os.path.join(cookie_dir, "imaginered_cookie.json")
        self.logger = logging.getLogger("aether.star")

    def get_user_agent(self):
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    async def _get_json(self, client: httpx.AsyncClient, url: str, headers: dict):
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except:
            return None

    async def _sleep_backoff(self, attempt: int, base: float = 40.0, cap: float = 40.0):
        await asyncio.sleep(min(cap, base * (1.0 ** attempt)))

    async def start(self):
        if self.page: return
        # self.logger.info("[S] Star Portal Opening...")
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=False,
            args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        self.context = await self.browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=self.get_user_agent())
        self.page = await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)
        if os.path.exists(self.cookies_file):
            with open(self.cookies_file, "r") as f:
                await self.context.add_cookies(json.load(f))
        await star_api.ensure_logged_in_async(self.page, self.context, logger=self.logger)

    async def _poll_task(self, client, tuid, headers, batch_prefix, idx, request_id):
        # Silenced polling logs
        for attempt in range(90):
            if request_id and request_id in self.cancelled_jobs:
                self.logger.warning("star task poll cancelled: %s", request_id)
                return None
            poll_data = await self._get_json(client, star_api.URL_GENERATE_TASK.format(task_uuid=tuid), headers)
            if not poll_data:
                await self._sleep_backoff(attempt)
                continue
            resp_obj = poll_data.get("response") or poll_data
            img_path = resp_obj.get("no_watermark_image_url") or resp_obj.get("image_url")
            if img_path:
                return f"https://r.imagine.red/{img_path.lstrip('/')}"
            await self._sleep_backoff(attempt)
        return None

    async def generate(self, req: GenerateRequest, request_id=None):
        async with self._lock:
            if request_id and request_id in self.cancelled_jobs:
                self.logger.info("star generate cancelled before start: %s", request_id)
                return None
            await self.start()
            # self.logger.info("[>] Star Pulse: %s", req.prompt[:30] + "...")
            token = await star_api.acquire_auth_token_async(self.page, self.context, logger=self.logger)
            if not token:
                await star_api.ensure_logged_in_async(self.page, self.context, force_login=True, logger=self.logger)
                token = await star_api.acquire_auth_token_async(self.page, self.context, logger=self.logger)
            if not token: raise RuntimeError("Auth failed")

            payload = star_api.build_payload(req.model, req.quality, req.aspect, req.prompt, req.count, req.seed, True, negative_prompt=req.negative_prompt)
            async with httpx.AsyncClient(timeout=90.0) as client:
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Origin": "https://imagine.red"}
                session_resp = await client.post(star_api.URL_GENERATE_SESSION, headers=headers)
                session_resp.raise_for_status()
                session_uuid = star_api.parse_session_uuid(session_resp.text)
                if self.db and request_id: await self.db.update_generation(request_id, session_uuid=session_uuid)

                payload["session_uuid"] = session_uuid
                batch_resp = await client.post(star_api.URL_GENERATE_BATCH, headers=headers, json=payload)
                batch_resp.raise_for_status()
                batch_data = batch_resp.json()
                task_uuids = batch_data if isinstance(batch_data, list) else batch_data.get("response", [])
                if not task_uuids and isinstance(batch_data, dict): task_uuids = batch_data.get("task_uuids", [])
                


                # Released Engine Lock: Next job can now start its "nap" or generate phase
                batch_prefix = self.vault.build_batch_prefix_with_name("star", session_uuid or "session", ts=datetime.now())
                poll_results = await asyncio.gather(*[
                    self._poll_task(client, tuid, headers, batch_prefix, i, request_id)
                    for i, tuid in enumerate(task_uuids)
                ])

                async def safe_upload(url, idx):
                    if not url: return None
                    try:
                        task_uuid = task_uuids[idx] if idx < len(task_uuids) else f"{idx + 1:03d}"
                        key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
                        return await asyncio.to_thread(self.vault.upload_image, url, key)
                    except Exception as e:
                        self.logger.error("Failed to vault star image %d for job %s: %s", idx, request_id, e)
                        return None

                vault_tasks = [safe_upload(url, i) for i, url in enumerate(poll_results)]
                final_results = await asyncio.gather(*vault_tasks)
                vaulted_urls = [u for u in final_results if u]

                return {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
