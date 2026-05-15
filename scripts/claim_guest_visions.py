import asyncio
import os
from core.db import DB

async def main():
    target_uid = "117792708564898340266"
    print(f"🚀 Starting Aether Identity Migration...")
    print(f"Targeting Account: {target_uid}")
    
    pool = await DB.get_pool()
    async with pool.acquire() as conn:
        # 1. Update generations table
        res1 = await conn.execute("UPDATE generations SET uid = $1 WHERE uid = 'uid_0'", target_uid)
        print(f"✅ Transferred records in 'generations' table: {res1}")
        
        # 2. Update image_summaries table
        res2 = await conn.execute("UPDATE image_summaries SET uid = $1 WHERE uid = 'uid_0'", target_uid)
        print(f"✅ Transferred records in 'image_summaries' table: {res2}")
        
        # 3. Update comments table (if any)
        res3 = await conn.execute("UPDATE comments SET uid = $1 WHERE uid = 'uid_0'", target_uid)
        print(f"✅ Transferred comments: {res3}")
        
        # 4. Update notifications table (if any)
        res4 = await conn.execute("UPDATE notifications SET actor_uid = $1 WHERE actor_uid = 'uid_0'", target_uid)
        print(f"✅ Transferred notifications: {res4}")

    print("\n✨ Migration Complete! All your guest visions now belong to your primary account.")
    await DB.close()

if __name__ == "__main__":
    asyncio.run(main())
