import asyncio
import os
import asyncpg
import sys
import boto3
import logging
from dotenv import load_dotenv

load_dotenv()

async def reset_db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ Error: DATABASE_URL not set.")
        return

    print(f"⚠️  WARNING: This will DELETE ALL DATA in the database AND all images in R2 Vault.")
    print(f"DB Target: {url.split('@')[-1]}")
    
    confirm = input("Are you absolutely sure? (type 'YES' to delete everything): ")
    if confirm != "YES":
        print("Aborted.")
        return

    # --- Step 1: Purge R2 ---
    try:
        # Get from env or fallback to values from main.py
        bucket = os.environ.get("R2_BUCKET", "imagenai")
        account_id = os.environ.get("R2_ACCOUNT_ID", "c733aa6dbf847adf0949e4387eb6f15f")
        access_key = os.environ.get("R2_ACCESS_KEY")
        secret_key = os.environ.get("R2_SECRET_KEY")

        if all([account_id, access_key, secret_key]):
            print(f"🧹 Purging R2 Bucket: {bucket} (Account: {account_id[:8]}...)")
            s3 = boto3.client(
                service_name="s3",
                endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
            
            # List and delete everything with prefix 'vault/'
            paginator = s3.get_paginator('list_objects_v2')
            delete_count = 0
            for page in paginator.paginate(Bucket=bucket, Prefix='vault/'):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        s3.delete_object(Bucket=bucket, Key=obj['Key'])
                        delete_count += 1
            print(f"✅ Deleted {delete_count} objects from R2.")
        else:
            print("⚠️ Skipping R2 Purge: Environment variables not set.")
    except Exception as e:
        print(f"❌ R2 Purge Error: {e}")

    # --- Step 2: Reset DB ---
    try:
        conn = await asyncpg.connect(url)
        
        print("Dropping tables...")
        await conn.execute("DROP TABLE IF EXISTS generation_images CASCADE")
        await conn.execute("DROP TABLE IF EXISTS generations CASCADE")
        
        print("Creating tables...")
        # (Same table creation logic as before)
        await conn.execute("""
            CREATE TABLE generations (
                id uuid PRIMARY KEY,
                request_id text UNIQUE NOT NULL,
                client_id text,
                realm text NOT NULL,
                status text NOT NULL,
                prompt text NOT NULL,
                model text,
                quality text,
                aspect text,
                seed bigint,
                negative_prompt text,
                count integer NOT NULL DEFAULT 4,
                session_uuid text,
                task_uuids jsonb NOT NULL DEFAULT '[]'::jsonb,
                error text,
                result jsonb,
                is_hidden boolean NOT NULL DEFAULT false,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        
        await conn.execute("""
            CREATE TABLE generation_images (
                id uuid PRIMARY KEY,
                generation_id uuid NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
                task_uuid text NOT NULL,
                r2_url text NOT NULL,
                r2_key text NOT NULL,
                image_index integer NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        
        print("Creating indexes...")
        await conn.execute("CREATE INDEX idx_generations_realm_created ON generations (realm, created_at DESC, id)")
        await conn.execute("CREATE INDEX idx_images_generation_id ON generation_images (generation_id)")
        
        await conn.close()
        print("✅ Database reset successfully!")
        print("\n✨ YOUR SYSTEM IS NOW 100% CLEAN AND FRESH ✨")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    asyncio.run(reset_db())
