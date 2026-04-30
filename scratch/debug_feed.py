import asyncio
import os
import json
from core.db import DB

async def main():
    await DB.init()
    print("--- POSTS PREVIEW ---")
    rows = await DB.list_posts(limit=10)
    for r in rows:
        print(f"Post ID: {r.get('id')}")
        print(f"Content: {r.get('content')[:30]}...")
        print(f"Preview URL: {r.get('preview_url')}")
        print(f"Request ID: {r.get('request_id')}")
        print("-" * 20)
    
    print("\n--- RECENT PUBLIC GENERATIONS ---")
    # Search for items that might be in Discovery but missing in Vault
    async with (await DB.get_pool()).acquire() as conn:
        rows = await conn.fetch("SELECT request_id, uid, is_public, is_hidden FROM generations WHERE is_public = TRUE ORDER BY id DESC LIMIT 10")
        for r in rows:
            print(dict(r))
            
    await DB.close()

if __name__ == "__main__":
    asyncio.run(main())
