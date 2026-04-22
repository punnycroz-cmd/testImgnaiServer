# Aether Studio Agent Guide 🛰️🕵️‍♂️

This guide defines the mandatory working protocols for all AI agents entering the Aether Studio workspace.

## 🛠️ Mandatory Completion Protocol
**Before ending any session, if logic or UI was modified, you MUST:**

1.  **Update `.memory/LOGBOOK.md`**: Add a timestamped entry describing what was changed, fixed, or broken.
2.  **Verify `README.md`**: Ensure it reflects any new features, environment variables, or infrastructure.
3.  **Stability Check**: If you modified the Day or Star engines, confirm that Cloudflare bypass logic remains intact.
4.  **Sync Manifest**: Update `.memory/ATLAS.md` if new files were added to the architecture.

## 🏁 Development Strategy
- **Day Engine**: Must stay as a Synchronous Subprocess (`day_api.py`) to maintain Cloudflare bypass.
- **Star Engine**: Can operate asynchronously.
- **Frontend**: All major UI logic is in `public/index.html`. 

---
*Failure to update the LOGBOOK is considered a breach of the Aether Stabilization Protocol.*
