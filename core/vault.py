import os
import logging
from io import BytesIO
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict
from urllib.parse import urlparse, unquote

import time
import boto3
import requests

# Global Client
_s3_client = None
_bucket_name = os.environ.get("R2_BUCKET", "imagenai")
_public_url = os.environ.get("R2_PUBLIC_URL", "https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev").rstrip("/")

def get_s3_client():
    global _s3_client
    if _s3_client is None:
        # Get from env or use the fallback from your main.py config
        account_id = os.environ.get("R2_ACCOUNT_ID", "c733aa6dbf847adf0949e4387eb6f15f")
        access_key = os.environ.get("R2_ACCESS_KEY")
        secret_key = os.environ.get("R2_SECRET_KEY")
        
        if not all([account_id, access_key, secret_key]):
            logging.warning("R2 Environment variables missing (Access/Secret Key)")
            return None
            
        _s3_client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
    return _s3_client

def build_batch_prefix(source: str, ts: Optional[datetime] = None, batch_id: Optional[str] = None) -> str:
    stamp_ts = ts or datetime.now(ZoneInfo("America/Los_Angeles"))
    stamp = stamp_ts.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y_%m_%d_%H%M%S")
    safe_source = source.strip().lower().replace(" ", "_")
    safe_batch_id = (batch_id or uuid4().hex[:8]).strip().lower()
    return f"vault/{stamp}_{safe_source}_{safe_batch_id}"

def build_batch_prefix_with_name(source: str, name: str, ts: Optional[datetime] = None) -> str:
    stamp_ts = ts or datetime.now(ZoneInfo("America/Los_Angeles"))
    stamp = stamp_ts.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y_%m_%d")
    safe_source = source.strip().lower().replace(" ", "_")
    safe_name = name.strip().replace("/", "_").replace(" ", "_")
    return f"vault/{stamp}/{safe_source}_{safe_name}"

def build_object_key(batch_prefix: str, file_name: str, ext: str = "jpg") -> str:
    safe_file_name = file_name.strip().replace("/", "_").replace(" ", "_")
    return f"{batch_prefix}/{safe_file_name}.{ext.lstrip('.')}"

