import asyncio
from typing import Optional
import logging
import os
import uuid
import traceback
import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config.schemas import GenerateRequest
from core.db import DB
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB pool
    await DB.init()
    yield
    # Close DB pool
    pool = await DB.get_pool()
    if pool:
        await pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cancelled_jobs = set()
day_mgr = DayManager(COOKIE_DIR, "", R2_VAULT, db=DB, cancelled_jobs=cancelled_jobs)
star_mgr = StarManager(COOKIE_DIR, "", R2_VAULT, db=DB, cancelled_jobs=cancelled_jobs)
job_store = {}
job_lock = asyncio.Lock()


def classify_error(message: str) -> str:
    msg = (message or "").lower()
    permanent = [
        "authentication", "unauthorized", "401", "403",
        "invalid prompt", "content policy", "bad request", "validation error", "400",
        "quota exceeded", "account disabled", "payment required",
    ]
    transient = [
        "timeout", "connection refused", "network unreachable",
        "502", "503", "504", "gateway error", "vault upload failed",
        "r2 error", "s3 error", "connection pool exhausted",
        "subprocess crashed", "exit code", "killed", "day failed",
    ]
    if any(k in msg for k in permanent):
        return "PERMANENT"
    if any(k in msg for k in transient):
        return "TRANSIENT"
    return "TRANSIENT"


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
        logger.info("[>] Job Start: %s", job_id[:8])
        is_star = (req.realm or "").lower() == "star" or req.nsfw
        await DB.update_generation(job_id, status="processing")
        if is_star:
            star_req = StarGenerateRequest(**req.model_dump())
            result = await star_mgr.generate(star_req, request_id=job_id)
        else:
            result = await day_mgr.generate(req, job_id)
        
        async with job_lock:
            job_store[job_id] = {"status": "done", "result": result, "client_id": req.client_id, "request_id": job_id}
        
        await DB.update_generation(job_id, status="done", result=result, error=None, last_error_text=None)
        logger.info("[!] Job: %s finished", job_id[:8])
    except Exception as exc:
        logger.exception("job failed request_id=%s", job_id)
        async with job_lock:
            job_store[job_id] = {"status": "error", "error": str(exc), "client_id": req.client_id, "request_id": job_id}
        await DB.update_generation(job_id, status="failed", error=str(exc), last_error_text=str(exc))


@app.get("/job-status/{request_id}")
async def job_status(request_id: str):
    async with job_lock:
        job = job_store.get(request_id)
    
    row = await DB.get_generation(request_id)
    if not row:
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return {"request_id": request_id, **job}
    
    return {
        "request_id": request_id,
        "status": row["status"],
        "client_id": row["client_id"],
        "prompt": row["prompt"],
        "realm": row["realm"],
        "images": row.get("images", []),
        "result": row.get("result"),
        "error": row.get("error")
    }

from pydantic import BaseModel
from typing import List

class JobBatchRequest(BaseModel):
    request_ids: List[str]

@app.post("/job-status-batch")
async def job_status_batch(req: JobBatchRequest):
    results = {}
    for rid in req.request_ids:
        async with job_lock:
            job = job_store.get(rid)
        row = await DB.get_generation(rid)
        if not row:
            if job:
                results[rid] = {"request_id": rid, **job}
            continue
        results[rid] = {
            "request_id": rid,
            "status": row["status"],
            "client_id": row["client_id"],
            "prompt": row["prompt"],
            "realm": row["realm"],
            "images": row.get("images", []),
            "result": row.get("result"),
            "error": row.get("error")
        }
    return results


