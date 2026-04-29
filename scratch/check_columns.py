import asyncio
import json
from core.db import DB

async def check():
    await DB.init()
    pool = await DB.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM generations LIMIT 1")
        if row:
            print("Columns in generations table:")
            print(list(dict(row).keys()))
        else:
            print("No rows in generations table.")

if __name__ == "__main__":
    asyncio.run(check())
