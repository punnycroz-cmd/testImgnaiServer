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
        
        print("Ensuring extensions...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        print("Dropping tables...")
        await conn.execute("DROP TABLE IF EXISTS generation_images CASCADE")
        await conn.execute("DROP TABLE IF EXISTS generations CASCADE")
        
        print("Creating table...")
        await conn.execute("""
            CREATE TABLE generations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id TEXT UNIQUE NOT NULL,
                client_id TEXT,
                realm TEXT CHECK (realm IN ('star', 'day')),
                prompt TEXT,
                negative_prompt TEXT,
                model TEXT,
                quality TEXT,
                aspect TEXT,
                seed BIGINT,
                count INTEGER,
                session_uuid TEXT,
                status TEXT CHECK (status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending',
                is_hidden BOOLEAN DEFAULT FALSE,
                result JSONB DEFAULT '{}',
                error TEXT,
                last_error_text TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        print("Creating indexes...")
        await conn.execute("CREATE INDEX idx_generations_realm_created ON generations (realm, created_at DESC)")
        await conn.execute("CREATE INDEX idx_generations_status ON generations (status)")
        
        await conn.close()
        print("✅ Database reset successfully!")
        print("\n✨ YOUR SYSTEM IS NOW 100% CLEAN AND FRESH ✨")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    asyncio.run(reset_db())
