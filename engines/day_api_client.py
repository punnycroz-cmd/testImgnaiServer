import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.parse

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
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


def save_cookies(context):
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(context.cookies(), f, indent=2)
    except Exception as e:
        LOGGER.exception("Failed to save cookies: %s", e)


def load_cookies(context):
    if not os.path.exists(COOKIES_FILE): return False
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            context.add_cookies(json.load(f))
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


def browser_fetch(page, method, url, headers=None, body=None):
    script = """
    async ([method, url, headers, body]) => {
        const opts = { method, headers: headers || {} };
        if (body) opts.body = JSON.stringify(body);
        const response = await fetch(url, opts);
        const text = await response.text();
        return { ok: response.ok, status: response.status, text };
    }
    """
    return page.evaluate(script, [method, url, headers or {}, body])


def acquire_auth_token(page, context):
    try:
        for cookie in context.cookies():
            if cookie["name"] in ("authentication", "auth"):
                val = urllib.parse.unquote(cookie["value"])
                token = json.loads(val).get("state", {}).get("token")
                if token: return token
        ls_auth = page.evaluate("window.localStorage.getItem('authentication')")
        if ls_auth:
            token = json.loads(ls_auth).get("state", {}).get("token")
            if token: return token
    except: pass
    return None


def ensure_logged_in(page, context, load_saved_cookies=True):
    if load_saved_cookies and load_cookies(context):
        page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=60000)
        if "login" not in page.url.lower(): return True

    if not USERNAME or not PASSWORD: raise SystemExit("Missing credentials.")
    page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('input[name="username"]')
    page.locator('input[name="username"]').type(USERNAME, delay=100)
    page.locator('input[type="password"]').type(PASSWORD, delay=100)
    page.keyboard.press("Enter")
    try: page.wait_for_selector('button:has-text("CREATE"), a[href="/generate"]', timeout=30000)
    except:
        if "generate" not in page.url.lower(): page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    save_cookies(context)
    return True


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model"); parser.add_argument("--quality"); parser.add_argument("--aspect")
    parser.add_argument("--prompt"); parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--negative-prompt"); parser.add_argument("--confirm-payload", action="store_true")
    parser.add_argument("--skip-login-prompt", action="store_true")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        ensure_logged_in(page, context)
        auth_token = acquire_auth_token(page, context)
        if not auth_token: sys.exit(1)

        api_headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json", "Origin": "https://app.imgnai.com"}
        session_result = browser_fetch(page, "POST", URL_GENERATE_SESSION, headers=api_headers)
        session_uuid = session_result["text"].strip()
        print(json.dumps({"event": "session", "session_uuid": session_uuid}))

        payload = build_payload(args.model, args.quality, args.aspect, args.prompt, args.count, negative_prompt=args.negative_prompt)
        payload["session_uuid"] = session_uuid
        batch_result = browser_fetch(page, "POST", URL_GENERATE_BATCH, headers=api_headers, body=payload)
        task_uuids = json.loads(batch_result["text"])
        print(json.dumps({"event": "tasks", "task_uuids": task_uuids}))

        final_image_urls = []
        for task_uuid in task_uuids:
            completed = False
            for attempt in range(90):
                poll_result = browser_fetch(page, "GET", URL_GENERATE_TASK.format(task_uuid=task_uuid), headers=api_headers)
                if poll_result["ok"]:
                    data = json.loads(poll_result["text"]).get("response", {})
                    image_path = data.get("no_watermark_image_url") or data.get("image_url")
                    if image_path:
                        final_image_urls.append(f"{URL_WASMALL}{image_path}")
                        completed = True
                        break
                time.sleep(sleep_seconds_for_quality(args.quality, attempt))
        
        save_cookies(context)
        print(json.dumps({"session_uuid": session_uuid, "task_uuids": task_uuids, "image_urls": final_image_urls}))


if __name__ == "__main__":
    run()
