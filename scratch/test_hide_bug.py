
import asyncio
import os
import json
from core.db import DB

async def test_hide_logic():
    await DB.init(force=True)
    
    # 1. Create a generation with 4 images
    request_id = "test_batch_1"
    result = {
        "image_urls": ["url_0", "url_1", "url_2", "url_3"],
        "thumbnail_urls": ["t_0", "t_1", "t_2", "t_3"]
    }
    await DB.create_generation(
        request_id=request_id,
        count=4,
        result=result,
        status="done"
    )
    
    print("Created batch with 4 images: 0, 1, 2, 3")
    
    # 2. Hide image at index 2 (url_2)
    await DB.hide_image_index(request_id, 2)
    gen = await DB.get_generation(request_id)
    print(f"Hidden indices: {gen['hidden_indices']}")
    # Images status
    for img in gen['images']:
        print(f"Index {img['image_index']}: {img['r2_url']} - {img['status']}")
        
    # 3. Delete image at index 1 (url_1)
    print("\nDeleting image at index 1 (url_1)...")
    await DB.mark_image_deleting(request_id, "url_1")
    await DB.finalize_image_deletion(request_id, "url_1")
    
    gen = await DB.get_generation(request_id)
    print(f"Hidden indices still: {gen['hidden_indices']}")
    print("Current images:")
    for img in gen['images']:
        print(f"Index {img['image_index']}: {img['r2_url']} - {img['status']}")

    # Expected: url_2 should still be hidden.
    # Reality: url_2 is now at index 1. Index 2 is now url_3.
    # So url_3 will be marked hidden instead of url_2!

if __name__ == "__main__":
    asyncio.run(test_hide_logic())
