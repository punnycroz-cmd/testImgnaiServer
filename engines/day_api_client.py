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

R2_VAULT = R2Vault(
    account_id="c733aa6dbf847adf0949e4387eb6f15f",
    bucket_name="imagenai",
    public_url="https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev",
)
LOGGER = logging.getLogger("aether.day.cli")


def sleep_seconds_for_quality(quality: str, attempt: int) -> float:
    if quality == "4k+":
        base = 2.75
        cap = 18.0
    elif quality == "High Quality":
        base = 2.25
        cap = 14.0
    else:
        base = 1.5
        cap = 10.0
    return min(cap, base * (1.25 ** attempt))


def ask_yes_no(question, default=True):
    default_str = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {default_str}: ").strip().lower()
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer with 'y' or 'n'.")


def ask_text(question, default=None, required=True):
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{question}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("Please enter a value.")


def choose_from_list(title, options, default_index=0):
    print(f"\n{title}")
    for idx, option in enumerate(options, 1):
        marker = " (default)" if idx - 1 == default_index else ""
        print(f"  {idx}. {option}{marker}")
    while True:
        raw = input(f"Choose 1-{len(options)} [{default_index + 1}]: ").strip()
        if raw == "":
            return options[default_index]
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print("Please choose one of the listed numbers.")


def save_cookies(context):
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(context.cookies(), f, indent=2)
    except Exception as e:
        LOGGER.exception("Failed to save cookies: %s", e)


def load_cookies(context):
    if not os.path.exists(COOKIES_FILE):
        return False
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            context.add_cookies(json.load(f))
        return True
    except Exception:
        return False


def model_choice_from_args_or_prompt(args):
    if args.model:
        if args.model not in MODEL_CONFIGS:
            raise SystemExit(f"Unknown model '{args.model}'. Use --list-models to see valid names.")
        return args.model
    return choose_from_list("Select a model:", MODEL_ORDER, 0)


def quality_choice_from_args_or_prompt(args):
    if args.quality:
        if args.quality not in QUALITY_CHOICES:
            raise SystemExit(f"Unknown quality '{args.quality}'. Use: {', '.join(QUALITY_CHOICES)}")
        return args.quality
    return choose_from_list("Select quality:", QUALITY_CHOICES, 0)


def aspect_choice_from_args_or_prompt(args):
    if args.aspect:
        if args.aspect not in ASPECT_CHOICES:
            raise SystemExit(f"Unknown aspect '{args.aspect}'. Use: {', '.join(ASPECT_CHOICES)}")
        return args.aspect
    return choose_from_list("Select aspect ratio:", ASPECT_CHOICES, 0)


def resolution_choice_from_args_or_prompt(args, aspect):
    default_resolution = ASPECT_TO_RESOLUTION[aspect]
    if args.resolution:
        return args.resolution
    if not args.interactive_resolution_override:
        return default_resolution
    if ask_yes_no(f"Use default resolution {default_resolution} for aspect {aspect}?", default=True):
        return default_resolution
    options = ["BOX_X_LARGE", "LANDSCAPE", "WIDE_LARGE", "PORTRAIT", "TALL_LARGE"]
    return choose_from_list("Select resolution keyword:", options, options.index(default_resolution))


def build_payload(
    model_name,
    quality,
    aspect,
    prompt,
    count,
    base_seed=None,
    nsfw=False,
    use_assistant=False,
    prompt_assist=False,
    use_credits=False,
    strength=None,
    n_steps=None,
    guidance_scale=None,
    negative_prompt=None,
    image_resolution=None,
    auto_resolution=False,
):
    config = MODEL_CONFIGS[model_name]
    profile = config["profile"]
    image_resolution = image_resolution or ASPECT_TO_RESOLUTION[aspect]
    is_fast = quality == "Fast"
    is_uhd = quality == "4k+"
    strength = config["strength"] if strength is None else strength
    n_steps = config["n_steps"] if n_steps is None else n_steps
    guidance_scale = config["guidance_scale"] if guidance_scale is None else guidance_scale
    negative_prompt = config["negative_prompt"] if negative_prompt is None else negative_prompt
    if base_seed is None:
        base_seed = int(time.time())

    generate_image_list = []
    for idx in range(count):
        generate_image_list.append(
            {
                "nsfw": nsfw,
                "profile": profile,
                "n_steps": n_steps,
                "strength": strength,
                "auto_resolution": auto_resolution,
                "seed": base_seed + (idx * 100),
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": 512,
                "height": 512,
                "guidance_scale": guidance_scale,
                "image_resolution": image_resolution,
                "is_uhd": is_uhd,
                "is_fast": is_fast,
                "use_assistant": use_assistant,
                "prompt_assist": prompt_assist,
            }
        )

    return {
        "session_uuid": None,
        "use_credits": use_credits,
        "use_assistant": use_assistant,
        "prompt_assist": prompt_assist,
        "generate_image_list": generate_image_list,
    }


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


