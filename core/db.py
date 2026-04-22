import json
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Optional, List

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def _now():
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, url: Optional[str] = None):
        self.url = url or os.environ.get("DATABASE_URL")
        self.enabled = bool(self.url)
        self.pool: Optional[AsyncConnectionPool] = None

    async def get_pool(self) -> AsyncConnectionPool:
        if not self.enabled:
            raise RuntimeError("DATABASE_URL is not set")
        if self.pool is None:
            self.pool = AsyncConnectionPool(
                conninfo=self.url,
                min_size=2,
                max_size=10,
                kwargs={"row_factory": dict_row},
                open=False
            )
            await self.pool.open()
        return self.pool

    async def init(self):
        if not self.enabled:
            return
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
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
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now()
                    );
                    """
                )
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS generation_images (
                        id uuid PRIMARY KEY,
                        generation_id uuid NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
                        task_uuid text NOT NULL,
                        r2_url text NOT NULL,
                        r2_key text NOT NULL,
                        image_index integer NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    );
                    """
                )
            await conn.commit()

    async def create_generation(self, *, generation_id: str, request_id: str, client_id: Optional[str], realm: str, prompt: str, model: str, quality: str, aspect: str, seed: Optional[int], negative_prompt: Optional[str], count: int = 4):
        if not self.enabled:
            return
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO generations (
                        id, request_id, client_id, realm, status, prompt, model, quality, aspect, seed, negative_prompt, count, updated_at
                    ) VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, %s, %s, %s, %s)
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
                    (generation_id, request_id, client_id, realm, prompt, model, quality, aspect, seed, negative_prompt, count, _now()),
                )
            await conn.commit()

    async def update_generation(self, request_id: str, **fields: Any):
        if not self.enabled or not fields:
            return
        sets = []
        values = []
        for key, val in fields.items():
            sets.append(f"{key} = %s")
            if key == "task_uuids" and not isinstance(val, str):
                values.append(json.dumps(val))
            elif key == "result" and not isinstance(val, str):
                values.append(json.dumps(val))
            else:
                values.append(val)
        sets.append("updated_at = %s")
        values.append(_now())
        values.append(request_id)
        
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"UPDATE generations SET {', '.join(sets)} WHERE request_id = %s", values)
            await conn.commit()

    async def add_image(self, *, generation_id: str, task_uuid: str, r2_url: str, r2_key: str, image_index: int):
        if not self.enabled:
            return
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO generation_images (id, generation_id, task_uuid, r2_url, r2_key, image_index)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), generation_id, task_uuid, r2_url, r2_key, image_index),
                )
            await conn.commit()

    async def get_generation(self, request_id: str):
        if not self.enabled:
            return None
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM generations WHERE request_id = %s", (request_id,))
                return await cur.fetchone()

    async def get_generation_images(self, generation_id: str):
        if not self.enabled:
            return []
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM generation_images WHERE generation_id = %s ORDER BY image_index ASC", (generation_id,))
                return await cur.fetchall()

    async def list_generations(self, limit: int = 20, offset: int = 0):
        if not self.enabled:
            return []
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM generations ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                return await cur.fetchall()
