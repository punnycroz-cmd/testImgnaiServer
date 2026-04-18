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
from core.db import Database
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
DB = Database()
DB.init()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

day_mgr = DayManager(COOKIE_DIR, "", R2_VAULT, db=DB)
star_mgr = StarManager(COOKIE_DIR, "", R2_VAULT, db=DB)
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
        logger.info("job start request_id=%s client_id=%s realm=%s model=%s quality=%s", job_id, req.client_id, req.realm, req.model, req.quality)
        if req.nsfw:
            star_req = StarGenerateRequest(**req.model_dump())
            result = await star_mgr.generate(star_req, request_id=job_id)
        else:
            result = await anyio.to_thread.run_sync(day_mgr.generate, req, job_id)
        async with job_lock:
            job_store[job_id] = {"status": "done", "result": result, "client_id": req.client_id, "request_id": job_id}
        DB.update_generation(job_id, status="done", result=result)
        logger.info("job done request_id=%s images=%s", job_id, len(result.get("image_urls", [])))
    except Exception as exc:
        logger.exception("job failed request_id=%s", job_id)
        async with job_lock:
            job_store[job_id] = {"status": "error", "error": str(exc), "client_id": req.client_id, "request_id": job_id}
        DB.update_generation(job_id, status="error", error=str(exc))


@app.get("/job-status/{request_id}")
async def job_status(request_id: str):
    async with job_lock:
        job = job_store.get(request_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"request_id": request_id, **job}


@app.get("/history")
async def history(page: int = 1, limit: int = 20):
    offset = max(0, (page - 1) * limit)
    rows = DB.list_generations(limit=limit, offset=offset)
    total = len(rows) if len(rows) < limit else offset + len(rows) + 1
    page_items = []
    for row in rows:
        image_rows = []
        gen_id = row["id"]
        if DB.enabled:
            with DB.connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT * FROM generation_images WHERE generation_id = %s ORDER BY image_index ASC", (gen_id,))
                image_rows = cur.fetchall()
        page_items.append(
            {
                "request_id": row["request_id"],
                "client_id": row["client_id"],
                "realm": row["realm"],
                "status": row["status"],
                "prompt": row["prompt"],
                "model": row["model"],
                "quality": row["quality"],
                "aspect": row["aspect"],
                "session_uuid": row["session_uuid"],
                "task_uuids": row["task_uuids"],
                "images": image_rows,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return {
        "items": page_items,
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": len(rows) == limit,
    }


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req.count = 4
        request_id = str(uuid.uuid4())
        DB.create_generation(
            generation_id=request_id,
            request_id=request_id,
            client_id=req.client_id,
            realm=req.realm or "day",
            prompt=req.prompt,
            model=req.model,
            quality=req.quality,
            aspect=req.aspect,
            seed=req.seed,
            negative_prompt=req.negative_prompt,
            count=req.count,
        )
        async with job_lock:
            existing = job_store.get(request_id)
            if existing:
                return {"request_id": request_id, **existing}
            job_store[request_id] = {"status": "running", "client_id": req.client_id, "request_id": request_id}
        logger.info("generate request accepted request_id=%s client_id=%s realm=%s model=%s quality=%s prompt=%s", request_id, req.client_id, req.realm, req.model, req.quality, req.prompt[:60])
        asyncio.create_task(_run_generation(request_id, req))
        return {"request_id": request_id, "status": "running", "client_id": req.client_id}
    except Exception as e:
        traceback.print_exc()
        logger.exception("generate request failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
