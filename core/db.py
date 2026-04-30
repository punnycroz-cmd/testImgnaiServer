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

        # Create Users Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY, -- Google 'sub' ID
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Create Master History Table with requested constraints
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                uid TEXT REFERENCES users(uid) ON DELETE CASCADE,
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
                hidden_indices INTEGER[] DEFAULT ARRAY[]::INTEGER[],
                
                -- Timestamps
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        # Create Feed/Posts Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                uid TEXT NOT NULL REFERENCES users(uid),
                content TEXT NOT NULL,
                request_id TEXT, -- Optional link to a manifestation
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                is_deleted BOOLEAN DEFAULT FALSE
            );
        """)

        # --- New Relational Schema ---
        
        # 1. Individual images table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_images (
                image_id            BIGSERIAL PRIMARY KEY,
                generation_id       TEXT NOT NULL REFERENCES generations(request_id) ON DELETE CASCADE,
                uid                 TEXT NOT NULL,
                image_index         INTEGER NOT NULL CHECK (image_index >= 0),
                r2_key              TEXT NOT NULL,
                thumbnail_r2_key    TEXT,
                status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','hidden','deleting','deleted')),
                seed_used           BIGINT,
                generation_duration_ms INTEGER,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                deleted_at          TIMESTAMPTZ,
                UNIQUE (generation_id, image_index)
            );
        """)

        # 2. Audit log for image status changes
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS image_status_log (
                log_id      BIGSERIAL PRIMARY KEY,
                image_id    BIGINT NOT NULL REFERENCES generation_images(image_id) ON DELETE CASCADE,
                old_status  TEXT,
                new_status  TEXT NOT NULL,
                changed_by  TEXT NOT NULL DEFAULT 'user',
                reason      TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        # 3. Materialised cache table for fast vault/discovery queries
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS image_summaries (
                request_id      TEXT PRIMARY KEY REFERENCES generations(request_id) ON DELETE CASCADE,
                uid             TEXT NOT NULL,
                realm           TEXT NOT NULL,
                model           TEXT NOT NULL,
                prompt          TEXT NOT NULL,
                total_images    INTEGER NOT NULL DEFAULT 0,
                visible_images  INTEGER NOT NULL DEFAULT 0,
                first_thumbnail TEXT,
                is_hidden       BOOLEAN NOT NULL DEFAULT FALSE,
                is_public       BOOLEAN NOT NULL DEFAULT FALSE,
                image_id_seq    BIGINT NOT NULL,
                created_at      TIMESTAMPTZ NOT NULL,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        # 4. Share links table (shortcode -> private R2 key)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS share_links (
                shortcode   TEXT PRIMARY KEY,
                request_id  TEXT NOT NULL REFERENCES generations(request_id) ON DELETE CASCADE,
                image_index INTEGER NOT NULL,
                r2_key      TEXT NOT NULL,
                title       TEXT,
                created_by  TEXT NOT NULL REFERENCES users(uid),
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at  TIMESTAMPTZ
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_share_request ON share_links (request_id, image_index);")

        # 5. Optional analytics for link clicks
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS share_clicks (
                click_id   BIGSERIAL PRIMARY KEY,
                shortcode  TEXT NOT NULL REFERENCES share_links(shortcode) ON DELETE CASCADE,
                ip_hash    TEXT NOT NULL,
                user_agent TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_clicks_shortcode ON share_clicks (shortcode);")

        # Extra columns for generations
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS image_id_seq BIGSERIAL;")
        
        # Additional Indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_uid_seq ON generations (uid, image_id_seq DESC);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_public_seq ON generations (is_public, realm, image_id_seq DESC) WHERE is_public = TRUE AND status = 'done';")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_images_generation ON generation_images (generation_id, image_index);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_images_uid_status ON generation_images (uid, created_at DESC) WHERE status != 'deleted';")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_uid_seq ON image_summaries (uid, image_id_seq DESC);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_public_seq ON image_summaries (is_public, realm, image_id_seq DESC) WHERE is_public = TRUE AND visible_images > 0;")

        # Self-healing: Ensure columns exist for existing tables
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS uid TEXT DEFAULT 'uid_0';")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS image_id BIGINT;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS result JSONB DEFAULT '{}'::jsonb;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS error TEXT;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS last_error_text TEXT;")
        await conn.execute("ALTER TABLE generations ADD COLUMN IF NOT EXISTS hidden_indices INTEGER[] DEFAULT ARRAY[]::INTEGER[];")
        
        # Backfill: Assign image_id to existing rows that don't have one
        null_rows = await conn.fetch("SELECT id FROM generations WHERE image_id IS NULL ORDER BY created_at ASC")
        if null_rows:
            logging.info(f"Backfilling image_id for {len(null_rows)} existing rows...")
            for i, row in enumerate(null_rows):
                await conn.execute("UPDATE generations SET image_id = $1, uid = 'uid_0' WHERE id = $2", i + 1, row['id'])
            logging.info("Backfill complete!")

async def upsert_user(uid: str, email: str, name: str = None, picture: str = None) -> Dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO users (uid, email, name, picture, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (uid) DO UPDATE 
            SET email = EXCLUDED.email, 
                name = EXCLUDED.name, 
                picture = EXCLUDED.picture,
                updated_at = NOW()
            RETURNING *
        """, uid, email, name, picture)
        return dict(row)

async def get_user(uid: str) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE uid = $1", uid)
        return dict(row) if row else None
        
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


def _build_images(result_obj: Dict[str, Any], include_hidden: bool = False, hidden_indices: List[int] = None) -> List[Dict]:
    """Returns list of image objects with status metadata."""
    images = []
    
    # Map lists for easy lookup
    active_urls = result_obj.get("image_urls", [])
    active_thumbs = result_obj.get("thumbnail_urls", [])
    
    # Active images
    hidden_indices = hidden_indices or []
    for i, url in enumerate(active_urls):
        if url: 
            thumb = active_thumbs[i] if i < len(active_thumbs) else url
            status = "hidden" if i in hidden_indices else "active"
            images.append({"r2_url": url, "thumbnail_url": thumb, "status": status, "image_index": i})
        
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
    
    if "uid" not in data:
        data["uid"] = "uid_0"
    
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
    
    query = f"INSERT INTO generations ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING request_id, image_id_seq"
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        request_id = row["request_id"]
        
        # Initial image_summaries entry (pending status)
        await conn.execute(
            """
            INSERT INTO image_summaries 
            (request_id, uid, realm, model, prompt, total_images, visible_images, is_hidden, is_public, image_id_seq, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, 0, FALSE, $7, $8, NOW())
            ON CONFLICT (request_id) DO NOTHING
            """,
            request_id, data["uid"], data.get("realm", "day"), data.get("model", ""), 
            data.get("prompt", ""), data.get("count", 4), data.get("is_public", False), row["image_id_seq"]
        )
        
        return request_id


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
        target_idx = -1
        target_key = None

        # 1. Find the index and which list it belongs to
        for key in ["image_urls", "hidden_image_urls"]:
            urls = result_obj.get(key, [])
            for i, u in enumerate(urls):
                if u and _normalize_image_url(u) == image_url:
                    target_idx = i
                    target_key = key
                    break
            if target_idx != -1: break
            
        if target_idx == -1:
            return result_obj, False

        # 2. Clear at that index in the primary list AND its corresponding thumbnail list
        thumb_key = "thumbnail_urls" if target_key == "image_urls" else "hidden_thumbnail_urls"
        
        for key in [target_key, thumb_key]:
            lst = result_obj.get(key)
            if isinstance(lst, list) and target_idx < len(lst):
                if lst[target_idx] != "":
                    lst[target_idx] = ""
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
        async with conn.transaction():
            await conn.execute(query, *values)
            
            # If status updated to done or result updated, sync relational tables
            if fields.get("status") == "done" or "result" in fields:
                row = await conn.fetchrow("SELECT uid, result, is_public FROM generations WHERE request_id = $1", request_id)
                if row:
                    uid = row["uid"]
                    res_obj = _normalize_result(row["result"])
                    is_pub = row["is_public"]
                    
                    img_urls = res_obj.get("image_urls", [])
                    thumb_urls = res_obj.get("thumbnail_urls", [])
                    
                    # Sync generation_images
                    for idx, url in enumerate(img_urls):
                        thumb = thumb_urls[idx] if idx < len(thumb_urls) else None
                        await conn.execute(
                            """
                            INSERT INTO generation_images (generation_id, uid, image_index, r2_key, thumbnail_r2_key, status)
                            VALUES ($1, $2, $3, $4, $5, 'active')
                            ON CONFLICT (generation_id, image_index) DO UPDATE 
                            SET r2_key = EXCLUDED.r2_key, thumbnail_r2_key = EXCLUDED.thumbnail_r2_key, updated_at = NOW()
                            """,
                            request_id, uid, idx, url, thumb
                        )
                    
                    # Update image_summaries
                    await conn.execute(
                        """
                        UPDATE image_summaries 
                        SET total_images = $2, 
                            visible_images = (SELECT COUNT(*) FROM generation_images WHERE generation_id = $1 AND status = 'active'),
                            first_thumbnail = $3,
                            is_public = $4,
                            updated_at = NOW()
                        WHERE request_id = $1
                        """,
                        request_id, len(img_urls), thumb_urls[0] if thumb_urls else None, is_pub
                    )

async def get_generation(request_id: str, include_hidden: bool = False) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM generations WHERE request_id = $1", request_id)
        if row:
            d = dict(row)
            d['id'] = str(d['id'])
            result_obj = _normalize_result(d.get("result"))
            d['hidden_indices'] = d.get('hidden_indices') or []
            d['images'] = _build_images(result_obj, include_hidden=include_hidden, hidden_indices=d['hidden_indices'])
            return d
        return None



async def list_generations(limit: int = 20, offset: int = 0, realm: Optional[str] = None, before_id: Optional[int] = None, uid: str = "uid_0", include_hidden: bool = False) -> List[Dict]:
    pool = await get_pool()
    
    # We query from image_summaries for speed
    clauses = ["(s.uid = $1 OR (s.is_public = TRUE AND s.uid = 'uid_0'))"]
    params = [uid] # $1

    if not include_hidden:
        clauses.append("s.is_hidden = FALSE")
    
    if realm:
        params.append(realm)
        clauses.append(f"s.realm = ${len(params)}")
        
    if before_id is not None:
        try:
            params.append(int(before_id))
            clauses.append(f"s.image_id_seq < ${len(params)}")
        except: pass
        
    where_stmt = " WHERE " + " AND ".join(clauses)
    
    params.append(int(limit))
    sql = f"""
        SELECT s.*, g.client_id, g.session_uuid, g.result, g.error, g.hidden_indices
        FROM image_summaries s
        JOIN generations g ON s.request_id = g.request_id
        {where_stmt}
        ORDER BY s.image_id_seq DESC 
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
            d['images'] = _build_images(result_obj, include_hidden=include_hidden, hidden_indices=d['hidden_indices'])
            results.append(d)
        return results

async def hide_image_index(request_id: str, index: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Update the indices
        await conn.execute("""
            UPDATE generations 
            SET hidden_indices = array_append(hidden_indices, $2::INTEGER),
                updated_at = NOW()
            WHERE request_id = $1 AND NOT ($2 = ANY(hidden_indices))
        """, request_id, index)
        
        # 2. Update individual image status in relational table
        await conn.execute("""
            UPDATE generation_images 
            SET status = 'hidden', updated_at = NOW()
            WHERE generation_id = $1 AND image_index = $2
        """, request_id, index)

        # 3. Write to audit log
        await conn.execute("""
            INSERT INTO image_status_log (image_id, old_status, new_status, changed_by)
            SELECT image_id, 'active', 'hidden', 'user'
            FROM generation_images WHERE generation_id = $1 AND image_index = $2
        """, request_id, index)

        # 4. Refresh summary
        await conn.execute("""
            UPDATE image_summaries
            SET visible_images = (SELECT COUNT(*) FROM generation_images WHERE generation_id = $1 AND status = 'active'),
                is_hidden = ((SELECT COUNT(*) FROM generation_images WHERE generation_id = $1 AND status = 'active') = 0),
                updated_at = NOW()
            WHERE request_id = $1
        """, request_id)
        return True

async def show_image_index(request_id: str, index: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Update the indices
        await conn.execute("""
            UPDATE generations 
            SET hidden_indices = array_remove(hidden_indices, $2::INTEGER),
                updated_at = NOW()
            WHERE request_id = $1
        """, request_id, index)
        
        # 2. Update individual image status
        await conn.execute("""
            UPDATE generation_images 
            SET status = 'active', updated_at = NOW()
            WHERE generation_id = $1 AND image_index = $2
        """, request_id, index)

        # 3. Refresh summary
        await conn.execute("""
            UPDATE image_summaries
            SET visible_images = (SELECT COUNT(*) FROM generation_images WHERE generation_id = $1 AND status = 'active'),
                is_hidden = FALSE,
                updated_at = NOW()
            WHERE request_id = $1
        """, request_id)
        return True

async def hide_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE generations SET is_hidden = true WHERE request_id = $1", request_id)

async def show_generation(request_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE generations SET is_hidden = false, hidden_indices = ARRAY[]::INTEGER[] WHERE request_id = $1", request_id)

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
    
    # Generic helper methods for scripts
    async def fetch(self, query: str, *args):
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def execute(self, query: str, *args):
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    async def delete_generation(self, rid): await delete_generation(rid)
    async def hide_image(self, rid, url): await hide_image(rid, url)
    async def show_image(self, rid, url): await show_image(rid, url)
    async def hide_image_index(self, rid, idx): await hide_image_index(rid, idx)
    async def show_image_index(self, rid, idx): await show_image_index(rid, idx)
    async def upsert_user(self, uid, email, name=None, picture=None): return await upsert_user(uid, email, name, picture)
    async def get_user(self, uid): return await get_user(uid)
    async def delete_image(self, rid, url): return await delete_image(rid, url)
    async def mark_image_deleting(self, rid, url): return await mark_image_deleting(rid, url)
    async def finalize_image_deletion(self, rid, url): return await finalize_image_deletion(rid, url)
    async def set_generation_public(self, rid, is_public: bool): return await set_generation_public(rid, is_public)
    async def list_public_generations(self, limit=20, before_id=None): return await list_public_generations(limit, before_id)
    async def create_post(self, uid, content, request_id=None): return await create_post(uid, content, request_id)
    async def list_posts(self, limit=20, before_id=None): return await list_posts(limit, before_id)

async def create_post(uid: str, content: str, request_id: Optional[str] = None) -> Dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO posts (uid, content, request_id) 
            VALUES ($1, $2, $3) 
            RETURNING id, created_at
        """, uid, content, request_id)
        return dict(row)

async def list_posts(limit: int = 20, before_id: Optional[int] = None) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        clauses = ["posts.is_deleted = FALSE"]
        params = []
        if before_id:
            params.append(int(before_id))
            clauses.append(f"posts.id < ${len(params)}")
        
        where_stmt = " WHERE " + " AND ".join(clauses)
        params.append(int(limit))
        
        sql = f"""
            SELECT 
                posts.*, 
                users.name, 
                users.picture,
                s.first_thumbnail as preview_url,
                s.realm as preview_realm,
                s.is_public
            FROM posts 
            JOIN users ON posts.uid = users.uid 
            LEFT JOIN image_summaries s ON posts.request_id = s.request_id
            {where_stmt}
            ORDER BY posts.id DESC 
            LIMIT ${len(params)}
        """
        rows = await conn.fetch(sql, *params)
        results = []
        for r in rows:
            d = dict(r)
            if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
            if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
            
            # Ensure preview_url is correctly handled (absolute R2 URL)
            if d.get('preview_url') and not d['preview_url'].startswith('http'):
                 d['preview_url'] = 'https://pub-b770478fe936495c8d44e69fb02d2943.r2.dev/' + d['preview_url'].lstrip('/')
            
            results.append(d)
        return results

async def set_generation_public(request_id: str, is_public: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                UPDATE generations 
                SET is_public = $2, 
                    updated_at = NOW() 
                WHERE request_id = $1
            """, request_id, is_public)
            
            await conn.execute("""
                UPDATE image_summaries
                SET is_public = $2,
                    updated_at = NOW()
                WHERE request_id = $1
            """, request_id, is_public)
            return True

async def list_public_generations(limit: int = 20, before_id: Optional[int] = None) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        clauses = ["s.is_public = TRUE", "s.visible_images > 0"]
        params = []
        
        if before_id is not None:
            params.append(int(before_id))
            clauses.append(f"s.image_id_seq < ${len(params)}")
            
        where_stmt = " WHERE " + " AND ".join(clauses)
        params.append(int(limit))
        
        sql = f"""
            SELECT s.*, g.result, g.hidden_indices
            FROM image_summaries s
            JOIN generations g ON s.request_id = g.request_id
            {where_stmt}
            ORDER BY s.image_id_seq DESC 
            LIMIT ${len(params)}
        """
        rows = await conn.fetch(sql, *params)
        
        results = []
        for r in rows:
            d = dict(r)
            if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
            if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
            
            result_obj = _normalize_result(d.get("result"))
            d['images'] = _build_images(result_obj, include_hidden=False, hidden_indices=d['hidden_indices'])
            results.append(d)
        return results

DB = DatabaseProxy()
