# LOGBOOK: The Living Ledger

This room tracks the chronological evolution of the Aether / ImgnAI project.

## 📈 Timeline

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

---
*Last Updated: 2026-04-21 23:05*
