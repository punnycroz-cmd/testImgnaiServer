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
                "--no-download",
            ]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                clean = line.strip()
                if "404" in clean:
                    try:
                        os.remove(os.path.join(self.cookie_dir, "imgnai_cookies.json"))
                    except OSError:
                        pass

            process.wait()

            json_files = [f for f in os.listdir(self.output_dir) if f.endswith(".json") and not f.startswith("star_")]
            json_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.output_dir, x)), reverse=True)
            if not json_files:
                raise RuntimeError("Engine output missing")

            with open(os.path.join(self.output_dir, json_files[0]), "r") as f:
                data = json.load(f)

            vaulted_urls = []
            for idx, url in enumerate(data.get("image_urls", [])):
                cloud_url = self.vault.upload_image(url, f"vault/day_{req.client_id}_{idx}.jpg")
                vaulted_urls.append(cloud_url)

            return {"image_urls": vaulted_urls, "client_id": req.client_id, "model": req.model, "prompt": req.prompt}

