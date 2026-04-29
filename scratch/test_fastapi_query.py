import asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

app = FastAPI()

@app.post("/test")
async def test_endpoint(request: Request):
    idx = request.query_params.get("index")
    body_idx = None
    try:
        body = await request.json()
        body_idx = body.get("index")
    except: pass
    
    return {"query_idx": idx, "body_idx": body_idx}

client = TestClient(app)

def run_tests():
    # Test 1: Query param only
    r1 = client.post("/test?index=0")
    print("Test 1 (Query param only):", r1.json())
    
    # Test 2: Body only
    r2 = client.post("/test", json={"index": 0})
    print("Test 2 (Body only):", r2.json())

if __name__ == "__main__":
    run_tests()
