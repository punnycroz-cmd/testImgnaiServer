# ATLAS: The Project Map

This room contains the spatial context for the Aether / ImgnAI Server. Use this to orient yourself within the codebase.

## 🛰️ System Overview

The Aether Server is an orchestration layer for image generation. It bridges the gap between client requests and upstream generation engines, handling persistence and image vaulting.

## 🏠 Project Structure

- **`main.py`**: The Brain. FastAPI entrypoint and orchestrator.
- **`engines/`**: The Muscles. Automation for Day (CLI) and Star (Playwright).
- **`core/`**: The Foundation. Neon (DB) and Cloudflare R2 (Vault).
- **`config/`**: The Knowledge. Shared models, schemas, and catalogs.
- **`public/`**: The Face. Frontend manifests and UI.

## 🧭 High-Level Data Flow

1. **Request**: UI sends payload to `/generate` with a `realm` (day/star).
2. **Persistence**: `main.py` initiates a record in Neon and returns a `request_id`.
3. **Execution**: The relevant manager (`DayManager` or `StarManager`) takes over.
4. **Resolution**: Images are generated, uploaded to **Cloudflare R2**, and the job is marked `done`.

## 🛠️ Essential Paths

- **Models**: [models.py](../config/models.py)
- **DB Operations**: [db.py](../core/db.py)
- **R2 Vaulting**: [vault.py](../core/vault.py)
- **Generation Entry**: [main.py](../main.py)

---
*For deep dives into specific subsystems, see the other rooms in the Memory House.*
