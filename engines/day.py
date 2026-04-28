import json
import os
import logging
import subprocess
import sys
import asyncio
from datetime import datetime

from core.vault import R2Vault


class DayManager:
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault, db=None, cancelled_jobs=None):
        self._lock = asyncio.Lock()
        self.cookie_dir = cookie_dir
        self.output_dir = output_dir
        self.vault = vault
        self.db = db
        self.cancelled_jobs = cancelled_jobs or set()
        self.logger = logging.getLogger("aether.day")

    async def generate(self, req, request_id=None):
        if request_id and request_id in self.cancelled_jobs:
            self.logger.info("day generate cancelled before start: %s", request_id)
            return None

        # self.logger.info("[>] Day Pulse: %s", req.prompt[:30] + "...")
        
        # Using absolute path for stability on Replit
        script_path = os.path.join(os.getcwd(), "day_api.py")
        cmd = [
            sys.executable, script_path, 
            "--prompt", str(req.prompt), 
            "--model", str(req.model), 
            "--count", str(req.count),
            "--aspect", str(req.aspect), 
            "--quality", str(req.quality),
            "--skip-login-prompt", 
            "--confirm-payload",
        ]
        if req.negative_prompt:
            cmd.extend(["--negative-prompt", str(req.negative_prompt)])
        if req.seed is not None:
            cmd.extend(["--seed", str(req.seed)])
            
        # We only lock the PROCESS START to prevent login collisions
        async with self._lock:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT
            )

            last_json_line = None
            tail = []
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes: break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line:
                    tail.append(line)
                    if len(tail) > 8:
                        tail.pop(0)
                    # Silenced engine logs
                    if request_id and request_id in self.cancelled_jobs:
                        self.logger.warning("day job cancelled during execution, terminating: %s", request_id)
                        try: process.terminate()
                        except: pass
                        break
                    try:
                        event = json.loads(line)
                        if self.db and request_id:
                            if event.get("event") == "session": await self.db.update_generation(request_id, session_uuid=event["session_uuid"])

                        if line.startswith("{") and line.endswith("}"): last_json_line = line
                    except: pass

            rc = await process.wait()
            if rc != 0:
                reason = " | ".join(tail[-4:]) if tail else "no output"
                raise RuntimeError(f"Day failed (code {rc}): {reason}")
            if not last_json_line: raise RuntimeError("Engine output missing")
            
            data = json.loads(last_json_line)
            session_uuid, task_uuids, image_urls = data.get("session_uuid", "session"), data.get("task_uuids", []), data.get("image_urls", [])

        # Released Engine Lock: Next job can start
        batch_prefix = self.vault.build_batch_prefix_with_name("day", session_uuid, ts=datetime.now())
        
        async def safe_upload(url, idx):
            try:
                task_uuid = task_uuids[idx] if idx < len(task_uuids) else f"{idx + 1:03d}"
                key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
                from core.vault import upload_image_with_thumbnail
                result = await asyncio.to_thread(upload_image_with_thumbnail, url, key)
                return {
                    "r2_url": result["full_url"],
                    "thumbnail_url": result["thumbnail_url"]
                }
            except Exception as e:
                self.logger.error("Failed to vault image %d for job %s: %s", idx, request_id, e)
                return None

        vault_tasks = [safe_upload(url, i) for i, url in enumerate(image_urls)]
        results = await asyncio.gather(*vault_tasks)
        vaulted_objects = [o for o in results if o]

        return {
            "image_urls": [o["r2_url"] for o in vaulted_objects], 
            "thumbnail_urls": [o["thumbnail_url"] for o in vaulted_objects],
            "client_id": req.client_id, 
            "model": req.model, 
            "prompt": req.prompt
        }
