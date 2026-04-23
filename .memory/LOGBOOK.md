# LOGBOOK: The Living Ledger

This room tracks the chronological evolution of the Aether / ImgnAI project.

## 📈 Timeline

### [2026-04-22 16:10] 📱 Mobile UX & State Synchronization Overhaul
- **Mobile Bottom Navigation**: Implemented a floating, glass-morphism bottom tab bar (Forge, Queue, Vault) for seamless one-handed control on mobile devices.
- **UX Automation & Magic Transitions**: 
    - Auto-minimizes the console when switching to Queue/Vault on mobile to maximize content visibility.
    - Clicking "Manifest" or "Matrix" now automatically switches the tab back to "Forge" and expands the console.
    - Console auto-minimizes after generation starts (on mobile) to reveal the images.
- **Model List Synchronization**: Exhaustively synchronized the Frontend (`index.html`) and Backend (`models.py`) model orders to match the literal configuration sequences (Alphabetical for Day, Curated for Star).
- **Initialization Fix**: Stopped the "Forge" tab from auto-loading the last generated images on page refresh, providing a clean "New Session" feel while preserving work in the Queue.
- **Queue/Temple Center**: Upgraded the "Queue" tab with live 4-second polling and dynamic task cards (Spinners, Checkmarks, and "View Result" buttons).
- **Responsive Touch Targets**: Enlarged "Clear", "Paste", and "Oracle" buttons and implemented `min-h-[44px]` for all primary action buttons for better mobile accessibility.
- **DB Resilience**: Patched `core/db.py` to fix `SSL connection closed unexpectedly` errors (OperationalError). Added `check=AsyncConnectionPool.check_connection` and `max_idle=300.0` to the Neon connection pool.
- **Frontend Hotfix**: Resolved a UI "Freeze" where dropdowns and buttons were unresponsive when opened via the `file://` protocol. Added error guards to `apiFetch` and an initialization `try/catch` safety net.

### [2026-04-21 23:30] 🎲 The Infinite Matrix
- **Matrix Cast UI**: Added a dedicated Matrix comparison grid that automatically fires a prompt across all 24 models (in Day or Star realm).
- **Sequential Safety Check**: Verified that the backend uses an `asyncio.Lock()` (equivalent to Semaphore(1)), safely queueing all 24 database entries instantly but running exactly 1 Playwright/API context at a time to remain 100% undetected by Cloudflare bot mitigation.
- **Batch Polling**: Built a `/job-status-batch` endpoint in `main.py` that checks the neon database for 24 jobs in a single query, preventing the frontend from DDoS-ing the FastAPI server during a Matrix Cast.

### [2026-04-21 23:20] ✨ Creative UX Elements
- **Aether Canvas**: Added a `<canvas>`-based background particle system that renders floating motes of light. The particles dynamically recolor themselves based on the active Realm (Emerald for Day, Violet for Star), adding subtle life to the static dashboard.
- **Oracle's Dice**: Built a sleek "Oracle" button attached to the Prompt field. Clicking it rolls for a random, hyper-aesthetic demonstration prompt (and automatically configures high-quality settings) to instantly obliterate writer's block.

### [2026-04-21 23:10] 📱 Responsive Split-Pane Interface
- **Lightbox Overhaul**: Redesigned the `.bubble-image-reveal` modal into a professional desktop/mobile responsive split-pane component.
- **Dynamic Sidebar**: Moved metadata, clone actions, download buttons, and thumbnails into an elegant glass-paneled sidebar that scrolls independently of the image.
- **Enhanced Transitions**: Refined the scaling overlay transitions and active shadow states to build a more application-like UX for exploring images.

### [2026-04-21 22:50] 🎨 Elite Frontend Overhaul
- **Progress Matrix**: Implemented a 4-step real-time diagnostic bar (*Link -> Auth -> Weave -> Vault*) to visualize backend progress.
- **Prophecy Panel (Inspector)**: Added a deep metadata viewer for both current and historical manifestations, revealing prompts, models, and seeds.
- **Recursive Invocation (Cloning)**: Enabled "Invoke Again" functionality, allowing users to clone historical settings back into the Forge with one click.
- **Infinite Vault Scroll**: Replaced paginated "Load More" with a smooth infinite scroll listener for seamless history exploration.

### [2026-04-21 22:45] 🛡️ Stability Hybrid Rollback (Day Engine)
- **Cloudflare Resilience**: After failed attempts at parallel async browser polling, the **Day Engine** was rolled back to its stable **Synchronous Subprocess** runner.
- **Performance Trade-off**: Re-accepted the 15-20s launch cost for Day in exchange for 100% bypass reliability against Cloudflare's Managed Challenges.
- **Hybrid Architecture**: Kept the manager and DB calls async but wrapped the sync execution, maintaining server-wide non-blocking performance.

## ⚠️ Critical Mistakes & Lessons

1. **[Mistake] Parallel Browser Bursts**: Firing 4 status polls at the same millisecond in a browser environment triggers Cloudflare instantly.
   - *Fix*: Use sequential polling or jittered async for browser-based engines.
2. **[Mistake] Async Browser Detection**: Async Playwright patterns are more easily detectable than Sync ones in some environments.
   - *Fix*: Stick to Sync Playwright logic for "Hard" Cloudflare targets like Day.

### [2026-04-23 16:35] 🏛️ Vault Pagination Engine & Cache Obliteration
- **Recursive Vault Fetching**: Implemented a robust `advanceVaultLoad` engine that recursively consumes database pages until a full 20-item visual batch is filled, effectively bypassing thousands of "ghost" rows (corrupt/empty batches).
- **Cache Buster Implementation**: Added strict `Cache-Control: no-cache` headers and `_t=timestamp` query parameters to all `apiFetch` calls. This fixes a critical blocker where browsers (and Replit edge proxies) were serving stale Page 1 data during pagination sweeps.
- **Ghost & Duplicate Filtering**: Added frontend logic to skip items with 0 images and prevent ID collisions during multi-page sweeps.
- **Vault Diagnostics**: Added `console.group` tracing to the vault loop for real-time inspection of database quality (Valid vs Ghost vs Duplicate counts).
- **End-of-Vault Graceful Termination**: The "Load More" button now transitions to an "End of Vault" disabled state once the database is exhausted, preventing redundant network requests.
- **Extended Stats API**: Updated `/debug/vault-stats` to include a deep-inspect `valid_batches` count, separating database row counts from actual viewable manifests.

---
*Last Updated: 2026-04-23 16:35*
