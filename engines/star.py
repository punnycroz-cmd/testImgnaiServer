import asyncio
import json
import os
import httpx
from typing import Optional

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
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault):
        self.browser = None
        self.context = None
        self.page = None
        self._lock = asyncio.Lock()
        self.cookie_dir = cookie_dir
        self.output_dir = output_dir
        self.vault = vault
        self.cookies_file = os.path.join(cookie_dir, "imgnai_star_cookies.json")

    def get_user_agent(self):
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    async def start(self):
        if self.page:
            return
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=False,
            args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=self.get_user_agent(),
        )
        self.page = await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)
        if os.path.exists(self.cookies_file):
            with open(self.cookies_file, "r") as f:
                await self.context.add_cookies(json.load(f))
        await star_api.ensure_logged_in_async(self.page, self.context)

    async def generate(self, req: GenerateRequest):
        async with self._lock:
            await self.start()
            token = await star_api.acquire_auth_token_async(self.page, self.context)
            if not token:
                await star_api.ensure_logged_in_async(self.page, self.context, force_login=True)
                token = await star_api.acquire_auth_token_async(self.page, self.context)

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Origin": "https://imagine.red"}
            payload = star_api.build_payload(req.model, req.quality, req.aspect, req.prompt, req.count, req.seed, True, negative_prompt=req.negative_prompt)

            async with httpx.AsyncClient(timeout=60) as client:
                session_resp = await client.post(star_api.URL_GENERATE_SESSION, headers=headers)
                session_uuid = star_api.parse_session_uuid(session_resp.text)
                payload["session_uuid"] = session_uuid

                batch_resp = await client.post(star_api.URL_GENERATE_BATCH, headers=headers, json=payload)
                batch_data = batch_resp.json()

                task_uuids = batch_data if isinstance(batch_data, list) else batch_data.get("response", [])
                if not task_uuids and isinstance(batch_data, dict):
                    task_uuids = batch_data.get("task_uuids", [])
                vaulted_urls = []

                for idx, tuid in enumerate(task_uuids):
                    for _ in range(60):
                        poll = await client.get(star_api.URL_GENERATE_TASK.format(task_uuid=tuid), headers=headers)
                        try:
                            poll_data = poll.json()
                        except Exception:
                            poll_data = {}
                        resp_obj = poll_data.get("response") or poll_data
                        img_path = resp_obj.get("no_watermark_image_url") or resp_obj.get("image_url")
                        if img_path:
                            source_url = f"https://r.imagine.red/{img_path.lstrip('/')}"
                            cloud_url = self.vault.upload_image(source_url, f"vault/star_{req.client_id or tuid}_{idx}.jpg")
                            vaulted_urls.append(cloud_url)
                            break
                        await asyncio.sleep(2)

            result = {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
            with open(os.path.join(self.output_dir, f"star_{req.client_id}.json"), "w") as f:
                json.dump(result, f)
            return result
