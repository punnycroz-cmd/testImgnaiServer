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
    # 1. Verify ownership OR if the image is public
    print(f"DEBUG: Share request for {payload.request_id} index {payload.image_index} from user {uid}")
    
    # Check if the image is public first
    public_gen = await DB.fetchrow(
        "SELECT uid, is_public, result FROM generations WHERE request_id = $1",
        payload.request_id
    )
    
    if not public_gen:
        print(f"DEBUG: Generation {payload.request_id} not found in DB at all")
        raise HTTPException(status_code=404, detail="Generation not found")

    is_owner = public_gen["uid"] == uid
    is_public = public_gen.get("is_public", False)
    
    if not is_owner and not is_public:
        print(f"DEBUG: Share failed - User {uid} is not owner and image is not public")
        raise HTTPException(status_code=403, detail="You do not have permission to share this private image")

    # 2. Get the R2 key from generation_images or fallback to result JSON
    image = await DB.fetchrow(
        "SELECT r2_key FROM generation_images WHERE generation_id = $1 AND image_index = $2", 
        payload.request_id, payload.image_index
    )
    
    r2_key = image["r2_key"] if image else None

    if not r2_key:
        print(f"DEBUG: Image not in generation_images, checking result JSON fallback")
        import json
        res = json.loads(public_gen["result"]) if isinstance(public_gen["result"], str) else public_gen["result"]
        urls = res.get("image_urls", [])
        if payload.image_index < len(urls):
            full_url = urls[payload.image_index]
            r2_key = full_url.split('/')[-1].split('?')[0]
            print(f"DEBUG: Extracted R2 key from fallback: {r2_key}")

    if not r2_key:
        print(f"DEBUG: Share failed - R2 key could not be resolved")
        raise HTTPException(status_code=404, detail="Image data missing")

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
