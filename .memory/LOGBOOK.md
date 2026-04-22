# LOGBOOK: The Living Ledger

This room tracks the chronological evolution of the Aether / ImgnAI project.

## 📈 Timeline

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