@app.get("/resume/{request_id}")
async def resume(request_id: str):
    row = await DB.get_generation(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    
    return {
        "request_id": row["request_id"],
        "client_id": row["client_id"],
        "realm": row["realm"],
        "status": row["status"],
        "prompt": row["prompt"],
        "model": row["model"],
        "quality": row["quality"],
        "aspect": row["aspect"],
        "count": row["count"],
        "session_uuid": row["session_uuid"],
        "result": row["result"],
        "images": row.get("images", []),
        "error": row.get("error"),
        "created_at": row["created_at"] if isinstance(row.get("created_at"), str) else (row["created_at"].isoformat() if row.get("created_at") else None),
    }


@app.get("/debug/vault-stats")
async def vault_stats(realm: Optional[str] = None):
    """Debug endpoint: shows total batch count and first few IDs per page."""
    pool = await DB.get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Total count
            if realm and realm.lower() == 'day':
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE is_hidden = false AND (LOWER(realm) = 'day' OR realm IS NULL)")
                total_row = await cur.fetchone()
                total = total_row["cnt"] if total_row else 0
                
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE (LOWER(realm) = 'day' OR realm IS NULL) AND is_hidden = false AND status = 'done'")
                valid_row = await cur.fetchone()
                valid = valid_row["cnt"] if valid_row else 0
            elif realm:
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE is_hidden = false AND LOWER(realm) = LOWER(%s)", (realm,))
                total_row = await cur.fetchone()
                total = total_row["cnt"] if total_row else 0
                
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE LOWER(realm) = LOWER(%s) AND is_hidden = false AND status = 'done'", (realm,))
                valid_row = await cur.fetchone()
                valid = valid_row["cnt"] if valid_row else 0
            else:
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE is_hidden = false")
                total_row = await cur.fetchone()
                total = total_row["cnt"] if total_row else 0
                
                await cur.execute("SELECT COUNT(*) as cnt FROM generations WHERE is_hidden = false AND status = 'done'")
                valid_row = await cur.fetchone()
                valid = valid_row["cnt"] if valid_row else 0

            # First 60 IDs ordered by created_at DESC
            if realm and realm.lower() == 'day':
                await cur.execute("SELECT request_id, realm, prompt, created_at FROM generations WHERE is_hidden = false AND (LOWER(realm) = 'day' OR realm IS NULL) ORDER BY created_at DESC LIMIT 60")
            elif realm:
                await cur.execute("SELECT request_id, realm, prompt, created_at FROM generations WHERE is_hidden = false AND LOWER(realm) = LOWER(%s) ORDER BY created_at DESC LIMIT 60", (realm,))
            else:
                await cur.execute("SELECT request_id, realm, prompt, created_at FROM generations WHERE is_hidden = false ORDER BY created_at DESC LIMIT 60")
            rows = await cur.fetchall()

            # Group into pages of 20
            pages = {}
            for i, row in enumerate(rows):
                page_num = (i // 20) + 1
                if page_num not in pages:
                    pages[page_num] = []
                pages[page_num].append({
                    "request_id": row["request_id"],
                    "realm": row["realm"],
                    "prompt": (row["prompt"] or "")[:50],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })

    return {"total_batches": total, "valid_batches": valid, "realm_filter": realm, "pages_preview": pages}


@app.get("/history")
async def history(page: int = 1, limit: int = 20, realm: Optional[str] = None, before: Optional[str] = None):
    offset = max(0, (page - 1) * limit)
    # Use before (cursor) if provided, otherwise fallback to page-based offset
    page_items = await DB.list_generations(limit=limit, offset=offset, realm=realm, before=before)
    
    return {
        "items": page_items,
        "page": page,
        "limit": limit,
        "has_more": len(page_items) == limit,
        "next_cursor": page_items[-1]["created_at"] if page_items else None
    }


@app.post("/history/batch/{request_id}/hide")
async def hide_batch(request_id: str):
    await DB.hide_generation(request_id)
    return {"status": "ok", "hidden": request_id}


@app.delete("/history/batch/{request_id}")
async def delete_batch(request_id: str):
    await DB.delete_generation(request_id)
    return {"status": "ok", "deleted": request_id}


@app.post("/cancel-job/{request_id}")
async def cancel_job(request_id: str):
    cancelled_jobs.add(request_id)
    async with job_lock:
        if request_id in job_store:
            job_store[request_id]["status"] = "error"
            job_store[request_id]["error"] = "Job cancelled by user"
    await DB.update_generation(request_id, status="error")
    return {"status": "ok", "cancelled": request_id}


@app.post("/cancel-all-jobs")
async def cancel_all_jobs():
    async with job_lock:
        for rid in job_store:
            if job_store[rid]["status"] == "running":
                cancelled_jobs.add(rid)
                job_store[rid]["status"] = "error"
                job_store[rid]["error"] = "All jobs cancelled"
                await DB.update_generation(rid, status="error")
    return {"status": "ok"}


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req.count = 4
        realm = (req.realm or "day").lower()
        request_id = str(uuid.uuid4())
        
        await DB.create_generation(
            request_id=request_id,
            client_id=req.client_id,
            realm=realm,
            prompt=req.prompt,
            model=req.model,
            quality=req.quality,
            aspect=req.aspect,
            seed=req.seed,
            negative_prompt=req.negative_prompt,
            count=req.count,
            status="pending",
        )
        
        async with job_lock:
            job_store[request_id] = {"status": "pending", "client_id": req.client_id, "request_id": request_id}
        
        logger.info("[>] Job: %s (%s) started", request_id[:8], req.model)
        asyncio.create_task(_run_generation(request_id, req))
        return {"request_id": request_id, "status": "pending", "client_id": req.client_id}
    except Exception as e:
        traceback.print_exc()
        logger.exception("generate request failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/retry-job/{request_id}")
async def retry_job(request_id: str):
    row = await DB.get_generation(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if row.get("status") not in ("failed", "error"):
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")
    
    # Rebuild payload from the stored generation row
    payload = {
        "prompt": row.get("prompt", ""),
        "model": row.get("model", "Gen"),
        "quality": row.get("quality", "Fast"),
        "aspect": row.get("aspect", "1:1"),
        "count": row.get("count", 4),
        "negative_prompt": row.get("negative_prompt", ""),
        "seed": row.get("seed"),
        "client_id": row.get("client_id"),
        "realm": row.get("realm") or "day",
    }
    await DB.update_generation(request_id, status="pending", error=None, last_error_text=None, result=None)
    async with job_lock:
        job_store[request_id] = {"status": "pending", "client_id": row.get("client_id"), "request_id": request_id}
    asyncio.create_task(_run_generation(request_id, GenerateRequest(**payload)))
    return {"status": "ok", "request_id": request_id, "queued": True}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    # Setting access_log=False removes the spam of "GET /history" and "GET /health" lines
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)
