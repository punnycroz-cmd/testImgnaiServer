import logging
import os
import traceback

import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config.schemas import GenerateRequest
from core.vault import R2Vault
from engines.day import DayManager
from engines.star import GenerateRequest as StarGenerateRequest
from engines.star import StarManager

load_dotenv()
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("aether")

COOKIE_DIR = "cookie"
os.makedirs(COOKIE_DIR, exist_ok=True)

R2_VAULT = R2Vault(
    account_id="c733aa6dbf847adf0949e4387eb6f15f",
    bucket_name="imagenai",
    public_url="https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev",
)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

day_mgr = DayManager(COOKIE_DIR, "", R2_VAULT)
star_mgr = StarManager(COOKIE_DIR, "", R2_VAULT)


@app.get("/")
async def index():
    return {"status": "Aether Server Online", "vault": R2_VAULT.bucket_name}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "cookie_dir": os.path.exists(COOKIE_DIR),
        "day_cookie": os.path.exists(os.path.join(COOKIE_DIR, "imgnai_cookie.json")),
        "star_cookie": os.path.exists(os.path.join(COOKIE_DIR, "imaginered_cookie.json")),
        "r2_configured": bool(R2_VAULT.access_key and R2_VAULT.secret_key),
    }


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req.count = 4
        logger.info("generate request start realm=%s model=%s quality=%s prompt=%s", req.realm, req.model, req.quality, req.prompt[:60])
        if req.nsfw:
            star_req = StarGenerateRequest(**req.model_dump())
            return await star_mgr.generate(star_req)
        result = await anyio.to_thread.run_sync(day_mgr.generate, req)
        logger.info("generate request done realm=day client_id=%s images=%s", req.client_id, len(result.get("image_urls", [])))
        return result
    except Exception as e:
        traceback.print_exc()
        logger.exception("generate request failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
