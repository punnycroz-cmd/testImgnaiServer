import argparse
import asyncio
import os
import sys
from typing import List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.db import Database
from core.vault import R2Vault


load_dotenv()


async def _main():
    parser = argparse.ArgumentParser(description="Remove orphan generation rows and matching R2 objects")
    parser.add_argument("--realm", default=None, help="Optional realm filter: day or star")
    parser.add_argument("--apply", action="store_true", help="Actually delete rows and objects")
    parser.add_argument("--limit", type=int, default=500, help="Max generations to inspect")
    args = parser.parse_args()

    db = Database()
    if not db.enabled:
        raise RuntimeError("DATABASE_URL is not set")
    await db.init()

    vault = R2Vault(
        account_id="c733aa6dbf847adf0949e4387eb6f15f",
        bucket_name="imagenai",
        public_url="https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev",
    )

    rows = await db.list_generation_rows(limit=args.limit, offset=0, realm=args.realm, include_hidden=True)
    all_keys = vault.list_object_keys("vault/")

    orphan_rows = []
    for row in rows:
        images = await db.get_generation_images(row["id"])
        if images:
            continue
        if row.get("status") != "done":
            continue
        orphan_rows.append(row)

    print(f"inspected={len(rows)} orphans={len(orphan_rows)} apply={args.apply} realm={args.realm!r}")

    for row in orphan_rows:
        request_id = row["request_id"]
        realm = row.get("realm") or "day"
        session_uuid = row.get("session_uuid")
        task_uuids = row.get("task_uuids") or []
        if isinstance(task_uuids, str):
            task_uuids = []
        matching_keys = []
        if session_uuid:
            needle = f"_{realm.lower()}_{session_uuid}/"
            matching_keys = [k for k in all_keys if needle in k]
        elif task_uuids:
            matching_keys = [k for k in all_keys if any(t in k for t in task_uuids)]

        print(f"\nrequest_id={request_id} realm={realm} session_uuid={session_uuid} matching_keys={len(matching_keys)}")
        if matching_keys[:5]:
            for key in matching_keys[:5]:
                print(f"  key={key}")
        if len(matching_keys) > 5:
            print(f"  ... +{len(matching_keys) - 5} more")

        if not args.apply:
            continue

        for key in matching_keys:
            vault.delete_object(key)
        await db.delete_generation(request_id)
        print(f"deleted request_id={request_id} r2_keys={len(matching_keys)}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to delete.")


if __name__ == "__main__":
    asyncio.run(_main())
