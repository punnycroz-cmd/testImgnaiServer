import asyncio
import logging
import os
import uuid
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
job_store = {}
job_lock = asyncio.Lock()


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


async def _run_generation(job_id: str, req: GenerateRequest):
    try:
        logger.info("job start job_id=%s realm=%s model=%s quality=%s", job_id, req.realm, req.model, req.quality)
        if req.nsfw:
            star_req = StarGenerateRequest(**req.model_dump())
            result = await star_mgr.generate(star_req)
        else:
            result = await anyio.to_thread.run_sync(day_mgr.generate, req)
        async with job_lock:
            job_store[job_id] = {"status": "done", "result": result}
        logger.info("job done job_id=%s images=%s", job_id, len(result.get("image_urls", [])))
    except Exception as exc:
        logger.exception("job failed job_id=%s", job_id)
        async with job_lock:
            job_store[job_id] = {"status": "error", "error": str(exc)}


@app.get("/job-status/{job_id}")
async def job_status(job_id: str):
    async with job_lock:
        job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **job}


@app.get("/history")
async def history(page: int = 1, limit: int = 20):
    items = R2_VAULT.list_images(prefix="vault/")
    total = len(items)
    start = max(0, (page - 1) * limit)
    end = start + limit
    page_items = items[start:end]
    return {
        "items": page_items,
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": end < total,
    }


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req.count = 4
        job_id = req.client_id or uuid.uuid4().hex[:12]
        async with job_lock:
            existing = job_store.get(job_id)
            if existing:
                return {"job_id": job_id, **existing}
            job_store[job_id] = {"status": "running"}
        logger.info("generate request accepted job_id=%s realm=%s model=%s quality=%s prompt=%s", job_id, req.realm, req.model, req.quality, req.prompt[:60])
        asyncio.create_task(_run_generation(job_id, req))
        return {"job_id": job_id, "status": "running"}
    except Exception as e:
        traceback.print_exc()
        logger.exception("generate request failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
