import os
import logging
from io import BytesIO
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Optional

import boto3
import requests


class R2Vault:
    def __init__(
        self,
        account_id: str,
        bucket_name: str,
        public_url: str,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.account_id = account_id
        self.bucket_name = bucket_name
        self.public_url = public_url.rstrip("/")
        self.access_key = access_key or os.environ.get("R2_ACCESS_KEY")
        self.secret_key = secret_key or os.environ.get("R2_SECRET_KEY")
        self.logger = logging.getLogger("aether.vault")

    def build_batch_prefix(self, source: str, ts: Optional[datetime] = None, batch_id: Optional[str] = None) -> str:
        stamp_ts = ts or datetime.now(ZoneInfo("America/Los_Angeles"))
        stamp = stamp_ts.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y_%m_%d_%H%M%S")
        safe_source = source.strip().lower().replace(" ", "_")
        safe_batch_id = (batch_id or uuid4().hex[:8]).strip().lower()
        return f"vault/{stamp}_{safe_source}_{safe_batch_id}"

    def build_object_key(self, batch_prefix: str, index: int, ext: str = "jpg") -> str:
        return f"{batch_prefix}/{index + 1:03d}.{ext.lstrip('.')}"

    def upload_image(self, image_url: str, file_name: str) -> str:
        if not self.access_key or "PASTE_YOUR" in self.access_key:
            self.logger.warning("R2 not configured, returning source url for %s", file_name)
            return image_url

        s3 = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
        )

        try:
            response = requests.get(image_url, timeout=20)
            response.raise_for_status()
            s3.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=BytesIO(response.content),
                ContentType="image/jpeg",
            )
            final_url = f"{self.public_url}/{file_name.lstrip('/')}"
            self.logger.info("uploaded image %s -> %s", image_url[:80], final_url)
            return final_url
        except Exception as exc:
            self.logger.exception("failed to upload image %s: %s", file_name, exc)
            return image_url
