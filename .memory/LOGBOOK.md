# LOGBOOK: Changes & Fixes

This room tracks the evolution of the project and the lessons learned through mistakes.

## 📈 Recent Changes

- **Memory House Migration**: Implemented the `.memory/` system for better agentic context.
- **Frontend Robustness**: 
  - Fixed XSS vulnerability in job cards by escaping prompt content.
  - Improved the Queue (Active Journeys) to show all current jobs instead of just the last one.
  - Added "Poll Clobbering" protection to prevent multiple simultaneous loops from interfering with UI state.
  - Enabled auto-refresh for the Vault tab when jobs complete in the background.
- **Vault Optimization**: Fixed aggressive "reloading" in the frontend history view by adding `historyLoaded` state tracking.
- **Standardization**: Unified R2 naming conventions and directory structures for both engines.
- **Persistence**: Fully migrated from local JSON storage to Neon (Postgres).

## ⚠️ Critical Mistakes & Lessons

1. **Routing Confusion**: Initially routed by `nsfw` flag instead of explicit `realm`.
   - *Lesson*: Use explicit fields for business logic paths.
2. **Catalog Drift**: Frontend and Backend model lists went out of sync.
   - *Lesson*: Maintain a shared source of truth in `config/`.
3. **Aggressive Reloading**: Frontend reset history on every mode switch or tab click.
   - *Lesson*: Do not clear UI state unless it's a destructive reset.
4. **Polling Impatience**: Short timeouts caused failed generations.
   - *Lesson*: Use backoff logic and patient polling for long-running jobs.

## 📜 Full Change History
*See previous `PROJECT_CHANGES.md` and `MISTAKES_AND_FIXES.md` for historical context.*
