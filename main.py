import os
import json
import traceback
from typing import Optional

import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.models import GenerateDefaults
from core.vault import R2Vault
from engines.day import DayManager
from engines.star import GenerateRequest as StarGenerateRequest
from engines.star import StarManager

load_dotenv()

COOKIE_DIR = "cookie"
OUTPUT_DIR = "outputs"
os.makedirs(COOKIE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

R2_VAULT = R2Vault(
    account_id="c733aa6dbf847adf0949e4387eb6f15f",
    bucket_name="imagenai",
    public_url="https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev",
)


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = GenerateDefaults.MODEL
    count: int = GenerateDefaults.COUNT
    aspect: str = GenerateDefaults.ASPECT
    quality: str = GenerateDefaults.QUALITY
    seed: Optional[int] = None
    nsfw: bool = GenerateDefaults.NSFW
    negative_prompt: Optional[str] = GenerateDefaults.NEGATIVE_PROMPT
    client_id: Optional[str] = None
    realm: Optional[str] = GenerateDefaults.REALM


app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

day_mgr = DayManager(COOKIE_DIR, OUTPUT_DIR, R2_VAULT)
star_mgr = StarManager(COOKIE_DIR, OUTPUT_DIR, R2_VAULT)


@app.get("/")
async def index():
    return {"status": "Aether Server Online", "vault": R2_VAULT.bucket_name}


@app.get("/fetch-by-client-id/{client_id}")
async def fetch_by_id(client_id: str):
    for fn in os.listdir(OUTPUT_DIR):
        if fn.endswith(".json"):
            with open(os.path.join(OUTPUT_DIR, fn), "r") as f:
                d = json.load(f)
                if d.get("client_id") == client_id:
                    return d
    raise HTTPException(status_code=404)


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req.count = 4
        if req.nsfw:
            star_req = StarGenerateRequest(**req.model_dump())
            return await star_mgr.generate(star_req)
        return await anyio.to_thread.run_sync(day_mgr.generate, req)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
