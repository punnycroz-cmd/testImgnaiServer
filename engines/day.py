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
            
        # We only lock the PROCESS START to prevent login collisions
        async with self._lock:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT
            )

            last_json_line = None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes: break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line:
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
                            if event.get("event") == "tasks": await self.db.update_generation(request_id, task_uuids=event["task_uuids"])
                        if line.startswith("{") and line.endswith("}"): last_json_line = line
                    except: pass

            rc = await process.wait()
            if rc != 0: raise RuntimeError(f"Day failed (code {rc})")
            if not last_json_line: raise RuntimeError("Engine output missing")
            
            data = json.loads(last_json_line)
            session_uuid, task_uuids, image_urls = data.get("session_uuid", "session"), data.get("task_uuids", []), data.get("image_urls", [])

        # Released Engine Lock: Next job can start
        batch_prefix = self.vault.build_batch_prefix_with_name("day", session_uuid, ts=datetime.now())
        vaulted_urls = []
        for idx, url in enumerate(image_urls):
            task_uuid = task_uuids[idx] if idx < len(task_uuids) else f"{idx + 1:03d}"
            key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
            cloud_url = await asyncio.to_thread(self.vault.upload_image, url, key)
            vaulted_urls.append(cloud_url)
            if self.db and request_id:
                await self.db.add_image(generation_id=request_id, task_uuid=task_uuid, r2_url=cloud_url, r2_key=key, image_index=idx)

        return {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
