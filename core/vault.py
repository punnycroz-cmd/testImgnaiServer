import os
import logging
from io import BytesIO
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

import boto3
import requests

# Global Client
_s3_client = None
_bucket_name = os.environ.get("R2_BUCKET", "imgnai")
_public_url = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")

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
    stamp = stamp_ts.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y_%m_%d_%H%M%S")
    safe_source = source.strip().lower().replace(" ", "_")
    safe_name = name.strip().replace("/", "_").replace(" ", "_")
    return f"vault/{stamp}_{safe_source}_{safe_name}"

def build_object_key(batch_prefix: str, file_name: str, ext: str = "jpg") -> str:
    safe_file_name = file_name.strip().replace("/", "_").replace(" ", "_")
    return f"{batch_prefix}/{safe_file_name}.{ext.lstrip('.')}"

def upload_image(image_url: str, file_name: str) -> str:
    s3 = get_s3_client()
    if s3 is None:
        return image_url

    try:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
        s3.put_object(
            Bucket=_bucket_name,
            Key=file_name,
            Body=BytesIO(response.content),
            ContentType="image/jpeg",
        )
        return f"{_public_url}/{file_name.lstrip('/')}"
    except Exception as exc:
        logging.error("Failed to upload image %s: %s", file_name, exc)
        return image_url

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

def delete_object(key: str) -> bool:
    s3 = get_s3_client()
    if s3 is None: return False
    try:
        s3.delete_object(Bucket=_bucket_name, Key=key)
        return True
    except Exception as exc:
        logging.error("Failed to delete key %s: %s", key, exc)
        return False

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
