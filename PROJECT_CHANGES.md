# Project Changes Summary

This file summarizes the main changes and improvements made to the Aether / ImgnAI server project.

## Core Architecture

- Split the app into clear modules instead of keeping everything in one file.
- Kept `main.py` as the API entrypoint and orchestration layer.
- Moved storage logic into `core/vault.py`.
- Separated Day and Star automation into `engines/day.py` and `engines/star.py`.
- Centralized shared request defaults and model settings in `config/`.

## Backend Improvements

- Added request tracking with `request_id` so a generation can be resumed after timeouts.
- Added `/job-status/{request_id}` for live polling.
- Added `/resume/{request_id}` to restore a saved generation state.
- Added `/history` with pagination so the frontend can load results from the database.
- Added `/health` for a lightweight runtime check.
- Added Neon database persistence for:
  - prompt
  - model
  - quality
  - aspect
  - seed
  - negative prompt
  - realm
  - session UUID
  - task UUIDs
  - final image URLs

## R2 / Vault Improvements

- Standardized R2 uploads so both Day and Star use the same batch-folder structure.
- Grouped all 4 images from one generation under the same batch prefix.
- Used `session_uuid` in the folder name and `task_uuid` for each image file name.
- Made batch names use Pacific Time so timestamps match the user’s timezone.

## Day Flow Improvements

- Kept the Day CLI/subprocess path working.
- Added progress logs while Day is running.
- Added early persistence of session UUIDs and task UUIDs.
- Added direct vault uploads for generated image URLs.

## Star Flow Improvements

- Kept Playwright for login/session handling.
- Switched remote API calls to Python HTTP requests for better reliability.
- Added retry/backoff around polling and auth renewal.
- Added token detection from cookies, localStorage, and sessionStorage.
- Added age-gate handling for the 18+ prompt.
- Added step-by-step screenshots for login debugging.

## Frontend Improvements

- Created `public/index.html` as a standalone frontend entry.
- Updated the UI to work with the new backend contract:
  - `POST /generate`
  - `GET /job-status/{request_id}`
  - `GET /resume/{request_id}`
  - `GET /history`
- Removed the old local JSON recovery path.
- Added retry/resume behavior without restarting generation.
- Added paginated vault browsing with lazy-loaded images.
- Added a clickable viewer for history groups.
- Restored full model lists for Day and Star.
- Removed `4k+` from the frontend quality selector.

## Reliability / Debugging

- Added structured logging across backend generation flows.
- Added debug screenshots for Star login flow.
- Added better error reporting around auth and polling.
- Added recovery behavior for stale Star sessions.

## Important Current Behavior

- The frontend should send the correct `realm`:
  - `day` for Day mode
  - `star` for Star mode
- The backend now routes based on `realm` first.
- Day and Star now have separate 24-model catalogs.
- If a generation times out, the backend still keeps:
  - `request_id`
  - `session_uuid`
  - `task_uuids`
  - DB history

