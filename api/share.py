import os
import nanoid
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from core.db import DB
from core.auth import get_uid_from_session

router = APIRouter()

class ShareRequest(BaseModel):
    request_id: str
    image_index: int
    title: Optional[str] = None

def get_current_uid_required(request: Request):
    uid = get_uid_from_session(request)
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return uid

@router.post("/share")
async def create_share_link(payload: ShareRequest, uid: str = Depends(get_current_uid_required)):
    # 1. Verify ownership and get R2 key
    print(f"DEBUG: Share request for {payload.request_id} index {payload.image_index} from user {uid}")
    image = await DB.fetchrow(
        """
        SELECT r2_key FROM generation_images 
        WHERE generation_id = $1 AND image_index = $2 AND uid = $3
        """, 
        payload.request_id, payload.image_index, uid
    )
    
    r2_key = image["r2_key"] if image else None
    print(f"DEBUG: Initial R2 key lookup: {r2_key}")

    # Fallback: Check the main generations table (for older images)
    if not r2_key:
        gen = await DB.fetchrow(
            "SELECT result FROM generations WHERE request_id = $1 AND uid = $2",
            payload.request_id, uid
        )
        if gen:
            print(f"DEBUG: Found generation in fallback table")
            import json
            res = json.loads(gen["result"]) if isinstance(gen["result"], str) else gen["result"]
            urls = res.get("image_urls", [])
            print(f"DEBUG: Found {len(urls)} images in result")
            if payload.image_index < len(urls):
                full_url = urls[payload.image_index]
                r2_key = full_url.split('/')[-1].split('?')[0]
                print(f"DEBUG: Extracted R2 key from fallback: {r2_key}")

    if not r2_key:
        print(f"DEBUG: Share failed - image not found or no ownership")
        raise HTTPException(status_code=404, detail="Image not found or access denied")

    # 2. Generate shortcode (8 chars)
    shortcode = nanoid.generate(size=8)

    # 3. Store in DB
    await DB.execute(
        """
        INSERT INTO share_links (shortcode, request_id, image_index, r2_key, title, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        shortcode, payload.request_id, payload.image_index, 
        r2_key, payload.title, uid
    )

    # 4. Write to Cloudflare KV for edge resolution
    try:
        await _write_to_kv(shortcode, r2_key)
    except Exception as e:
        print(f"KV write failed: {e}")
        # We don't fail the whole request if KV write fails, 
        # as it can be retried or handled by a fallback
        pass

    return {
        "shortcode": shortcode,
        "share_url": f"https://aether-share-worker.sienfinla.workers.dev/s/{shortcode}"
    }

async def _write_to_kv(shortcode: str, r2_key: str):
    account_id = os.environ.get("CF_ACCOUNT_ID")
    kv_namespace = os.environ.get("CF_KV_NAMESPACE")
    api_token = os.environ.get("CF_API_TOKEN")
    
    if not all([account_id, kv_namespace, api_token]):
        print("Missing Cloudflare credentials for KV write")
        return

    url = (f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
           f"/storage/kv/namespaces/{kv_namespace}/values/{shortcode}")
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "text/plain"
    }
    
    # We use a synchronous requests call here for simplicity, 
    # but in a high-traffic app we'd use httpx
    resp = requests.put(url, headers=headers, data=r2_key, timeout=5)
    resp.raise_for_status()
