from typing import Optional

from pydantic import BaseModel

from config.models import GenerateDefaults


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