def response_looks_like_no_credits(text):
    try:
        data = json.loads(text)
    except Exception:
        return False
    if isinstance(data, dict):
        return data.get("errorKey") == "no-credits" or data.get("message") == "error.no-credits"
    return False


def acquire_auth_token(page, context):
    try:
        for cookie in context.cookies():
            if cookie["name"] in ("authentication", "auth"):
                val = urllib.parse.unquote(cookie["value"])
                token = json.loads(val).get("state", {}).get("token")
                if token:
                    return token
    except Exception:
        pass

    try:
        ls_auth = page.evaluate("window.localStorage.getItem('authentication')")
        if ls_auth:
            token = json.loads(ls_auth).get("state", {}).get("token")
            if token:
                return token
    except Exception:
        pass

    auth_tokens = []

    def sniff_token(request):
        auth_header = request.headers.get("authorization")
        if auth_header and "Bearer " in auth_header:
            auth_tokens.append(auth_header.split("Bearer ")[1].strip())

    page.on("request", sniff_token)
    if "generate" not in page.url.lower():
        page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    page.remove_listener("request", sniff_token)

    if auth_tokens:
        return auth_tokens[0]
    return None


def ensure_logged_in(page, context, load_saved_cookies=True):
    if load_saved_cookies and load_cookies(context):
        LOGGER.info("Loaded saved day cookies")
        page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=60000)
        if "login" not in page.url.lower():
            LOGGER.info("Reused saved session")
            return True

    if not USERNAME or not PASSWORD:
        raise SystemExit("Set IMGNAI_USERNAME and IMGNAI_PASSWORD before running.")

    LOGGER.info("Performing fresh day login")
    page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('input[name="username"]')
    page.locator('input[name="username"]').type(USERNAME, delay=100)
    page.locator('input[type="password"]').type(PASSWORD, delay=100)
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")
    try:
        page.locator('button:has-text("Log in"), button[type="submit"]').first.click(timeout=2000)
    except Exception:
        pass

    try:
        print("Waiting for dashboard to load...")
        page.wait_for_selector('button:has-text("CREATE"), a[href="/generate"]', timeout=30000)
        print("✅ Dashboard detected.")
    except PlaywrightTimeoutError:
        print("⚠️ Direct UI check failed, checking URL...")
        if "generate" not in page.url.lower():
            page.goto(URL_GENERATE, wait_until="domcontentloaded", timeout=30000)

    page.wait_for_timeout(2000)
    save_cookies(context)
    return True


