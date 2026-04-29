import asyncio
import os
import json
from core.db import DB

async def test_deletion():
    await DB.init()
    
    # Create a dummy generation
    request_id = "test-deletion-id"
    await DB.create_generation(
        request_id=request_id,
        prompt="Test deletion",
        result={"image_urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]},
        status="done"
    )
    
    print("Created generation.")
    
    # Test single image deletion
    ok = await DB.delete_image(request_id, "https://example.com/image1.jpg?t=123")
    print(f"Delete single image: {ok}")
    
    row = await DB.get_generation(request_id)
    print(f"Remaining images: {row['result'].get('image_urls')}")
    print(f"Deleted images: {row['result'].get('deleted_image_urls')}")
    
    # Test batch deletion
    await DB.delete_generation(request_id)
    row = await DB.get_generation(request_id)
    print(f"Batch deleted: {row is None}")
    
    await DB.close()

if __name__ == "__main__":
    asyncio.run(test_deletion())
