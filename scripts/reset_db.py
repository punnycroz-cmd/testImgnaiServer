import asyncio
import os
import asyncpg
import sys

async def reset_db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ Error: DATABASE_URL not set.")
        return

    print(f"⚠️  WARNING: This will DELETE ALL DATA in the database.")
    print(f"Target: {url.split('@')[-1]}") # Print host only for safety
    
    confirm = input("Are you absolutely sure? (type 'YES' to delete): ")
    if confirm != "YES":
        print("Aborted.")
        return

    try:
        conn = await asyncpg.connect(url)
        
        print("Dropping tables...")
        await conn.execute("DROP TABLE IF EXISTS generation_images CASCADE")
        await conn.execute("DROP TABLE IF EXISTS generations CASCADE")
        
        print("Creating tables...")
        # Generations table
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
        
        # Images table
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
        
        # Indexes
        print("Creating indexes...")
        await conn.execute("CREATE INDEX idx_generations_realm_created ON generations (realm, created_at DESC, id)")
        await conn.execute("CREATE INDEX idx_images_generation_id ON generation_images (generation_id)")
        
        await conn.close()
        print("✅ Database reset successfully. You are now starting with a clean slate!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        # Skip confirmation if --force is passed
        pass
    
    asyncio.run(reset_db())