def run():
    parser = argparse.ArgumentParser(description="ImgNai API payload builder and generator")
    parser.add_argument("--model", help="Model display name, for example 'HyperX'")
    parser.add_argument("--quality", help="Quality label, for example 'Fast' or 'High Quality'")
    parser.add_argument("--aspect", help="Aspect ratio, for example '4:7'")
    parser.add_argument("--resolution", help="Resolution keyword override")
    parser.add_argument("--prompt", help="Prompt text")
    parser.add_argument("--count", type=int, default=4, help="Images per batch")
    parser.add_argument("--seed", type=int, help="Base seed")
    parser.add_argument("--use-assistant", action="store_true", help="Enable assistant flag")
    parser.add_argument("--prompt-assist", action="store_true", help="Enable prompt assist flag")
    parser.add_argument("--use-credits", action="store_true", help="Use credits")
    parser.add_argument("--negative-prompt", help="Override negative prompt")
    parser.add_argument("--auto-resolution", action="store_true", help="Set auto_resolution true")
    parser.add_argument("--no-download", action="store_true", help="Skip image downloading")
    parser.add_argument("--list-models", action="store_true", help="Print available models and exit")
    parser.add_argument("--interactive-resolution-override", action="store_true", help="Ask before using the default resolution")
    parser.add_argument("--skip-login-prompt", action="store_true", help="Do not ask before loading saved cookies")
    parser.add_argument("--confirm-payload", action="store_true", help="Do not ask for confirmation on settings")
    args = parser.parse_args()

    if args.list_models:
        for name in MODEL_ORDER:
            print(f"{name} -> {MODEL_CONFIGS[name]['profile']}")
        return

    if not os.path.exists(COOKIES_FILE) and not USERNAME:
        print(f"Missing {COOKIES_FILE} and IMGNAI_USERNAME. You need a saved login session.")
        sys.exit(1)

    model_name = model_choice_from_args_or_prompt(args)
    quality = quality_choice_from_args_or_prompt(args)
    aspect = aspect_choice_from_args_or_prompt(args)
    resolution = resolution_choice_from_args_or_prompt(args, aspect)
    prompt = args.prompt or ask_text("Prompt")
    count = 4
    base_seed = args.seed if args.seed is not None else int(time.time())
    load_saved = True

    with sync_playwright() as p:
        LOGGER.info("Starting day browser session")
        browser = p.chromium.launch(headless=False, args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        LOGGER.info("Day generation request start model=%s quality=%s aspect=%s prompt=%s", model_name, quality, aspect, prompt[:60])
        ensure_logged_in(page, context, load_saved_cookies=load_saved)
        auth_token = acquire_auth_token(page, context)
        if not auth_token:
            LOGGER.error("Could not locate an authorization token")
            sys.exit(1)

        api_headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.imgnai.com",
            "Referer": "https://app.imgnai.com/generate",
        }

        session_result = browser_fetch(page, "POST", URL_GENERATE_SESSION, headers=api_headers)
        if not session_result["ok"] and session_result.get("status") == 401 and load_saved:
            print("Token expired! Forcing a new login...")
            context.clear_cookies()
            ensure_logged_in(page, context, load_saved_cookies=False)
            auth_token = acquire_auth_token(page, context)
            if not auth_token:
                print("Could not locate an authorization token after forcing login.")
                sys.exit(1)
            api_headers["Authorization"] = f"Bearer {auth_token}"
            session_result = browser_fetch(page, "POST", URL_GENERATE_SESSION, headers=api_headers)

        if not session_result["ok"]:
            print(f"Failed to create session: {session_result['status']}")
            sys.exit(1)

        session_uuid = session_result["text"].strip()
        print(json.dumps({"event": "session", "session_uuid": session_uuid}))
        nsfw = False
        if args.negative_prompt is None:
            if args.confirm_payload or ask_yes_no("Use model default negative prompt?", default=True):
                negative_prompt = None
            else:
                negative_prompt = ask_text("Negative prompt", default=MODEL_CONFIGS[model_name]["negative_prompt"], required=False)
        else:
            negative_prompt = args.negative_prompt

        payload = build_payload(
            model_name=model_name,
            quality=quality,
            aspect=aspect,
            prompt=prompt,
            count=count,
            base_seed=base_seed,
            nsfw=nsfw,
            use_assistant=args.use_assistant,
            prompt_assist=args.prompt_assist,
            use_credits=args.use_credits,
            negative_prompt=negative_prompt,
            image_resolution=resolution,
            auto_resolution=args.auto_resolution,
        )
        payload["session_uuid"] = session_uuid

        batch_result = browser_fetch(page, "POST", URL_GENERATE_BATCH, headers=api_headers, body=payload)
        if not batch_result["ok"] and quality == "4k+" and response_looks_like_no_credits(batch_result["text"]):
            quality = "High Quality"
            payload["is_uhd"] = False
            payload["is_fast"] = False
            batch_result = browser_fetch(page, "POST", URL_GENERATE_BATCH, headers=api_headers, body=payload)

        if not batch_result["ok"]:
            print(f"Failed to submit batch: {batch_result['status']}")
            print(f"Error details: {batch_result['text']}")
            sys.exit(1)

        try:
            task_uuids = json.loads(batch_result["text"])
        except Exception as e:
            print(f"Could not parse batch response: {e}")
            sys.exit(1)
        print(json.dumps({"event": "tasks", "task_uuids": task_uuids}))

        final_image_urls = []
        for task_uuid in task_uuids:
            completed = False
            max_attempts = 140 if quality == "4k+" else 110 if quality == "High Quality" else 90
            LOGGER.info("Polling day task %s with up to %s attempts", task_uuid[:8], max_attempts)
            for attempt in range(max_attempts):
                poll_result = browser_fetch(page, "GET", URL_GENERATE_TASK.format(task_uuid=task_uuid), headers=api_headers)
                if poll_result["ok"]:
                    try:
                        poll_data = json.loads(poll_result["text"])
                    except Exception:
                        poll_data = {}
                    response_obj = poll_data.get("response")
                    if isinstance(response_obj, dict):
                        image_path = response_obj.get("no_watermark_image_url") or response_obj.get("image_url")
                        if image_path:
                            final_image_urls.append(f"{URL_WASMALL}{image_path}")
                            completed = True
                            break
                page.wait_for_timeout(int(sleep_seconds_for_quality(quality, attempt) * 1000))
            if not completed:
                print(f"  Timed out: {task_uuid}")

        save_cookies(context)
        context.close()
        browser.close()
        print(json.dumps({
            "session_uuid": session_uuid,
            "task_uuids": task_uuids,
            "image_urls": final_image_urls,
        }))


if __name__ == "__main__":
    run()
