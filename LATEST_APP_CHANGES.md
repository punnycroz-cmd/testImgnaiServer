# Latest App Changes

This file summarizes the most recent behavior changes in the app itself, separate from the documentation updates.

## Backend

- Routed generation by `realm` instead of relying on `nsfw`.
- Added `request_id`-based job tracking for resume and retry.
- Persisted generation state in Neon:
  - prompt
  - model
  - quality
  - aspect
  - seed
  - negative prompt
  - realm
  - session UUID
  - task UUIDs
  - image URLs
- Added `/job-status/{request_id}`, `/resume/{request_id}`, `/history`, and `/health`.
- Expanded the Star model catalog to 24 models.
- Kept the Day model catalog at 24 models.

## Frontend

- Added a standalone `public/index.html`.
- Updated the frontend to send `realm` correctly.
- Switched retry/resume flow from local file recovery to backend state recovery.
- Added paginated history loading from the backend.
- Added clickable vault group viewing with thumbnails.
- Restored the full Day and Star model lists.
- Removed `4k+` from the frontend quality selector.

## Day Engine

- Kept Day working through the CLI subprocess path.
- Added better progress logging.
- Saved session UUIDs and task UUIDs early.
- Vaulted images directly to R2.

## Star Engine

- Kept Playwright for login/session handling.
- Added more reliable auth detection.
- Added age-gate handling for the 18+ prompt.
- Added screenshot-based debug steps for login flow.
- Switched remote calls to Python HTTP requests.
- Vaulted images directly to R2.

## Storage

- Standardized R2 upload naming by batch folder, session UUID, and task UUID.
- Batch names now use Pacific time.

