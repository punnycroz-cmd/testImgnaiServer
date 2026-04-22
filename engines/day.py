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

    async def _vault_image(self, url, batch_prefix, task_uuid, idx, request_id):
        key = self.vault.build_object_key(batch_prefix, task_uuid, "jpg")
        cloud_url = await asyncio.to_thread(self.vault.upload_image, url, key)
        if self.db and request_id:
            await self.db.add_image(generation_id=request_id, task_uuid=task_uuid, r2_url=cloud_url, r2_key=key, image_index=idx)
        return cloud_url

    async def generate(self, req, request_id=None):
        async with self._lock:
            self.logger.info("day generate start prompt=%s", req.prompt[:60])
            
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
                
            self.logger.info("day execute: %s", " ".join(cmd))
            
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT
            )

            last_json_line = None
            full_output = []
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes: break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line:
                    full_output.append(line)
                    self.logger.info("day engine: %s", line)
                    try:
                        event = json.loads(line)
                        if self.db and request_id:
                            if event.get("event") == "session": await self.db.update_generation(request_id, session_uuid=event["session_uuid"])
                            if event.get("event") == "tasks": await self.db.update_generation(request_id, task_uuids=event["task_uuids"])
                        if line.startswith("{") and line.endswith("}"): last_json_line = line
                    except: pass

            rc = await process.wait()
            if rc != 0:
                self.logger.error("Day engine failed with exit code %s. Output: %s", rc, "\n".join(full_output))
                raise RuntimeError(f"Day failed (code {rc})")
                
            if not last_json_line: 
                raise RuntimeError("No JSON output from Day engine")
            
            data = json.loads(last_json_line)
            session_uuid, task_uuids, image_urls = data.get("session_uuid", "session"), data.get("task_uuids", []), data.get("image_urls", [])
            batch_prefix = self.vault.build_batch_prefix_with_name("day", session_uuid, ts=datetime.now())

            # Parallel Vaulting
            results = await asyncio.gather(*[
                self._vault_image(url, batch_prefix, task_uuids[i] if i < len(task_uuids) else f"{i+1:03d}", i, request_id)
                for i, url in enumerate(image_urls)
            ])
            
            return {"image_urls": [r for r in results if r], "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
