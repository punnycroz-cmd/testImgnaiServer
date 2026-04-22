import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from config.models import ASPECT_TO_RESOLUTION, MODEL_CONFIGS, MODEL_ORDER
from core.vault import R2Vault

URL_LOGIN = "https://app.imgnai.com/login"
URL_GENERATE = "https://app.imgnai.com/generate"
URL_GENERATE_SESSION = "https://app.imgnai.com/services/webappms/api/generate-session"
URL_GENERATE_BATCH = "https://app.imgnai.com/services/webappms/api/generate-image-batch"
URL_GENERATE_TASK = "https://app.imgnai.com/services/webappms/api/generate-image/uuid/{task_uuid}"
URL_WASMALL = "https://wasmall.imgnai.com/"


class DayManager:
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault, db=None):
        self.browser_context = None
        self.page = None
        self._lock = asyncio.Lock()
        self.user_data_dir = os.path.join(cookie_dir, "day_profile")
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.vault = vault
        self.db = db
        self.logger = logging.getLogger("aether.day")
        self.username = os.environ.get("IMGNAI_USERNAME")
        self.password = os.environ.get("IMGNAI_PASSWORD")

    async def _browser_fetch(self, method, url, body=None, token=None):
        script = """
        async ([m, u, b, t]) => {
            const h = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
            if (t) h['Authorization'] = 'Bearer ' + t;
            const r = await fetch(u, { method: m, headers: h, body: b ? JSON.stringify(b) : null });
            const text = await r.text();
            return { ok: r.ok, status: r.status, text };
        }
        """
        return await self.page.evaluate(script, [method, url, body, token])

    async def start(self):
        if self.page: return
        self.logger.info("Starting Persistent Day Profile")
        pw = await async_playwright().start()
        
        # Using launch_persistent_context for higher Cloudflare trust
        self.browser_context = await pw.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 1000},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        self.page = self.browser_context.pages[0] if self.browser_context.pages else await self.browser_context.new_page()
        await Stealth().apply_stealth_async(self.page)
        await self.ensure_logged_in()

    async def _wait_for_cloudflare(self):
        self.logger.info("Page State: [%s] %s", await self.page.title(), self.page.url)
        for _ in range(20):
            content = await self.page.content()
            if "Just a moment" not in content and "challenges.cloudflare.com" not in content:
                break
            self.logger.info("Cloudflare Active... Waiting 2s")
            await asyncio.sleep(2)

    async def ensure_logged_in(self, force_login=False):
        if not force_login:
            await self.page.goto(URL_GENERATE, wait_until="domcontentloaded")
            await self._wait_for_cloudflare()
            if "login" not in self.page.url.lower(): return

        self.logger.info("Performing Day login")
        await self.page.goto(URL_LOGIN, wait_until="domcontentloaded")
        await self._wait_for_cloudflare()
        
        try:
            await self.page.wait_for_selector('input[name="username"]', timeout=15000)
            await self.page.locator('input[name="username"]').type(self.username, delay=100)
            await self.page.locator('input[type="password"]').type(self.password, delay=100)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_url("**/generate", timeout=60000)
        except Exception:
            self.logger.warning("Direct login fields not found. Checking if already on dashboard.")
            if "generate" not in self.page.url.lower():
                self.logger.error("Login failed. Current URL: %s", self.page.url)

    async def _vault_image(self, url, batch_prefix, task_uuid, idx, request_id):
        key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
        cloud_url = await asyncio.to_thread(self.vault.upload_image, url, key)
        if self.db and request_id:
            await self.db.add_image(generation_id=request_id, task_uuid=task_uuid, r2_url=cloud_url, r2_key=key, image_index=idx)
        return cloud_url

    async def generate(self, req, request_id=None):
        async with self._lock:
            await self.start()
            self.logger.info("day generate start prompt=%s", req.prompt[:60])
            
            # Fetch token from LocalStorage
            token_json = await self.page.evaluate("window.localStorage.getItem('authentication')")
            token = json.loads(token_json).get("state", {}).get("token") if token_json else None
            
            if not token:
                await self.ensure_logged_in(force_login=True)
                token_json = await self.page.evaluate("window.localStorage.getItem('authentication')")
                token = json.loads(token_json).get("state", {}).get("token") if token_json else None
            
            if not token: raise RuntimeError("Day Auth Missing")

            s_res = await self._browser_fetch("POST", URL_GENERATE_SESSION, token=token)
            session_uuid = s_res["text"].strip().strip('"')
            if self.db and request_id: await self.db.update_generation(request_id, session_uuid=session_uuid)

            config = MODEL_CONFIGS[req.model or MODEL_ORDER[0]]
            img_list = [{
                "nsfw": False, "profile": config["profile"], "n_steps": config["n_steps"], "strength": config["strength"],
                "seed": int(time.time()) + (i*100), "prompt": req.prompt, "negative_prompt": req.negative_prompt or config["negative_prompt"],
                "guidance_scale": config["guidance_scale"], "image_resolution": ASPECT_TO_RESOLUTION[req.aspect or "1:1"],
                "is_uhd": req.quality == "4k+", "is_fast": req.quality == "Fast",
            } for i in range(req.count)]
            
            b_res = await self._browser_fetch("POST", URL_GENERATE_BATCH, body={"session_uuid": session_uuid, "use_credits": False, "generate_image_list": img_list}, token=token)
            task_uuids = json.loads(b_res["text"])
            if self.db and request_id: await self.db.update_generation(request_id, task_uuids=task_uuids)

            final_image_urls = []
            for task_uuid in task_uuids:
                for _ in range(60):
                    p_res = await self._browser_fetch("GET", URL_GENERATE_TASK.format(task_uuid=task_uuid), token=token)
                    if p_res["ok"]:
                        data = json.loads(p_res["text"]).get("response", {})
                        path = data.get("no_watermark_image_url") or data.get("image_url")
                        if path:
                            final_image_urls.append(f"{URL_WASMALL}{path}")
                            break
                    await asyncio.sleep(2)

            # Parallel Vaulting
            batch_prefix = self.vault.build_batch_prefix_with_name("day", session_uuid, ts=datetime.now())
            results = await asyncio.gather(*[
                self._vault_image(url, batch_prefix, task_uuids[i] if i < len(task_uuids) else f"{i:03d}", i, request_id)
                for i, url in enumerate(final_image_urls)
            ])
            return {"image_urls": [r for r in results if r], "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
