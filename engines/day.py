import json
import os
import logging
import subprocess
import sys
import threading

from core.vault import R2Vault


class DayManager:
    def __init__(self, cookie_dir: str, output_dir: str, vault: R2Vault):
        self._lock = threading.Lock()
        self.cookie_dir = cookie_dir
        self.output_dir = output_dir
        self.vault = vault
        self.logger = logging.getLogger("aether.day")

    def generate(self, req):
        with self._lock:
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

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            last_json_line = None
            for line in process.stdout:
                clean = line.strip()
                if clean:
                    self.logger.info("day engine: %s", clean)
                if clean.startswith("{") and clean.endswith("}"):
                    last_json_line = clean

            rc = process.wait()
            if rc != 0:
                raise RuntimeError("Day engine failed")
            if not last_json_line:
                raise RuntimeError("Engine output missing")
            data = json.loads(last_json_line)
            vaulted_urls = []
            image_urls = data.get("image_urls", [])
            self.logger.info("day generated %s urls, vaulting", len(image_urls))
            for idx, url in enumerate(image_urls):
                cloud_url = self.vault.upload_image(url, f"vault/day_{req.client_id}_{idx}.jpg")
                vaulted_urls.append(cloud_url)
                self.logger.info("day image vaulted idx=%s url=%s", idx, cloud_url)
            self.logger.info("day generate done images=%s", len(vaulted_urls))
            return {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
