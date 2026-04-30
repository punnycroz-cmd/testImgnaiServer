-- 2024-04-30 Migration: Add normalized image tables and share link workflow

-- 1. Individual images table
CREATE TABLE generation_images (
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

-- 2. Audit log for image status changes
CREATE TABLE image_status_log (
    log_id      BIGSERIAL PRIMARY KEY,
    image_id    BIGINT NOT NULL REFERENCES generation_images(image_id) ON DELETE CASCADE,
    old_status  TEXT,
    new_status  TEXT NOT NULL,
    changed_by  TEXT NOT NULL DEFAULT 'user',
    reason      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Materialised view (table) for fast vault/discovery queries
CREATE TABLE image_summaries (
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

-- 4. Share links table (shortcode → private R2 key)
CREATE TABLE share_links (
    shortcode   TEXT PRIMARY KEY,
    request_id  TEXT NOT NULL REFERENCES generations(request_id) ON DELETE CASCADE,
    image_index INTEGER NOT NULL,
    r2_key      TEXT NOT NULL,
    title       TEXT,
    created_by  TEXT NOT NULL REFERENCES users(uid),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);
CREATE INDEX idx_share_request ON share_links (request_id, image_index);

-- 5. Optional analytics for link clicks
CREATE TABLE share_clicks (
    click_id   BIGSERIAL PRIMARY KEY,
    shortcode  TEXT NOT NULL REFERENCES share_links(shortcode) ON DELETE CASCADE,
    ip_hash    TEXT NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_clicks_shortcode ON share_clicks (shortcode);

-- 6. Indexes for fast queries
CREATE INDEX idx_generations_uid_seq ON generations (uid, image_id_seq DESC);
CREATE INDEX idx_generations_status ON generations (status);
CREATE INDEX idx_generations_public_seq ON generations (is_public, realm, image_id_seq DESC)
    WHERE is_public = TRUE AND status = 'done';

CREATE INDEX idx_images_generation ON generation_images (generation_id, image_index);
CREATE INDEX idx_images_uid_status ON generation_images (uid, created_at DESC)
    WHERE status != 'deleted';
CREATE INDEX idx_images_deleting ON generation_images (status, updated_at)
    WHERE status = 'deleting';

CREATE INDEX idx_summaries_uid_seq ON image_summaries (uid, image_id_seq DESC);
CREATE INDEX idx_summaries_public_seq ON image_summaries (is_public, realm, image_id_seq DESC)
    WHERE is_public = TRUE AND visible_images > 0;

CREATE INDEX idx_posts_created ON posts (created_at DESC) WHERE is_deleted = FALSE;
