import argparse
import json
import logging
import os
import re
import sys
import asyncio
import urllib.parse
import time

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

from config.models import ASPECT_CHOICES, ASPECT_TO_RESOLUTION, MODEL_CONFIGS, MODEL_ORDER, QUALITY_CHOICES
from core.vault import R2Vault

load_dotenv()

URL_LOGIN = "https://app.imgnai.com/login"
URL_GENERATE = "https://app.imgnai.com/generate"
URL_GENERATE_SESSION = "https://app.imgnai.com/services/webappms/api/generate-session"
URL_GENERATE_BATCH = "https://app.imgnai.com/services/webappms/api/generate-image-batch"
URL_GENERATE_TASK = "https://app.imgnai.com/services/webappms/api/generate-image/uuid/{task_uuid}"
URL_WASMALL = "https://wasmall.imgnai.com/"

USERNAME = os.environ.get("IMGNAI_USERNAME")
PASSWORD = os.environ.get("IMGNAI_PASSWORD")

COOKIE_DIR = "cookie"
COOKIES_FILE = os.path.join(COOKIE_DIR, "imgnai_cookie.json")
os.makedirs(COOKIE_DIR, exist_ok=True)

LOGGER = logging.getLogger("aether.day.cli")


def sleep_seconds_for_quality(quality: str, attempt: int) -> float:
    base, cap = (2.75, 18.0) if quality == "4k+" else (2.25, 14.0) if quality == "High Quality" else (1.5, 10.0)
    return min(cap, base * (1.25 ** attempt))


async def save_cookies(context):
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(await context.cookies(), f, indent=2)
    except Exception as e:
        LOGGER.exception("Failed to save cookies: %s", e)


async def load_cookies(context):
    if not os.path.exists(COOKIES_FILE): return False
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            await context.add_cookies(json.load(f))
        return True
    except: return False


def build_payload(model_name, quality, aspect, prompt, count, base_seed=None, nsfw=False, use_assistant=False, prompt_assist=False, use_credits=False, strength=None, n_steps=None, guidance_scale=None, negative_prompt=None, image_resolution=None, auto_resolution=False):
    config = MODEL_CONFIGS[model_name]
    profile = config["profile"]
    image_resolution = image_resolution or ASPECT_TO_RESOLUTION[aspect]
    is_fast, is_uhd = (quality == "Fast"), (quality == "4k+")
    strength = config["strength"] if strength is None else strength
    n_steps = config["n_steps"] if n_steps is None else n_steps
    guidance_scale = config["guidance_scale"] if guidance_scale is None else guidance_scale
    negative_prompt = config["negative_prompt"] if negative_prompt is None else negative_prompt
    if base_seed is None: base_seed = int(time.time())

    generate_image_list = [{
        "nsfw": nsfw, "profile": profile, "n_steps": n_steps, "strength": strength,
        "auto_resolution": auto_resolution, "seed": base_seed + (idx * 100),
        "prompt": prompt, "negative_prompt": negative_prompt, "width": 512, "height": 512,
        "guidance_scale": guidance_scale, "image_resolution": image_resolution,
        "is_uhd": is_uhd, "is_fast": is_fast, "use_assistant": use_assistant, "prompt_assist": prompt_assist,
    } for idx in range(count)]

    return {"session_uuid": None, "use_credits": use_credits, "use_assistant": use_assistant, "prompt_assist": prompt_assist, "generate_image_list": generate_image_list}


async def browser_fetch(page, method, url, headers=None, body=None):
    script = "async ([m, u, h, b]) => { const r = await fetch(u, { method: m, headers: h || {}, body: b ? JSON.stringify(b) : null }); return { ok: r.ok, status: r.status, text: await r.text() }; }"
    return await page.evaluate(script, [method, url, headers or {}, body])


async def acquire_auth_token(page, context):
    try:
        for cookie in await context.cookies():
            if cookie["name"] in ("authentication", "auth"):
                val = urllib.parse.unquote(cookie["value"])
                token = json.loads(val).get("state", {}).get("token")
                if token: return token
        ls_auth = await page.evaluate("window.localStorage.getItem('authentication')")
        if ls_auth:
            token = json.loads(ls_auth).get("state", {}).get("token")
            if token: return token
    except: pass
    return None


async def ensure_logged_in(page, context, load_saved_cookies=True):
    if load_saved_cookies and await load_cookies(context):
        await page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=60000)
        if "login" not in page.url.lower(): return True

    if not USERNAME or not PASSWORD: raise SystemExit("Missing credentials.")
    await page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_selector('input[name="username"]')
    await page.locator('input[name="username"]').type(USERNAME, delay=50)
    await page.locator('input[type="password"]').type(PASSWORD, delay=50)
    await page.keyboard.press("Enter")
    try: await page.wait_for_selector('button:has-text("CREATE"), a[href="/generate"]', timeout=30000)
    except:
        if "generate" not in page.url.lower(): await page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)
    await save_cookies(context)
    return True


async def poll_task(page, task_uuid, quality, api_headers):
    max_attempts = 140 if quality == "4k+" else 110 if quality == "High Quality" else 90
    for attempt in range(max_attempts):
        res = await browser_fetch(page, "GET", URL_GENERATE_TASK.format(task_uuid=task_uuid), headers=api_headers)
        if res["ok"]:
            try:
                data = json.loads(res["text"]).get("response", {})
                path = data.get("no_watermark_image_url") or data.get("image_url")
                if path: return f"{URL_WASMALL}{path}"
            except: pass
        await asyncio.sleep(sleep_seconds_for_quality(quality, attempt))
    return None


async def run_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--quality", help="Quality")
    parser.add_argument("--aspect", help="Aspect")
    parser.add_argument("--prompt", help="Prompt")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--negative-prompt", help="Negative prompt")
    parser.add_argument("--confirm-payload", action="store_true")
    parser.add_argument("--skip-login-prompt", action="store_true")
    args = parser.parse_args()

    model_name = args.model or MODEL_ORDER[0]
    quality = args.quality or QUALITY_CHOICES[0]
    aspect = args.aspect or ASPECT_CHOICES[0]
    prompt = args.prompt or "Portrait of a cyberpunk city"
    neg_prompt = args.negative_prompt or MODEL_CONFIGS[model_name]["negative_prompt"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        await ensure_logged_in(page, context)
        
        # Wait for Cloudflare to clear
        for _ in range(10):
            if "Just a moment" not in await page.content(): break
            await asyncio.sleep(2)
            
        token = await acquire_auth_token(page, context)
        if not token: raise RuntimeError("Auth token missing")

        api_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Origin": "https://app.imgnai.com"}
        
        session_res = await browser_fetch(page, "POST", URL_GENERATE_SESSION, headers=api_headers)
        session_uuid = session_res["text"].strip()
        print(json.dumps({"event": "session", "session_uuid": session_uuid}))

        payload = build_payload(model_name, quality, aspect, prompt, args.count, negative_prompt=neg_prompt)
        payload["session_uuid"] = session_uuid
        
        batch_res = await browser_fetch(page, "POST", URL_GENERATE_BATCH, headers=api_headers, body=payload)
        task_uuids = json.loads(batch_res["text"])
        print(json.dumps({"event": "tasks", "task_uuids": task_uuids}))

        # Parallel Polling
        results = await asyncio.gather(*[poll_task(page, tuid, quality, api_headers) for tuid in task_uuids])
        
        final_urls = [r for r in results if r]
        print(json.dumps({"session_uuid": session_uuid, "task_uuids": task_uuids, "image_urls": final_urls}))
        
        await save_cookies(context)
        await browser.close()


def run():
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
