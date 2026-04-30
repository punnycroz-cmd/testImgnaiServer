import os
from typing import Optional
from itsdangerous import URLSafeSerializer
from fastapi import Request

SESSION_SECRET = os.environ.get("SESSION_SECRET", "aether-spiritual-fallback-secret-2024")
serializer = URLSafeSerializer(SESSION_SECRET, salt="aether-auth")

def get_uid_from_session(request: Request) -> Optional[str]:
    session_token = request.cookies.get("aether_session")
    if not session_token:
        return None
    try:
        return serializer.loads(session_token)
    except:
        return None
