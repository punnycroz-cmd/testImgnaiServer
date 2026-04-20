import asyncio
import json
import os
import logging
import urllib.parse
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
DEBUG_DIR = "screenshots"


async def save_cookies_async(context, logger=None):
    cookies = await context.cookies()
    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    if logger:
        logger.info("saved star cookies to %s", COOKIES_FILE)


def _safe_preview(value: str, keep: int = 12) -> str:
    if not value:
        return ""
    value = str(value)
    if len(value) <= keep * 2:
        return value
    return f"{value[:keep]}...{value[-keep:]}"


def _find_token_path(value, path="root", max_depth=6):
    if max_depth < 0:
        return None
    if isinstance(value, str):
      if value.startswith("eyJ") and len(value) > 40:
          return path
      return None
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}"
            if key.lower() in {"token", "access_token", "authtoken", "jwt"} and isinstance(item, str) and item:
                return next_path
            found = _find_token_path(item, next_path, max_depth - 1)
            if found:
                return found
    if isinstance(value, list):
        for idx, item in enumerate(value):
            found = _find_token_path(item, f"{path}[{idx}]", max_depth - 1)
            if found:
                return found
    return None


async def debug_star_auth_state(page, context, logger=None, label="login"):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot_path = os.path.join(DEBUG_DIR, f"star_{label}_{ts}.png")
        await page.screenshot(path=shot_path, full_page=True)
        if logger:
            logger.info("star debug screenshot saved to %s", shot_path)
    except Exception as exc:
        if logger:
            logger.warning("star debug screenshot failed: %s", exc)

    try:
        cookies = await context.cookies()
        if logger:
            for cookie in cookies:
                name = cookie.get("name")
                value = urllib.parse.unquote(cookie.get("value", ""))
                token_path = None
                try:
                    parsed = json.loads(value)
                    token_path = _find_token_path(parsed)
                except Exception:
                    pass
                logger.info(
                    "star debug cookie name=%s domain=%s value=%s token_path=%s",
                    name,
                    cookie.get("domain"),
                    _safe_preview(value),
                    token_path,
                )
    except Exception as exc:
        if logger:
            logger.warning("star debug cookie dump failed: %s", exc)

    for storage_name in ("localStorage", "sessionStorage"):
        try:
            keys = await page.evaluate(f"Object.keys(window.{storage_name})")
            if logger:
                logger.info("star debug %s keys=%s", storage_name, keys)
            for key in keys or []:
                try:
                    value = await page.evaluate(f"window.{storage_name}.getItem({json.dumps(key)})")
                    token_path = None
                    try:
                        parsed = json.loads(urllib.parse.unquote(value or ""))
                        token_path = _find_token_path(parsed)
                    except Exception:
                        pass
                    if logger:
                        logger.info(
                            "star debug %s key=%s value=%s token_path=%s",
                            storage_name,
                            key,
                            _safe_preview(urllib.parse.unquote(value or "")),
                            token_path,
                        )
                except Exception as exc:
                    if logger:
                        logger.warning("star debug %s key=%s read failed: %s", storage_name, key, exc)
        except Exception as exc:
            if logger:
                logger.warning("star debug %s dump failed: %s", storage_name, exc)


async def capture_star_step(page, logger=None, label="step"):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot_path = os.path.join(DEBUG_DIR, f"star_{label}_{ts}.png")
        await page.screenshot(path=shot_path, full_page=True)
        if logger:
            logger.info("star step screenshot saved to %s", shot_path)
    except Exception as exc:
        if logger:
            logger.warning("star step screenshot failed at %s: %s", label, exc)


async def ensure_logged_in_async(page, context, force_login=False, logger=None):
    if force_login:
        await context.clear_cookies()
        if logger:
            logger.warning("forcing star login")
        await page.goto(URL_LOGIN, wait_until="domcontentloaded")
        await capture_star_step(page, logger=logger, label="force_login_page")
    else:
        await page.goto(URL_GENERATE, wait_until="domcontentloaded")
        await capture_star_step(page, logger=logger, label="generate_page")

    if force_login or "login" in page.url.lower():
        if "login" not in page.url.lower():
            await page.goto(URL_LOGIN)
            await capture_star_step(page, logger=logger, label="redirect_login")
        await page.wait_for_selector('input[name="username"]')
        await capture_star_step(page, logger=logger, label="login_form_ready")
        await page.locator('input[name="username"]').type(USERNAME, delay=100)
        await page.locator('input[type="password"]').type(PASSWORD, delay=100)
        await capture_star_step(page, logger=logger, label="login_form_filled")
        await page.keyboard.press("Enter")
        await capture_star_step(page, logger=logger, label="after_enter")
        await asyncio.sleep(5)
        await page.goto(URL_GENERATE, wait_until="domcontentloaded")
        await capture_star_step(page, logger=logger, label="after_generate_redirect")
        await asyncio.sleep(2)
        await debug_star_auth_state(page, context, logger=logger, label="post_login")
        await save_cookies_async(context, logger=logger)
        if logger:
            logger.info("star login complete")


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


async def acquire_auth_token_async(page, context, logger=None):
    def extract_token_from_value(raw_value):
        if not raw_value:
            return None
        try:
            decoded = json.loads(raw_value)
        except Exception:
            return None
        if isinstance(decoded, dict):
            direct = decoded.get("token")
            if isinstance(direct, str) and direct:
                return direct
            state = decoded.get("state")
            if isinstance(state, dict):
                token = state.get("token")
                if isinstance(token, str) and token:
                    return token
                auth = state.get("authentication")
                if isinstance(auth, dict):
                    token = auth.get("token")
                    if isinstance(token, str) and token:
                        return token
        token_path = _find_token_path(decoded)
        if token_path and logger:
            logger.info("star auth token candidate path=%s", token_path)
        return None

    try:
        cookies = await context.cookies()
        for cookie in cookies:
            name = (cookie.get("name") or "").lower()
            if any(part in name for part in ("auth", "token", "session")):
                token = extract_token_from_value(urllib.parse.unquote(cookie.get("value", "")))
                if token:
                    if logger:
                        logger.info("star auth token found in cookie %s", cookie.get("name"))
                    return token
        if logger:
            logger.info("star cookie names=%s", [c.get("name") for c in cookies])
    except Exception:
        pass

    auth_tokens = []

    def sniff_token(request):
        auth_header = request.headers.get("authorization")
        if auth_header and "Bearer " in auth_header:
            auth_tokens.append(auth_header.split("Bearer ")[1].strip())

    page.on("request", sniff_token)
    try:
        if "generate" not in page.url.lower():
            await page.goto(URL_GENERATE, wait_until="domcontentloaded")
        await asyncio.sleep(4)
    finally:
        page.remove_listener("request", sniff_token)
    if auth_tokens:
        if logger:
            logger.info("star auth token found in network request")
        return auth_tokens[0]
    for storage_name in ("localStorage", "sessionStorage"):
        try:
            keys = await page.evaluate(f"Object.keys(window.{storage_name})")
            for key in keys or []:
                value = await page.evaluate(f"window.{storage_name}.getItem({json.dumps(key)})")
                token = extract_token_from_value(urllib.parse.unquote(value or ""))
                if token:
                    if logger:
                        logger.info("star auth token found in %s key=%s", storage_name, key)
                    return token
        except Exception:
            continue

    if logger:
        logger.warning("star auth token not found")
    return None
