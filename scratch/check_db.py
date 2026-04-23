import asyncio
import os
from core.db import Database

async def check():
    db = Database()
    pool = await db.get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT realm, count(*) FROM generations GROUP BY realm")
            print("Realms:", await cur.fetchall())
            await cur.execute("SELECT count(*) FROM generations WHERE is_hidden = true")
            print("Hidden count:", await cur.fetchone())
            await cur.execute("SELECT count(*) FROM generations")
            print("Total count:", await cur.fetchone())
    await db.pool.close()

if __name__ == "__main__":
    asyncio.run(check())
