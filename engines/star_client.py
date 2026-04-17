import asyncio
import json
import os
from datetime import datetime

from dotenv import load_dotenv

from config.models import ASPECT_TO_RESOLUTION, STAR_MODEL_CONFIGS

load_dotenv()

SITE_BASE_URL = os.environ.get("RED_AI_SITE_BASE_URL", "https://imagine.red")
API_BASE_URL = os.environ.get("RED_AI_API_BASE_URL", "https://api.imagine.red")
IMAGE_BASE_URL = os.environ.get("RED_AI_IMAGE_BASE_URL", "https://r.imagine.red/")

URL_LOGIN = f"{SITE_BASE_URL}/login"
URL_GENERATE = f"{SITE_BASE_URL}/generate"
URL_GENERATE_SESSION = f"{API_BASE_URL}/services/webappms/api/generate-session"
URL_GENERATE_BATCH = f"{API_BASE_URL}/services/webappms/api/generate-image-batch"
URL_GENERATE_TASK = f"{API_BASE_URL}/services/webappms/api/generate-image/uuid/{{task_uuid}}"
URL_WASMALL = IMAGE_BASE_URL if IMAGE_BASE_URL.endswith("/") else f"{IMAGE_BASE_URL}/"

USERNAME = os.environ.get("IMGNAI_USERNAME")
PASSWORD = os.environ.get("IMGNAI_PASSWORD")
COOKIES_FILE = "cookie/imaginered_cookie.json"


async def save_cookies_async(context):
    cookies = await context.cookies()
    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)


async def ensure_logged_in_async(page, context, force_login=False):
    if force_login:
        await context.clear_cookies()
        await page.goto(URL_LOGIN, wait_until="domcontentloaded")
    else:
        await page.goto(URL_GENERATE, wait_until="domcontentloaded")

    if force_login or "login" in page.url.lower():
        if "login" not in page.url.lower():
            await page.goto(URL_LOGIN)
        await page.wait_for_selector('input[name="username"]')
        await page.locator('input[name="username"]').type(USERNAME, delay=100)
        await page.locator('input[type="password"]').type(PASSWORD, delay=100)
        await page.keyboard.press("Enter")
        await asyncio.sleep(5)
        await save_cookies_async(context)


def build_payload(model_name, quality, aspect, prompt, count, base_seed=None, nsfw=False, use_assistant=False, prompt_assist=False, use_credits=False, negative_prompt=None, image_resolution=None, auto_resolution=False):
    config = STAR_MODEL_CONFIGS.get(model_name, STAR_MODEL_CONFIGS["Gen"])
    res = image_resolution or ASPECT_TO_RESOLUTION.get(aspect, "BOX_X_LARGE")
    seed = base_seed if base_seed is not None else int(datetime.now().timestamp())
    generate_image_list = []
    for idx in range(count):
        generate_image_list.append(
            {
                "nsfw": nsfw,
                "profile": config["profile"],
                "n_steps": config["n_steps"],
                "strength": config["strength"],
                "auto_resolution": auto_resolution,
                "seed": seed + (idx * 100),
                "prompt": prompt,
                "negative_prompt": negative_prompt or config["negative_prompt"],
                "width": 512,
                "height": 512,
                "guidance_scale": config["guidance_scale"],
                "image_resolution": res,
                "is_uhd": quality == "4k+",
                "is_fast": quality == "Fast",
                "use_assistant": use_assistant,
                "prompt_assist": prompt_assist,
            }
        )
    return {"session_uuid": None, "generate_image_list": generate_image_list}


def parse_session_uuid(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, str):
            return data
        return data.get("session_uuid") or data.get("uuid") or text
    except Exception:
        return text


async def acquire_auth_token_async(page, context):
    auth_tokens = []

    def sniff_token(request):
        auth_header = request.headers.get("authorization")
        if auth_header and "Bearer " in auth_header:
            auth_tokens.append(auth_header.split("Bearer ")[1].strip())

    page.on("request", sniff_token)
    await asyncio.sleep(2)
    page.remove_listener("request", sniff_token)
    if auth_tokens:
        return auth_tokens[0]
    try:
        ls_auth = await page.evaluate("window.localStorage.getItem('authentication')")
        if ls_auth:
            return json.loads(ls_auth).get("state", {}).get("token")
    except Exception:
        pass
    return None
