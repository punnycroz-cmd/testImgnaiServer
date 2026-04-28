import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import os
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv
import asyncpg
from uuid import uuid4

load_dotenv()

LOGGER = logging.getLogger("db")

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

async def init_db(force: bool = False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Load extensions for UUID generation (still good to have)
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        
        if force:
            await conn.execute("DROP TABLE IF EXISTS generations CASCADE;")

        # Create Master History Table with requested constraints
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                uid TEXT DEFAULT 'uid_0',
                image_id BIGINT,
                id UUID PRIMARY KEY,
                
                -- Request Identifiers
                request_id TEXT UNIQUE NOT NULL,
                client_id TEXT,
                
                -- Configuration
                realm TEXT CHECK (realm IN ('star', 'day')),
                prompt TEXT,
                negative_prompt TEXT,
                model TEXT,
                quality TEXT,
                aspect TEXT,
                seed BIGINT,
                count INTEGER,
                
                -- Grouping & Status
                session_uuid TEXT,
                status TEXT CHECK (status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending',
                is_hidden BOOLEAN DEFAULT FALSE,
                
                -- Results & Errors
                result JSONB DEFAULT '{}', -- Will hold { "image_urls": [...] }
                error TEXT,
                last_error_text TEXT,
                
                -- Timestamps
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Self-healing: Ensure columns exist for existing tables
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS uid TEXT DEFAULT 'uid_0';")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS image_id BIGINT;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS result JSONB DEFAULT '{}'::jsonb;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS error TEXT;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS last_error_text TEXT;")
        
        # Backfill: Assign image_id to existing rows that don't have one
        null_rows = await conn.fetch("SELECT id FROM generations WHERE image_id IS NULL ORDER BY created_at ASC")
        if null_rows:
            logging.info(f"Backfilling image_id for {len(null_rows)} existing rows...")
            for i, row in enumerate(null_rows):
                await conn.execute("UPDATE generations SET image_id = $1, uid = 'uid_0' WHERE id = $2", i + 1, row['id'])
            logging.info("Backfill complete!")
        
        # CRITICAL INDEXES (Prevents 502 errors & sorts correctly)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_realm_created ON generations (realm, created_at DESC);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_status ON generations (status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_uid_image ON generations (uid, image_id DESC);")


async def get_next_image_id(uid: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT MAX(image_id) FROM generations WHERE uid = $1", uid)
        return (val or 0) + 1


def _normalize_result(result_obj: Any) -> Dict[str, Any]:
    if not result_obj:
        return {}
    if isinstance(result_obj, str):
        try:
            result_obj = json.loads(result_obj)
        except Exception:
            return {}
    if not isinstance(result_obj, dict):
        return {}
    result_obj.setdefault("image_urls", [])
    result_obj.setdefault("hidden_image_urls", [])
    result_obj.setdefault("deleting_image_urls", []) # New intermediate state
    result_obj.setdefault("deleted_image_urls", [])
    return result_obj


def _build_images(result_obj: Dict[str, Any], include_hidden: bool = False) -> List[Dict]:
    """Returns list of image objects with status metadata."""
    images = []
    
    # Map lists for easy lookup
    active_urls = result_obj.get("image_urls", [])
    active_thumbs = result_obj.get("thumbnail_urls", [])
    
    # Active images
    for i, url in enumerate(active_urls):
        if url: 
            thumb = active_thumbs[i] if i < len(active_thumbs) else url
            images.append({"r2_url": url, "thumbnail_url": thumb, "status": "active", "image_index": i})
        
    # Hidden images (Archive)
    if include_hidden:
        hidden_urls = result_obj.get("hidden_image_urls", [])
        hidden_thumbs = result_obj.get("hidden_thumbnail_urls", [])
        for i, url in enumerate(hidden_urls):
            if url: 
                thumb = hidden_thumbs[i] if i < len(hidden_thumbs) else url
                images.append({"r2_url": url, "thumbnail_url": thumb, "status": "hidden", "image_index": i})
            
    # Deleting images (Transient state for UI blurring)
    deleting_urls = result_obj.get("deleting_image_urls", [])
    deleting_thumbs = result_obj.get("deleting_thumbnail_urls", [])
    for i, url in enumerate(deleting_urls):
        if url: 
            thumb = deleting_thumbs[i] if i < len(deleting_thumbs) else url
            images.append({"r2_url": url, "thumbnail_url": thumb, "status": "deleting", "image_index": i})
        
    return images


def _normalize_image_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        # Strip query/fragment because UI cache-busting can append them.
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except Exception:
        return raw.split("?", 1)[0].split("#", 1)[0]


async def _mutate_result_images(request_id: str, mutator) -> Tuple[Optional[Dict], bool]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT result FROM generations WHERE request_id = $1 FOR UPDATE", request_id)
            if not row:
                return None, False
            result_obj = _normalize_result(row["result"])
            new_result, changed = mutator(result_obj)
            if not changed:
                return new_result, False
            await conn.execute(
                "UPDATE generations SET result = $1, updated_at = NOW() WHERE request_id = $2",
                json.dumps(new_result),
                request_id,
            )
            return new_result, True


async def create_generation(data: Dict[str, Any]) -> str:
    pool = await get_pool()
    
    # User and Image ID logic
    if "uid" not in data:
        data["uid"] = "uid_0"
    
    if "image_id" not in data:
        data["image_id"] = await get_next_image_id(data["uid"])
    
    # Generate ID in Python to avoid DB extension issues
    if "id" not in data:
        data["id"] = str(uuid4())
        
    cols = []
    placeholders = []
    values = []
    for i, (k, v) in enumerate(data.items()):
        cols.append(k)
        placeholders.append(f"${i+1}")
        if k == "result" and not isinstance(v, (str, bytes)):
            values.append(json.dumps(v))
        else:
            values.append(v)
    
    query = f"INSERT INTO generations ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING request_id"
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *values)


async def hide_image(request_id: str, image_url: str) -> bool:
    image_url = _normalize_image_url(image_url)
    if not image_url:
        return False

    def mutator(result_obj):
        changed = False
        visible = []
        for u in result_obj.get("image_urls", []):
            if not u:
                continue
            if _normalize_image_url(u) == image_url:
                changed = True
                continue
            visible.append(u)
        
        result_obj["image_urls"] = visible
        hidden = [u for u in result_obj.get("hidden_image_urls", []) if u]
        if all(_normalize_image_url(u) != image_url for u in hidden):
            hidden.append(image_url)
            changed = True
        result_obj["hidden_image_urls"] = hidden
        return result_obj, changed

    res_obj, ok = await _mutate_result_images(request_id, mutator)
    return ok


async def show_image(request_id: str, image_url: str) -> bool:
    image_url = _normalize_image_url(image_url)
    if not image_url:
        return False

    def mutator(result_obj):
        changed = False
        hidden = []
        for u in result_obj.get("hidden_image_urls", []):
            if not u:
                continue
            if _normalize_image_url(u) == image_url:
                changed = True
                continue
            hidden.append(u)
        visible = [u for u in result_obj.get("image_urls", []) if u]
        if all(_normalize_image_url(u) != image_url for u in visible):
            visible.append(image_url)
            changed = True
        result_obj["hidden_image_urls"] = hidden
        result_obj["image_urls"] = visible
        return result_obj, changed

    res_obj, ok = await _mutate_result_images(request_id, mutator)
    return ok


async def mark_image_deleting(request_id: str, image_url: str) -> bool:
    """Move image to a 'deleting' state in the DB."""
    image_url = _normalize_image_url(image_url)
    if not image_url: return False

    def mutator(result_obj):
        changed = False
        # Remove from active or hidden
        for key in ["image_urls", "hidden_image_urls"]:
            old_list = result_obj.get(key, [])
            new_list = [u for u in old_list if u and _normalize_image_url(u) != image_url]
            if len(new_list) < len(old_list):
                result_obj[key] = new_list
                changed = True
        
        if changed:
            deleting = [u for u in result_obj.get("deleting_image_urls", []) if u]
            if all(_normalize_image_url(u) != image_url for u in deleting):
                deleting.append(image_url)
            result_obj["deleting_image_urls"] = deleting
        return result_obj, changed

    res, ok = await _mutate_result_images(request_id, mutator)
    return ok

async def finalize_image_deletion(request_id: str, image_url: str) -> bool:
    """Move image from 'deleting' to 'deleted' graveyard."""
    image_url = _normalize_image_url(image_url)
    if not image_url: return False

    def mutator(result_obj):
        changed = False
        deleting = result_obj.get("deleting_image_urls", [])
        new_deleting = [u for u in deleting if u and _normalize_image_url(u) != image_url]
        
        if len(new_deleting) < len(deleting):
            result_obj["deleting_image_urls"] = new_deleting
            changed = True
            
            deleted = [u for u in result_obj.get("deleted_image_urls", []) if u]
            if all(_normalize_image_url(u) != image_url for u in deleted):
                deleted.append(image_url)
            result_obj["deleted_image_urls"] = deleted
            
        return result_obj, changed

    res, ok = await _mutate_result_images(request_id, mutator)
    return ok

async def delete_image(request_id: str, image_url: str) -> bool:
    # Legacy wrapper: for immediate hard-ish delete
    return await mark_image_deleting(request_id, image_url)


async def update_generation(request_id: str, **fields: Any):
    if not fields:
        return
    
    sets = []
    values = []
    i = 1
    for key, val in fields.items():
        sets.append(f"{key} = ${i}")
        if key == "result" and not isinstance(val, (str, bytes)):
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

async def get_generation(request_id: str, include_hidden: bool = False) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM generations WHERE request_id = $1", request_id)
        if row:
            d = dict(row)
            if d.get('id'): d['id'] = str(d['id'])
            result_obj = _normalize_result(d.get("result"))
            d['images'] = _build_images(result_obj, include_hidden=include_hidden)
            return d
        return None



async def list_generations(limit: int = 20, offset: int = 0, realm: Optional[str] = None, before_id: Optional[int] = None, uid: str = "uid_0", include_hidden: bool = False) -> List[Dict]:
    pool = await get_pool()
    
    # Build where clauses explicitly
    clauses = ["status = 'done'", "uid = $1"]
    params = [uid] # $1

    if not include_hidden:
        clauses.append("is_hidden = FALSE")
    
    if realm:
        params.append(realm)
        clauses.append(f"realm = ${len(params)}")
        
    if before_id is not None:
        try:
            params.append(int(before_id))
            clauses.append(f"image_id < ${len(params)}")
        except: pass
        
    where_stmt = " WHERE " + " AND ".join(clauses)
    
    # Final Query
    params.append(int(limit))
    sql = f"""
        SELECT uid, image_id, request_id, client_id, realm, prompt, model, 
               quality, aspect, count, session_uuid, result, error, 
               created_at, updated_at 
        FROM generations 
        {where_stmt}
        ORDER BY image_id DESC 
        LIMIT ${len(params)}
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
            
        results = []
        for r in rows:
            d = dict(r)
            if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
            if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
            
            result_obj = _normalize_result(d.get("result"))
            d['images'] = _build_images(result_obj, include_hidden=include_hidden)
            results.append(d)
        return results

async def hide_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE generations SET is_hidden = true WHERE request_id = $1", request_id)

async def show_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE generations SET is_hidden = false WHERE request_id = $1", request_id)

async def delete_generation(request_id: str) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM generations WHERE request_id = $1 RETURNING result", request_id)
        return dict(row) if row else None

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

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

# Compatibility Layer
class DatabaseProxy:
    async def init(self, force: bool = False): await init_db(force)
    async def get_pool(self): return await get_pool()
    async def close(self): await close_pool()
    async def get_generation(self, rid): return await get_generation(rid)
    async def update_generation(self, rid, **kwargs): await update_generation(rid, **kwargs)
    async def create_generation(self, **data): return await create_generation(data)
    async def list_generations(self, limit=20, offset=0, realm=None, before_id=None, uid="uid_0", include_hidden=False):
        return await list_generations(limit=limit, offset=offset, realm=realm, before_id=before_id, uid=uid, include_hidden=include_hidden)
    async def hide_generation(self, rid): await hide_generation(rid)
    async def show_generation(self, rid): await show_generation(rid)
    async def delete_generation(self, rid): await delete_generation(rid)
    async def hide_image(self, rid, url): await hide_image(rid, url)
    async def show_image(self, rid, url): await show_image(rid, url)
    async def delete_image(self, rid, url): return await delete_image(rid, url)
    async def mark_image_deleting(self, rid, url): return await mark_image_deleting(rid, url)
    async def finalize_image_deletion(self, rid, url): return await finalize_image_deletion(rid, url)

DB = DatabaseProxy()
