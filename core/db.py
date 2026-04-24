import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        db_url = os.environ.get("DATABASE_URL")
        # Ensure it works with asyncpg (postgresql:// instead of postgres:// if needed, though asyncpg usually handles it)
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        _pool = await asyncpg.create_pool(
            dsn=db_url,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
    return _pool

def _now():
    return datetime.now()

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create tables if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id TEXT UNIQUE NOT NULL,
                client_id TEXT,
                realm TEXT,
                status TEXT NOT NULL,
                prompt TEXT,
                model TEXT,
                quality TEXT,
                aspect TEXT,
                seed BIGINT,
                negative_prompt TEXT,
                count INTEGER DEFAULT 1,
                session_uuid TEXT,
                task_uuids JSONB NOT NULL DEFAULT '[]'::jsonb,
                error TEXT,
                result JSONB,
                is_hidden BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_images (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                generation_id UUID REFERENCES generations(id) ON DELETE CASCADE,
                image_index INTEGER NOT NULL,
                r2_url TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_req_id ON generations(request_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_realm ON generations(realm);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_status ON generations(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_img_gen_id ON generation_images(generation_id);")

async def create_generation(data: Dict[str, Any]) -> str:
    pool = await get_pool()
    cols = []
    placeholders = []
    values = []
    for i, (k, v) in enumerate(data.items()):
        cols.append(k)
        placeholders.append(f"${i+1}")
        # asyncpg handles jsonb automatically
        values.append(v)
    
    query = f"INSERT INTO generations ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING request_id"
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *values)

async def update_generation(request_id: str, **fields: Any):
    if not fields:
        return
    
    sets = []
    values = []
    i = 1
    for key, val in fields.items():
        sets.append(f"{key} = ${i}")
        if key in ("task_uuids", "result") and not isinstance(val, (str, bytes)):
            values.append(json.dumps(val))
        else:
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

async def get_generation(request_id: str) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM generations WHERE request_id = $1", request_id)
        if row:
            d = dict(row)
            if d.get('id'): d['id'] = str(d['id'])
            return d
        return None

async def add_image(generation_request_id: str, index: int, url: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        gen_id = await conn.fetchval("SELECT id FROM generations WHERE request_id = $1", generation_request_id)
        if gen_id:
            await conn.execute(
                "INSERT INTO generation_images (generation_id, image_index, r2_url) VALUES ($1, $2, $3)",
                gen_id, index, url
            )

async def get_generation_images(generation_db_id: Any) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # generation_db_id could be a UUID object or a string
        rows = await conn.fetch("SELECT * FROM generation_images WHERE generation_id = $1 ORDER BY image_index ASC", generation_db_id)
        results = []
        for r in rows:
            d = dict(r)
            if d.get('id'): d['id'] = str(d['id'])
            if d.get('generation_id'): d['generation_id'] = str(d['generation_id'])
            results.append(d)
        return results

async def list_generations(limit: int = 20, offset: int = 0, realm: Optional[str] = None, before: Optional[str] = None) -> List[Dict]:
    pool = await get_pool()
    base_query = """
        SELECT g.*, 
               (SELECT json_agg(i.* ORDER BY i.image_index ASC) 
                FROM generation_images i 
                WHERE i.generation_id = g.id) as images
        FROM generations g
        WHERE g.is_hidden = false
          AND g.status = 'done'
          AND EXISTS (SELECT 1 FROM generation_images i WHERE i.generation_id = g.id)
    """
    
    async with pool.acquire() as conn:
        where_clauses = []
        params = []
        
        if realm:
            if realm.lower() == 'day':
                where_clauses.append("(LOWER(g.realm) = 'day' OR g.realm IS NULL)")
            else:
                params.append(realm)
                where_clauses.append(f"LOWER(g.realm) = LOWER(${len(params)})")
        
        if before:
            params.append(before)
            where_clauses.append(f"g.created_at < ${len(params)}")
            
        full_query = base_query
        if where_clauses:
            # base_query already has WHERE g.is_hidden = false etc.
            full_query += " AND " + " AND ".join(where_clauses)
            
        params.append(limit)
        limit_idx = len(params)
        
        # If using 'before' (cursor), we usually don't need 'offset'
        # but we keep it for backward compatibility
        params.append(offset)
        offset_idx = len(params)
        
        query = full_query + f" ORDER BY g.created_at DESC, g.id DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
        rows = await conn.fetch(query, *params)
            
        results = []
        for r in rows:
            d = dict(r)
            if d.get('id'): d['id'] = str(d['id'])
            if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
            if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
            if d.get('images'):
                for img in d['images']:
                    if img.get('id'): img['id'] = str(img['id'])
                    if img.get('generation_id'): img['generation_id'] = str(img['generation_id'])
            else:
                d['images'] = []
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

async def list_raw_generations(limit: int = 100, offset: int = 0, realm: Optional[str] = None, include_hidden: bool = True) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = []
        params = []
        if not include_hidden:
            where.append("is_hidden = false")
        if realm:
            if realm.lower() == "day":
                where.append("(LOWER(realm) = 'day' OR realm IS NULL)")
            else:
                params.append(realm)
                where.append(f"LOWER(realm) = LOWER(${len(params)})")
        
        query = "SELECT * FROM generations"
        if where:
            query += " WHERE " + " AND ".join(where)
        
        params.append(limit)
        params.append(offset)
        query += f" ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}"
        
        rows = await conn.fetch(query, *params)
        results = []
        for r in rows:
            d = dict(r)
            if d.get('id'): d['id'] = str(d['id'])
            results.append(d)
        return results

# Compatibility Layer
class DatabaseProxy:
    async def init(self): await init_db()
    async def get_generation(self, rid): return await get_generation(rid)
    async def get_generation_images(self, guid): return await get_generation_images(guid)
    async def update_generation(self, rid, **kwargs): await update_generation(rid, **kwargs)
    async def create_generation(self, data): return await create_generation(data)
    async def add_image(self, rid=None, idx=0, url="", **kwargs):
        # Handle various legacy parameter names used in different engines
        generation_id = rid or kwargs.get("generation_id") or kwargs.get("generation_request_id")
        index = idx or kwargs.get("image_index") or 0
        r2_url = url or kwargs.get("r2_url") or ""
        await add_image(generation_id, index, r2_url)
    async def list_generations(self, limit=20, offset=0, realm=None, before=None): return await list_generations(limit, offset, realm, before)
    async def hide_generation(self, rid): await hide_generation(rid)
    async def delete_generation(self, rid): await delete_generation(rid)
    async def delete_image(self, iid):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM generation_images WHERE id = $1", iid)

DB = DatabaseProxy()
