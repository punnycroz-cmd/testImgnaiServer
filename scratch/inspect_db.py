import asyncio
import os
import json
from core.db import DB

async def main():
    await DB.init()
    rid = '832b1b69-31bc-4d19-89aa-7dc694d11a46'
    r = await DB.get_generation(rid)
    if r:
        print("RESULT_START")
        print(json.dumps(r.get('result', {}), indent=2))
        print("RESULT_END")
    else:
        print("Not found")
    await DB.close()

if __name__ == "__main__":
    asyncio.run(main())
