# LOGBOOK: The Living Ledger

This room tracks the chronological evolution of the Aether / ImgnAI project.

## 📈 Timeline

### [2026-04-21 17:30] 🧵 Parallelism & Async Refactor
- **Event Loop Optimization**: Converted all database operations to use **`AsyncConnectionPool`** (`psycopg_pool`), preventing blocking during history fetches or status checks.
- **Concurrent Managers**: Refactored the **Day** and **Star** managers to be fully asynchronous, allowing generation jobs and vault browsing to happen independently and in parallel.
- **FastAPI Lifespan**: Implemented a lifespan context manager to handle the safe initialization and cleanup of database resources.

### [2026-04-21 17:44] 🔐 Security & Robustness
- **XSS Protection**: Implemented HTML escaping in job cards to prevent payload injection via prompts.
- **Poll Clobbering Protection**: Added request-id verification in the polling loop to ensure old polling threads don't overwrite new data.
- **Improved Messaging**: Refined status verbiage (e.g., "Searching for job pulse...") for better user feedback.

### [2026-04-21 17:53] 📡 Live Streaming & Instant Vault
- **Live Image Streaming**: Re-architected `/job-status` and the gallery renderer to "stream" images into the UI as soon as they appear in the database, without waiting for the full batch.
- **Instant Vault Caching**: Implemented a `localStorage` cache for the history list, allowing the Vault tab to load instantly on refresh.
- **Queue Transparency**: Upgraded the "Active Journeys" view to list all current non-completed jobs from the history database.

### [2026-04-21 17:41] 🏠 Memory House Alpha
- **Initial Migration**: Transitioned from root `.md` files to the `.memory/` Spatial Context system.
- **Room Setup**: Established **ATLAS** (Map), **ENGINES** (Mechanics), and **LOGBOOK** (Ledger).

### [2026-04-21 00:35] ⚡️ Performance Stabilization
- **Vault Optimization**: Introduced `historyLoaded` flag to prevent redundant network calls when switching tabs or Day/Star modes.

## ⚠️ Critical Mistakes & Lessons

1. **[Mistake] Routing by `nsfw`**: Initially used UI flags for backend routing.
   - *Fix*: Switched to explicit `realm` (day/star).
2. **[Mistake] Catalog Drift**: Out-of-sync model lists.
   - *Fix*: Centralized catalogs in `config/models.py`.
3. **[Mistake] Aggressive Reloading**: Wiping UI state on tab switch.
   - *Fix*: Implemented state-aware rendering and caching.

---
*Last Updated: 2026-04-21 17:25*
