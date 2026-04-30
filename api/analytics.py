from fastapi import APIRouter, Request
from core.db import DB

router = APIRouter()

@router.post("/track_click")
async def track_click(request: Request):
    try:
        data = await request.json()
        shortcode = data.get("shortcode")
        ip_hash = data.get("ip_hash")
        user_agent = data.get("user_agent")
        
        if not shortcode or not ip_hash:
            return {"status": "ignored"}
            
        await DB.execute(
            """
            INSERT INTO share_clicks (shortcode, ip_hash, user_agent)
            VALUES ($1, $2, $3)
            """,
            shortcode, ip_hash, user_agent
        )
        return {"status": "ok"}
    except Exception as e:
        print(f"Failed to track click: {e}")
        return {"status": "error"}
