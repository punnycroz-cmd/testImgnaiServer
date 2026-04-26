import argparse
import asyncio
import json
import logging
import os
import sys
import time

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from config.models import MODEL_CONFIGS, STAR_MODEL_CONFIGS, MODEL_ORDER
from engines.star_client import (
    URL_GENERATE_BATCH,
    URL_GENERATE_SESSION,
    URL_GENERATE_TASK,
    URL_WASMALL,
    acquire_auth_token_async,
    build_payload,
    ensure_logged_in_async,
    parse_session_uuid,
)

LOGGER = logging.getLogger("aether.star_test.cli")


def fatal(code: str, message: str, extra: dict = None, exit_code: int = 1):
    payload = {"event": "error", "code": code, "message": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload))
    print(message, file=sys.stderr)
    sys.exit(exit_code)


async def _poll_task(client, tuid, headers):
    for attempt in range(90):
        try:
            resp = await client.get(URL_GENERATE_TASK.format(task_uuid=tuid), headers=headers)
            if resp.status_code == 200:
                poll_data = resp.json()
                resp_obj = poll_data.get("response") or poll_data
                img_path = resp_obj.get("no_watermark_image_url") or resp_obj.get("image_url")
                if img_path:
                    return f"https://r.imagine.red/{img_path.lstrip('/')}"
        except Exception:
            pass
        await asyncio.sleep(min(10.0, 1.5 * (1.4 ** attempt)))
    return None


async def main_async(args):
    model_name = args.model
    if not model_name:
        fatal("missing_arg", "Missing --model argument")
    quality = args.quality or "Fast"
    aspect = args.aspect or "1:1"
    prompt = args.prompt
    if not prompt:
        fatal("missing_arg", "Missing --prompt argument")
    count = args.count or 4
    base_seed = args.seed if args.seed is not None else int(time.time())

    cookie_dir = "cookie"
    cookies_file = os.path.join(cookie_dir, "imaginered_cookie.json")
    os.makedirs(cookie_dir, exist_ok=True)

    async with async_playwright() as p:
        LOGGER.info("Starting star test browser session")
        browser = await p.chromium.launch(
            headless=False,
            args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, "r") as f:
                    await context.add_cookies(json.load(f))
            except: pass

        LOGGER.info("Authenticating star test...")
        token = await acquire_auth_token_async(page, context, logger=LOGGER)
        if not token:
            await ensure_logged_in_async(page, context, force_login=True, logger=LOGGER)
            token = await acquire_auth_token_async(page, context, logger=LOGGER)
            
        if not token:
            fatal("token_missing", "Could not locate an authorization token after forcing login.")

        payload = build_payload(
            model_name=model_name,
            quality=quality,
            aspect=aspect,
            prompt=prompt,
            count=count,
            base_seed=base_seed,
            nsfw=True,
            negative_prompt=args.negative_prompt
        )

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Origin": "https://imagine.red"}
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            session_resp = await client.post(URL_GENERATE_SESSION, headers=headers)
            if session_resp.status_code != 200:
                fatal("session_failed", f"Failed to create session: {session_resp.status_code}")
            
            session_uuid = parse_session_uuid(session_resp.text)
            print(json.dumps({"event": "session", "session_uuid": session_uuid}))
            
            payload["session_uuid"] = session_uuid
            batch_resp = await client.post(URL_GENERATE_BATCH, headers=headers, json=payload)
            if batch_resp.status_code != 200:
                fatal("batch_failed", f"Failed to submit batch: {batch_resp.status_code}")
                
            batch_data = batch_resp.json()
            task_uuids = batch_data if isinstance(batch_data, list) else batch_data.get("response", [])
            if not task_uuids and isinstance(batch_data, dict):
                task_uuids = batch_data.get("task_uuids", [])
                
            print(json.dumps({"event": "tasks", "task_uuids": task_uuids}))
            
            poll_results = await asyncio.gather(*[
                _poll_task(client, tuid, headers)
                for tuid in task_uuids
            ])
            
            final_image_urls = [u for u in poll_results if u]
            
            print(json.dumps({
                "session_uuid": session_uuid,
                "task_uuids": task_uuids,
                "image_urls": final_image_urls,
            }))
            
        await browser.close()


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--quality")
    parser.add_argument("--aspect")
    parser.add_argument("--prompt")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--negative-prompt")
    parser.add_argument("--skip-login-prompt", action="store_true")
    parser.add_argument("--confirm-payload", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    run()
