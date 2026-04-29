import asyncio
import json
from core.db import list_generations, hide_generation, create_generation, init_db

async def test_hidden_batch():
    await init_db(force=False)
    
    # 1. Create a generation
    rid = "test-hidden-batch"
    result = {
        "image_urls": ["http://example.com/1.png"],
        "thumbnail_urls": ["http://example.com/1-t.png"]
    }
    await create_generation({
        "request_id": rid,
        "prompt": "test prompt",
        "result": result,
        "status": "done",
        "uid": "uid_0",
        "realm": "day"
    })
    
    # 2. Hide the batch
    await hide_generation(rid)
    print(f"Batch {rid} hidden.")
    
    # 3. List with include_hidden=False
    items = await list_generations(include_hidden=False)
    print("Items (include_hidden=False):", [i['request_id'] for i in items])
    
    # 4. List with include_hidden=True
    items = await list_generations(include_hidden=True)
    print("Items (include_hidden=True):", [i['request_id'] for i in items])

if __name__ == "__main__":
    asyncio.run(test_hidden_batch())
