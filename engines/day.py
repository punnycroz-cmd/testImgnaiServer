import json
import os
import logging
import asyncio
import sys
from datetime import datetime

from core.vault import R2Vault


class DayManager:
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault, db=None):
        self._lock = asyncio.Lock()
        self.cookie_dir = cookie_dir
        self.output_dir = output_dir
        self.vault = vault
        self.db = db
        self.logger = logging.getLogger("aether.day")

    async def generate(self, req, request_id=None):
        async with self._lock:
            self.logger.info("day generate start prompt=%s quality=%s model=%s", req.prompt[:60], req.quality, req.model)
            cmd = [
                sys.executable,
                "day_api.py",
                "--prompt",
                req.prompt,
                "--model",
                req.model,
                "--count",
                str(req.count),
                "--aspect",
                req.aspect,
                "--quality",
                req.quality,
                "--negative-prompt",
                req.negative_prompt,
                "--skip-login-prompt",
                "--confirm-payload",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            last_json_line = None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line:
                    self.logger.info("day engine: %s", line)
                    try:
                        event = json.loads(line)
                        if self.db and request_id and event.get("event") == "session" and event.get("session_uuid"):
                            await self.db.update_generation(request_id, session_uuid=event["session_uuid"])
                        if self.db and request_id and event.get("event") == "tasks" and event.get("task_uuids") is not None:
                            await self.db.update_generation(request_id, task_uuids=event["task_uuids"])
                        
                        if line.startswith("{") and line.endswith("}"):
                            last_json_line = line
                    except Exception:
                        pass

            rc = await process.wait()
            if rc != 0:
                raise RuntimeError("Day engine failed")
            if not last_json_line:
                raise RuntimeError("Engine output missing")
            
            data = json.loads(last_json_line)
            session_uuid = data.get("session_uuid") or "session"
            task_uuids = data.get("task_uuids", [])
            image_urls = data.get("image_urls", [])
            
            self.logger.info("day session_uuid=%s", session_uuid)
            self.logger.info("day task_uuids=%s", task_uuids)
            
            if self.db and request_id:
                await self.db.update_generation(request_id, session_uuid=session_uuid, task_uuids=task_uuids)
            
            vaulted_urls = []
            self.logger.info("day generated %s urls, vaulting", len(image_urls))
            run_stamp = datetime.now()
            batch_prefix = self.vault.build_batch_prefix_with_name("day", session_uuid, ts=run_stamp)
            
            for idx, url in enumerate(image_urls):
                task_uuid = task_uuids[idx] if idx < len(task_uuids) else f"{idx + 1:03d}"
                key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
                cloud_url = await asyncio.to_thread(self.vault.upload_image, url, key)
                vaulted_urls.append(cloud_url)
                
                if self.db and request_id:
                    await self.db.add_image(
                        generation_id=request_id,
                        task_uuid=task_uuid,
                        r2_url=cloud_url,
                        r2_key=key,
                        image_index=idx,
                    )
                self.logger.info("day image vaulted task=%s url=%s", task_uuid[:8] if isinstance(task_uuid, str) else task_uuid, cloud_url)
            
            self.logger.info("day generate done images=%s", len(vaulted_urls))
            return {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
