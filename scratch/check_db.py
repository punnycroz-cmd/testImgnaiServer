import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    url = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(url)
    rows = await conn.fetch("SELECT status, COUNT(*) FROM generations GROUP BY status;")
    for r in rows:
        print(f"Status: {r['status']}, Count: {r['count']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
