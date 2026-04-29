import asyncio
import json
from core.db import DB

async def check():
    await DB.init()
    pool = await DB.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT uid, request_id, prompt, status, created_at FROM generations ORDER BY created_at DESC LIMIT 10")
        print("Last 10 generations:")
        for r in rows:
            print(f"UID: {r['uid']} | Status: {r['status']} | Prompt: {r['prompt'][:30]}... | Created: {r['created_at']}")
            
        users = await conn.fetch("SELECT * FROM users")
        print("\nUsers in DB:")
        for u in users:
            print(f"UID: {u['uid']} | Name: {u['name']} | Email: {u['email']}")

if __name__ == "__main__":
    asyncio.run(check())
