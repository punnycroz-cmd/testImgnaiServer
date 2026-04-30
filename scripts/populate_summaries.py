import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import DB

async def populate():
    print("Populating image summaries...")
    await DB.init()
    
    # Clear existing summaries
    await DB.execute("TRUNCATE TABLE image_summaries RESTART IDENTITY")
    
    # Aggregate data from generations and generation_images
    # We use image_id_seq from generations table as the primary cursor
    sql = """
        INSERT INTO image_summaries 
        (request_id, uid, realm, model, prompt, total_images, visible_images, first_thumbnail, is_hidden, is_public, image_id_seq, created_at, updated_at)
        SELECT 
            g.request_id, 
            g.uid, 
            g.realm, 
            g.model, 
            g.prompt,
            COUNT(i.image_id) as total_images,
            COUNT(i.image_id) FILTER (WHERE i.status = 'active') as visible_images,
            MIN(i.thumbnail_r2_key) FILTER (WHERE i.status = 'active' AND i.image_index = 0) as first_thumbnail,
            (COUNT(i.image_id) FILTER (WHERE i.status = 'active') = 0) as is_hidden,
            g.is_public,
            g.image_id_seq,
            g.created_at,
            g.updated_at
        FROM generations g
        LEFT JOIN generation_images i ON g.request_id = i.generation_id
        GROUP BY g.request_id, g.uid, g.realm, g.model, g.prompt, g.is_public, g.image_id_seq, g.created_at, g.updated_at
    """
    
    try:
        await DB.execute(sql)
        print("Summaries populated successfully.")
    except Exception as e:
        print(f"Failed to populate summaries: {e}")
        
    await DB.close()

if __name__ == "__main__":
    asyncio.run(populate())
