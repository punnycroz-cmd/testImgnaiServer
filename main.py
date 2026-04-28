import asyncio
from typing import Optional
import logging
import os
import uuid
import traceback
import json
import hashlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from config.schemas import GenerateRequest
from core.db import DB
from core.vault import R2Vault
from engines.day import DayManager
from engines.star import GenerateRequest as StarGenerateRequest
from engines.star import StarManager

# --- Logging Cleanup ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Ignore these high-frequency polling endpoints in the console
        msg = record.getMessage()
        return "/job-status/" not in msg and "/history" not in msg

# Apply filter to uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

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
    await DB.init(force=False)
    yield
    # Close DB pool
    await DB.close()

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


async def _extract_image_url(request: Request, url: Optional[str]) -> str:
    """Accept image URL from query string, fallback header, then JSON body."""
    candidate = (url or "").strip()
    if candidate:
        return candidate

    candidate = (request.headers.get("X-Image-Url") or "").strip()
    if candidate:
        return candidate

    try:
        body = await request.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        candidate = str(body.get("url") or "").strip()
        if candidate:
            return candidate

    raise HTTPException(status_code=422, detail="Missing image url")


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


async def _cleanup_r2_image_task(request_id: str, url: str):
    """Background task to delete from R2 and then finalize DB state."""
    try:
        from core.vault import _public_url, delete_object
        if url.startswith(_public_url):
            key = url[len(_public_url):].lstrip("/")
            # Attempt R2 deletion with retries (logic inside delete_object)
            ok = delete_object(key)
            if not ok:
                logger.error(f"Failed R2 cleanup for {url}, will NOT finalize DB deletion.")
                return
        
        # Once storage is clean, finalize the record
        await DB.finalize_image_deletion(request_id, url)
        logger.info(f"Finalized deletion for {url} in {request_id}")
    except Exception as e:
        logger.error(f"Error in R2 cleanup task for {url}: {e}")


async def _run_generation(job_id: str, req: GenerateRequest):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            logger.info("[>] Job Start: %s (Attempt %d/%d)", job_id[:8], attempt + 1, max_retries)
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
            logger.info("[!] Job: %s finished successfully", job_id[:8])
            return # Success!
            
        except Exception as exc:
            logger.warning("[?] Job Attempt %d failed for %s: %s", attempt + 1, job_id[:8], exc)
            await asyncio.sleep(5) # Cooldown before next attempt
            if attempt == max_retries - 1:
                # Final failure
                logger.exception("job totally failed request_id=%s", job_id)
                async with job_lock:
                    job_store[job_id] = {"status": "error", "error": str(exc), "client_id": req.client_id, "request_id": job_id}
                await DB.update_generation(job_id, status="failed", error=str(exc), last_error_text=str(exc))
            else:
                # Wait a bit before retrying
                await asyncio.sleep(2)



@app.get("/job-status/{job_id}")
async def get_job_status(request: Request, response: Response, job_id: str):
    res = await DB.get_generation(job_id)
    if not res:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Option 4: ETag for job status
    # Note: We use default=str to handle datetime objects in the record
    content_str = json.dumps(res, sort_keys=True, default=str)
    etag = f'W/"{hashlib.md5(content_str.encode()).hexdigest()}"'
    
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
        
    response.headers["ETag"] = etag
    return res

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
async def get_history(request: Request, response: Response, limit: int = 20, realm: Optional[str] = None, before: Optional[str] = None, uid: str = "uid_0", include_hidden: bool = False):
    # Fallback for proxies that strip query params
    cursor = before or request.headers.get("X-Debug-Cursor")
    b_id = None
    if cursor and cursor != "null" and cursor != "undefined":
        try: b_id = int(float(cursor))
        except: pass

    page_items = await DB.list_generations(limit=limit, realm=realm, before_id=b_id, uid=uid, include_hidden=include_hidden)
    
    result = {
        "items": page_items,
        "limit": limit,
        "has_more": len(page_items) == limit,
        "next_cursor": page_items[-1]["image_id"] if page_items else None
    }

    # Option 4: ETag Generation
    # Note: We use default=str to handle datetime objects in the record
    content_str = json.dumps(result, sort_keys=True, default=str)
    etag = f'W/"{hashlib.md5(content_str.encode()).hexdigest()}"'
    
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
        
    response.headers["ETag"] = etag
    return result


