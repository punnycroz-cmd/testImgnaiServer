import json
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict

import asyncpg

# Global Pool
_pool: Optional[asyncpg.Pool] = None

def _now():
    return datetime.now(timezone.utc)

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        
        # Initialize the pool with dictionary-like row access (Record objects)
        _pool = await asyncpg.create_pool(
            dsn=url,
            min_size=2,
            max_size=10,
            max_inactive_connection_lifetime=300.0
        )
    return _pool

async def init():
    """Initializes tables and indexes. Called on server startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create generations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
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
        
        # Create images table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_images (
                id uuid PRIMARY KEY,
                generation_id uuid NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
                task_uuid text NOT NULL,
                r2_url text NOT NULL,
                r2_key text NOT NULL,
                image_index integer NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        
        # Add is_hidden column if missing (safety)
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS is_hidden boolean NOT NULL DEFAULT false")
        
        # Create performance indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_realm_created ON generations (realm, created_at DESC, id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_images_generation_id ON generation_images (generation_id)")

async def create_generation(*, generation_id: str, request_id: str, client_id: Optional[str], realm: str, prompt: str, model: str, quality: str, aspect: str, seed: Optional[int], negative_prompt: Optional[str], count: int = 4):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO generations (
                id, request_id, client_id, realm, status, prompt, model, quality, aspect, seed, negative_prompt, count, updated_at
            ) VALUES ($1, $2, $3, $4, 'running', $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (request_id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                realm = EXCLUDED.realm,
                status = EXCLUDED.status,
                prompt = EXCLUDED.prompt,
                model = EXCLUDED.model,
                quality = EXCLUDED.quality,
                aspect = EXCLUDED.aspect,
                seed = EXCLUDED.seed,
                negative_prompt = EXCLUDED.negative_prompt,
                count = EXCLUDED.count,
                updated_at = EXCLUDED.updated_at
            """,
            uuid.UUID(generation_id), request_id, client_id, realm, prompt, model, quality, aspect, seed, negative_prompt, count, _now()
        )

async def update_generation(request_id: str, **fields: Any):
    if not fields:
        return
    
    sets = []
    values = []
    i = 1
    for key, val in fields.items():
        sets.append(f"{key} = ${i}")
        # asyncpg handles jsonb automatically, NO NEED to json.dumps
        values.append(val)
        i += 1
    
    sets.append(f"updated_at = ${i}")
    values.append(_now())
    i += 1
    
    values.append(request_id)
    query = f"UPDATE generations SET {', '.join(sets)} WHERE request_id = ${i}"
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(query, *values)

async def add_image(*, generation_id: str, task_uuid: str, r2_url: str, r2_key: str, image_index: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO generation_images (id, generation_id, task_uuid, r2_url, r2_key, image_index)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.uuid4(), uuid.UUID(generation_id), task_uuid, r2_url, r2_key, image_index
        )

async def get_generation(request_id: str) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM generations WHERE request_id = $1", request_id)
        if not row: return None
        # Convert to dict and handle UUID/Datetime serialization if needed
        data = dict(row)
        if data.get('id'): data['id'] = str(data['id'])
        return data

async def get_generation_images(generation_id: Any) -> List[Dict]:
    pool = await get_pool()
    # Handle cases where generation_id might be a string or a UUID object
    try:
        val = uuid.UUID(str(generation_id))
    except (ValueError, AttributeError):
        val = generation_id

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM generation_images WHERE generation_id = $1 ORDER BY image_index ASC", val)
        results = []
        for r in rows:
            d = dict(r)
            if d.get('id'): d['id'] = str(d['id'])
            if d.get('generation_id'): d['generation_id'] = str(d['generation_id'])
            results.append(d)
        return results

async def list_generations(limit: int = 20, offset: int = 0, realm: Optional[str] = None) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if realm:
            if realm.lower() == 'day':
                rows = await conn.fetch(
                    """
                    SELECT g.*
                    FROM generations g
                    WHERE g.is_hidden = false
                      AND g.status = 'done'
                      AND (LOWER(g.realm) = 'day' OR g.realm IS NULL)
                      AND EXISTS (SELECT 1 FROM generation_images i WHERE i.generation_id = g.id)
                    ORDER BY g.created_at DESC, g.id DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT g.*
                    FROM generations g
                    WHERE g.is_hidden = false
                      AND g.status = 'done'
                      AND LOWER(g.realm) = LOWER($1)
                      AND EXISTS (SELECT 1 FROM generation_images i WHERE i.generation_id = g.id)
                    ORDER BY g.created_at DESC, g.id DESC
                    LIMIT $2 OFFSET $3
                    """,
                    realm, limit, offset
                )
        else:
            rows = await conn.fetch(
                """
                SELECT g.*
                FROM generations g
                WHERE g.is_hidden = false
                  AND g.status = 'done'
                  AND EXISTS (SELECT 1 FROM generation_images i WHERE i.generation_id = g.id)
                ORDER BY g.created_at DESC, g.id DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        results = []
        for r in rows:
            d = dict(r)
            if d.get('id'): d['id'] = str(d['id'])
            results.append(d)
        return results

async def hide_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE generations SET is_hidden = true WHERE request_id = $1", request_id)

async def delete_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM generations WHERE request_id = $1", request_id)

# Compatibility Class (Temporary)
class Database:
    def __init__(self, *args, **kwargs):
        pass
    
    @property
    def pool(self):
        return _pool

    async def init(self): await init()
    async def create_generation(self, **kwargs): await create_generation(**kwargs)
    async def update_generation(self, rid, **kwargs): await update_generation(rid, **kwargs)
    async def add_image(self, **kwargs): await add_image(**kwargs)
    async def get_generation(self, rid): return await get_generation(rid)
    async def get_generation_images(self, gid): return await get_generation_images(gid)
    async def list_generations(self, **kwargs): return await list_generations(**kwargs)
    async def hide_generation(self, rid): await hide_generation(rid)
    async def delete_generation(self, rid): await delete_generation(rid)
