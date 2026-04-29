import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    url = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(url)
    rows = await conn.fetch("SELECT * FROM generations;")
    print(f"Total Rows in 'generations': {len(rows)}")
    for r in rows:
        print(f"ID: {r['request_id']}, Status: {r['status']}, Hidden: {r['is_hidden']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