def upload_image(image_url: str, file_name: str) -> str:
    s3 = get_s3_client()
    if s3 is None:
        raise RuntimeError(f"R2 not configured for upload: {file_name}")

    final_url = f"{_public_url}/{file_name.lstrip('/')}"
    try:
        s3.head_object(Bucket=_bucket_name, Key=file_name)
        logging.info("vaulted image already exists key=%s", file_name)
        return final_url
    except Exception:
        pass # Object does not exist, proceed to upload

    max_retries = 3
    last_exc = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(image_url, timeout=25)
            response.raise_for_status()
            s3.put_object(
                Bucket=_bucket_name,
                Key=file_name,
                Body=BytesIO(response.content),
                ContentType="image/jpeg",
            )
            logging.info("vaulted image uploaded key=%s", file_name)
            return final_url
        except Exception as exc:
            last_exc = exc
            logging.warning("Vault upload failed for %s (attempt %d/%d): %s", file_name, attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                time.sleep(2 * (1.5 ** attempt))
                
    logging.error("Failed to upload image %s after %d retries: %s", file_name, max_retries, last_exc)
    raise last_exc

def list_images(prefix: str = "vault/") -> List[Dict]:
    s3 = get_s3_client()
    if s3 is None: return []
    
    try:
        paginator = s3.get_paginator("list_objects_v2")
        items = []
        for page in paginator.paginate(Bucket=_bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key")
                if key and key.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    items.append({
                        "key": key,
                        "url": f"{_public_url}/{key.lstrip('/')}",
                        "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                    })
        items.sort(key=lambda x: x["key"], reverse=True)
        return items
    except Exception as exc:
        logging.error("Failed to list images: %s", exc)
        return []

def extract_key_from_url(image_url: str, public_url: str) -> Optional[str]:
    """Safely extract R2 object key from a public URL."""
    try:
        # Strip query params/fragments and unquote
        clean_url = image_url.split("?")[0].split("#")[0]
        url_parsed = urlparse(unquote(clean_url.strip()))
        public_parsed = urlparse(public_url.rstrip("/"))
        
        if url_parsed.netloc != public_parsed.netloc:
            # logging.warning(f"URL domain mismatch: {image_url}")
            return None
            
        # Extract path and strip the leading slash
        key = url_parsed.path.lstrip("/")
        if not key:
            return None
        return key
    except Exception as e:
        logging.error(f"Failed to extract key from {image_url}: {e}")
        return None

def delete_object(key: str, max_retries: int = 3) -> bool:
    """Delete object from R2 with exponential backoff retry."""
    s3 = get_s3_client()
    if s3 is None: return False
    
    last_exc = None
    for attempt in range(max_retries):
        try:
            s3.delete_object(Bucket=_bucket_name, Key=key)
            logging.info("R2 object deleted: key=%s", key)
            return True
        except s3.exceptions.NoSuchKey:
            logging.info("R2 object already deleted (404): key=%s", key)
            return True
        except Exception as exc:
            last_exc = exc
            wait_time = 1 * (2 ** attempt) # Simple exponential backoff
            logging.warning("R2 delete failed for %s (attempt %d/%d): %s - retrying in %.1fs", 
                            key, attempt+1, max_retries, exc, wait_time)
            if attempt < max_retries - 1:
                time.sleep(wait_time)
                
    logging.error("Failed to delete R2 key %s after %d retries: %s", key, max_retries, last_exc)
    return False

def delete_objects_batch(keys: List[str], max_retries: int = 2) -> Dict[str, bool]:
    """Delete multiple objects from R2 efficiently using DeleteObjects API."""
    s3 = get_s3_client()
    if s3 is None or not keys: 
        return {k: False for k in keys}
    
    results = {k: False for k in keys}
    # S3 allows up to 1000 objects per batch delete call
    for i in range(0, len(keys), 1000):
        batch = keys[i:i+1000]
        delete_request = {"Objects": [{"Key": k} for k in batch], "Quiet": True}
        
        for attempt in range(max_retries):
            try:
                response = s3.delete_objects(Bucket=_bucket_name, Delete=delete_request)
                # Mark successfully deleted
                for deleted in response.get("Deleted", []):
                    results[deleted["Key"]] = True
                # Log errors
                for error in response.get("Errors", []):
                    logging.warning(f"R2 batch delete error for {error['Key']}: {error['Message']}")
                    results[error["Key"]] = False
                break
            except Exception as exc:
                logging.warning(f"R2 batch delete failed (attempt {attempt+1}): {exc}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (2 ** attempt))
                    
    return results

# Compatibility Class
class R2Vault:
    def __init__(self, account_id=None, bucket_name=None, public_url=None, access_key=None, secret_key=None):
        self.account_id = account_id or os.environ.get("R2_ACCOUNT_ID")
        self.bucket_name = bucket_name or os.environ.get("R2_BUCKET", "imagenai")
        self.public_url = public_url or os.environ.get("R2_PUBLIC_URL", "")
        self.access_key = access_key or os.environ.get("R2_ACCESS_KEY")
        self.secret_key = secret_key or os.environ.get("R2_SECRET_KEY")

    def build_batch_prefix(self, *args, **kwargs): return build_batch_prefix(*args, **kwargs)
    def build_batch_prefix_with_name(self, *args, **kwargs): return build_batch_prefix_with_name(*args, **kwargs)
    def build_object_key(self, *args, **kwargs): return build_object_key(*args, **kwargs)
    def upload_image(self, *args, **kwargs): return upload_image(*args, **kwargs)
    def delete_object(self, *args, **kwargs): return delete_object(*args, **kwargs)
