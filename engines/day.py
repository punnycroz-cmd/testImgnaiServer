import json
import os
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

    def generate(self, req):
        with self._lock:
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
                if clean.startswith("{") and clean.endswith("}"):
                    last_json_line = clean

            rc = process.wait()
            if rc != 0:
                raise RuntimeError("Day engine failed")
            if not last_json_line:
                raise RuntimeError("Engine output missing")
            data = json.loads(last_json_line)

            return {"image_urls": data.get("image_urls", []), "client_id": req.client_id, "model": req.model, "prompt": req.prompt}