@app.get("/diag/db")
async def diag_db():
    pool = await DB.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT uid, image_id, request_id, status, realm, is_hidden, created_at FROM generations ORDER BY image_id DESC LIMIT 50")
        return [dict(r) for r in rows]

@app.post("/history/batch/{request_id}/hide")
async def hide_batch(request_id: str):
    await DB.hide_generation(request_id)
    return {"status": "ok", "hidden": request_id}


@app.post("/history/batch/{request_id}/show")
async def show_batch(request_id: str):
    await DB.show_generation(request_id)
    return {"status": "ok", "shown": request_id}


@app.delete("/history/batch/{request_id}")
async def delete_batch(request_id: str):
    # 1. Database removal (returns result for R2 cleanup)
    result_data = await DB.delete_generation(request_id)
    
    # 2. In-memory cleanup
    async with job_lock:
        if request_id in job_store:
            del job_store[request_id]
        if request_id in cancelled_jobs:
            cancelled_jobs.remove(request_id)

    # 3. R2 Cleanup (Improved Batch Deletion)
    if result_data:
        from core.vault import _public_url, extract_key_from_url, delete_objects_batch
        res_obj = result_data.get("result") or {}
        # Collect all unique URLs from different lists
        all_urls = set()
        for key in ["image_urls", "hidden_image_urls", "deleted_image_urls"]:
            all_urls.update(res_obj.get(key) or [])
        
        # Extract keys for batch deletion
        keys_to_delete = []
        for url in all_urls:
            key = extract_key_from_url(url, _public_url)
            if key:
                keys_to_delete.append(key)
        
        if keys_to_delete:
            # We don't await because it's a synchronous function called in a thread inside if needed,
            # but for now we just call it.
            delete_objects_batch(keys_to_delete)

    return {"status": "ok", "deleted": request_id}


@app.post("/history/image/{request_id}/hide")
async def hide_image(request_id: str, request: Request, url: Optional[str] = Query(None)):
    # 🔍 Nuclear search for index (Query -> Header -> Body)
    idx = request.query_params.get("index") or request.headers.get("X-Image-Index")
    
    if idx is None:
        try:
            body = await request.json()
            idx = body.get("index")
        except: pass

    if idx is not None:
        try:
            index = int(idx)
            ok = await DB.hide_image_index(request_id, index)
            return {"status": "ok" if ok else "error", "hidden": ok, "request_id": request_id, "index": index}
        except Exception as e:
            logger.error(f"Hide image error: {str(e)}\n{traceback.format_exc()}")
            return {"status": "error", "detail": str(e), "request_id": request_id}

    # Fallback to URL-based logic
    resolved_url = await _extract_image_url(request, url)
    ok = await DB.hide_image(request_id, resolved_url)
    return {"status": "ok" if ok else "error", "hidden": ok, "request_id": request_id, "url": resolved_url}


@app.post("/history/image/{request_id}/show")
async def show_image(request_id: str, request: Request, url: Optional[str] = Query(None)):
    # 🔍 Nuclear search
    idx = request.query_params.get("index") or request.headers.get("X-Image-Index")
    if idx is None:
        try:
            body = await request.json()
            idx = body.get("index")
        except: pass

    if idx is not None:
        try:
            index = int(idx)
            ok = await DB.show_image_index(request_id, index)
            return {"status": "ok" if ok else "error", "shown": ok, "request_id": request_id, "index": index}
        except Exception as e:
            logger.error(f"Show image error: {str(e)}\n{traceback.format_exc()}")
            return {"status": "error", "detail": str(e), "request_id": request_id}
        
    resolved_url = await _extract_image_url(request, url)
    ok = await DB.show_image(request_id, resolved_url)
    return {"status": "ok" if ok else "error", "shown": ok, "request_id": request_id, "url": resolved_url}


@app.delete("/history/image/{request_id}")
async def delete_image(request: Request, request_id: str, url: Optional[str] = None):
    resolved_url = await _extract_image_url(request, url)
    
    # 1. Mark as 'deleting' in DB (immediate)
    ok = await DB.mark_image_deleting(request_id, resolved_url)
    
    if ok:
        # 2. Spawn background task for R2 cleanup and finalization
        asyncio.create_task(_cleanup_r2_image_task(request_id, resolved_url))

    return {"status": "ok" if ok else "error", "deleted": ok, "request_id": request_id, "url": resolved_url}


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
