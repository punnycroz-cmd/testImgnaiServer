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
        # Drop old confusing table
        await conn.execute("DROP TABLE IF EXISTS generation_images CASCADE;")
        
        # Create Master History Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id TEXT UNIQUE NOT NULL,
                client_id TEXT,
                realm TEXT,
                prompt TEXT,
                negative_prompt TEXT,
                model TEXT,
                quality TEXT,
                aspect TEXT,
                seed BIGINT,
                count INTEGER DEFAULT 1,
                session_uuid TEXT,
                task_uuids JSONB NOT NULL DEFAULT '[]'::jsonb,
                status TEXT NOT NULL,
                is_hidden BOOLEAN DEFAULT FALSE,
                result JSONB DEFAULT '{}',
                error TEXT,
                last_error_text TEXT,
                attempts INTEGER DEFAULT 0,
                error_type TEXT,
                last_error TEXT,
                max_retries INTEGER DEFAULT 3,
                retry_payload JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Critical Indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_realm_created ON generations (realm, created_at DESC);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_status ON generations (status);")


async def create_generation(data: Dict[str, Any]) -> str:
    pool = await get_pool()
    cols = []
    placeholders = []
    values = []
    for i, (k, v) in enumerate(data.items()):
        cols.append(k)
        placeholders.append(f"${i+1}")
        if k in ("task_uuids", "result", "retry_payload") and not isinstance(v, (str, bytes)):
            values.append(json.dumps(v))
        else:
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
        if key in ("task_uuids", "result", "retry_payload") and not isinstance(val, (str, bytes)):
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
            
            result_obj = d.get("result") or {}
            if isinstance(result_obj, str):
                try: result_obj = json.loads(result_obj)
                except: result_obj = {}
            
            image_urls = result_obj.get("image_urls", [])
            d['images'] = [{"r2_url": url} for url in image_urls]
            return d
        return None



async def list_generations(limit: int = 20, offset: int = 0, realm: Optional[str] = None, before: Optional[str] = None) -> List[Dict]:
    pool = await get_pool()
    query = """
        SELECT 
            request_id, client_id, realm, prompt, model, 
            quality, aspect, count, session_uuid, result, error, 
            created_at, updated_at
        FROM generations
        WHERE is_hidden = FALSE AND status = 'done'
    """
    
    async with pool.acquire() as conn:
        where_clauses = []
        params = []
        
        if realm:
            params.append(realm)
            where_clauses.append(f"realm = ${len(params)}")
            
        if before:
            params.append(before)
            where_clauses.append(f"created_at < ${len(params)}")
            
        if where_clauses:
            query += " AND " + " AND ".join(where_clauses)
            
        params.append(limit)
        limit_idx = len(params)
        params.append(offset)
        offset_idx = len(params)
        
        query += f" ORDER BY created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
        rows = await conn.fetch(query, *params)
            
        results = []
        for r in rows:
            d = dict(r)
            if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
            if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
            
            result_obj = d.get("result") or {}
            if isinstance(result_obj, str):
                try: result_obj = json.loads(result_obj)
                except: result_obj = {}
            
            image_urls = result_obj.get("image_urls", [])
            d['images'] = [{"r2_url": url} for url in image_urls]
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
    async def update_generation(self, rid, **kwargs): await update_generation(rid, **kwargs)
    async def create_generation(self, **data): return await create_generation(data)
    async def list_generations(self, limit=20, offset=0, realm=None, before=None): return await list_generations(limit, offset, realm, before)
    async def hide_generation(self, rid): await hide_generation(rid)
    async def delete_generation(self, rid): await delete_generation(rid)

DB = DatabaseProxy()
