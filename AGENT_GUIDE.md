# Aether Server Agent Guide

This file gives a short map of the project so a new agent can work efficiently without reading the whole codebase.

## High-Level Flow

1. Frontend sends a generation request to `main.py`.
2. `main.py` creates a `request_id` and stores generation state in Neon.
3. `main.py` routes the request to either Day or Star based on `realm`.
4. The engine logs in, creates a session UUID, submits a batch, and polls task UUIDs.
5. Generated images are uploaded to Cloudflare R2.
6. The final vaulted image URLs are returned to the frontend.

## File Map

### `main.py`

- FastAPI app entrypoint.
- Owns API routes and job orchestration.
- Important routes:
  - `GET /`
  - `GET /health`
  - `POST /generate`
  - `GET /job-status/{request_id}`
  - `GET /resume/{request_id}`
  - `GET /history`
- Routes by `realm`:
  - `day` -> Day manager
  - `star` -> Star manager

### `config/models.py`

- Shared configuration and model catalog.
- Contains:
  - `MODEL_CONFIGS` for Day
  - `STAR_MODEL_CONFIGS` for Star
  - `MODEL_ORDER`
  - `QUALITY_CHOICES`
  - `ASPECT_CHOICES`
  - `ASPECT_TO_RESOLUTION`
- If a model is missing here, the backend may fall back to `Gen`.

### `config/schemas.py`

- Shared request schema.
- Defines `GenerateRequest`.
- Keep this in sync with frontend payload fields.

### `core/db.py`

- Neon/Postgres persistence layer.
- Stores:
  - generation rows
  - image rows
  - session UUIDs
  - task UUIDs
  - status / result / error
- Used by:
  - `POST /generate`
  - `GET /job-status/{request_id}`
  - `GET /resume/{request_id}`
  - `GET /history`

### `core/vault.py`

- Cloudflare R2 helper.
- Handles:
  - file uploads
  - batch folder naming
  - image URL generation
  - R2 listing
- Current naming convention:
  - `vault/<timestamp>_<realm>_<session_uuid>/<task_uuid>.jpg`

### `engines/day.py`

- Day engine wrapper.
- Calls the Day CLI subprocess.
- Reads CLI output to capture:
  - session UUID
  - task UUIDs
  - source image URLs
- Uploads images to R2.

### `engines/day_api_client.py`

- Day CLI implementation.
- Handles:
  - login
  - auth token extraction
  - session creation
  - batch creation
  - polling
- Emits JSON log lines for session/task state.

### `engines/star.py`

- Star engine wrapper.
- Uses Playwright plus HTTP requests.
- Handles:
  - login
  - session creation
  - batch creation
  - polling
  - R2 upload
- Also writes Star generation state to Neon.

### `engines/star_client.py`

- Shared Star browser/login helpers.
- Handles:
  - age-gate acceptance
  - screenshot debug capture
  - token discovery
  - cookie persistence

### `public/index.html`

- Frontend entry.
- Sends requests to the backend and renders results.
- Supports:
  - generation
  - retry/resume
  - history browsing
  - lazy-loaded vault thumbnails

## Key Concepts

### `request_id`

- Server-side retry token for one generation attempt.
- Frontend should store it when generation starts.
- Retry should use `/resume/{request_id}` or `/job-status/{request_id}`.

### `session_uuid`

- Upstream generation session identifier.
- Saved in Neon early.
- Used to group uploads in R2.

### `task_uuids`

- The 4 task IDs returned by the batch API.
- Saved in Neon early.
- Used for polling and naming each image file.

### `realm`

- Determines the backend path:
  - `day`
  - `star`
- Frontend should send the correct realm.

## Safe Edit Targets

- Add or change model behavior:
  - `config/models.py`
- Change API routes:
  - `main.py`
- Change upload naming or R2 behavior:
  - `core/vault.py`
- Fix Day browser/login behavior:
  - `engines/day_api_client.py`
  - `engines/day.py`
- Fix Star login/token/polling:
  - `engines/star_client.py`
  - `engines/star.py`

## Common Pitfalls

- Do not assume `nsfw` alone controls routing.
- Do not add business logic directly in `main.py`.
- Do not remove `request_id` persistence if you want retries to work.
- Do not add new Star models only in the frontend; `config/models.py` must also know them.

