import asyncio
import json
import os
import sys

# Add the project root to sys.path so we can import core.db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import DB

BATCH_SIZE = 100

async def backfill():
    print("Starting image backfill...")
    await DB.init()
    
    offset = 0
    total_processed = 0
    
    while True:
        # Fetch generations that don't have images in generation_images yet
        rows = await DB.fetch(
            """
            SELECT g.request_id, g.uid, g.result 
            FROM generations g
            WHERE g.result IS NOT NULL 
              AND NOT EXISTS (
                SELECT 1 FROM generation_images i WHERE i.generation_id = g.request_id
              )
            ORDER BY g.created_at ASC 
            LIMIT $1 OFFSET $2
            """, 
            BATCH_SIZE, offset
        )
        
        if not rows:
            break
            
        print(f"Processing batch of {len(rows)} (offset {offset})...")
        
        for r in rows:
            req_id = r["request_id"]
            uid = r["uid"]
            
            # Handle both dict and string result
            result = r["result"]
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception as e:
                    print(f"Failed to parse result for {req_id}: {e}")
                    continue
            
            if not isinstance(result, dict):
                continue

            img_urls = result.get("image_urls", [])
            thumb_urls = result.get("thumbnail_urls", [])
            
            for idx, url in enumerate(img_urls):
                thumb_url = thumb_urls[idx] if idx < len(thumb_urls) else None
                try:
                    await DB.execute(
                        """
                        INSERT INTO generation_images 
                        (generation_id, uid, image_index, r2_key, thumbnail_r2_key, status)
                        VALUES ($1, $2, $3, $4, $5, 'active')
                        ON CONFLICT (generation_id, image_index) DO NOTHING
                        """,
                        req_id, uid, idx, url, thumb_url
                    )
                except Exception as e:
                    print(f"Failed to insert image {idx} for {req_id}: {e}")
            
            total_processed += 1
        
        offset += BATCH_SIZE
        
    print(f"Backfill complete. Processed {total_processed} generations.")
    await DB.close()

if __name__ == "__main__":
    asyncio.run(backfill())
