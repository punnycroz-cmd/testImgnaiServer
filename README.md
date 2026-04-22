# Aether Server

This repository contains the backend and project docs for Aether / ImgnAI generation.

## 🏠 The Memory House (Start Here)

This project uses the **Memory House** system (Spatial Context) for agentic efficiency. If you are an AI agent, start by reading these rooms:

- [**ATLAS**](.memory/ATLAS.md): The project map and high-level structure.
- [**ENGINES**](.memory/ENGINES.md): Deep dive into Day and Star generation logic.
- [**LOGBOOK**](.memory/LOGBOOK.md): History of changes, fixes, and lessons learned.
- [**DEPLOYMENT**](.memory/DEPLOYMENT.md): Deployment and infrastructure guide.

## Main Runtime Files

- [`main.py`](/Users/sema/Documents/code/work/testImgnai/main.py)
- [`config/models.py`](/Users/sema/Documents/code/work/testImgnai/config/models.py)
- [`config/schemas.py`](/Users/sema/Documents/code/work/testImgnai/config/schemas.py)
- [`core/db.py`](/Users/sema/Documents/code/work/testImgnai/core/db.py)
- [`core/vault.py`](/Users/sema/Documents/code/work/testImgnai/core/vault.py)
- [`engines/day.py`](/Users/sema/Documents/code/work/testImgnai/engines/day.py)
- [`engines/day_api_client.py`](/Users/sema/Documents/code/work/testImgnai/engines/day_api_client.py)
- [`engines/star.py`](/Users/sema/Documents/code/work/testImgnai/engines/star.py)
- [`engines/star_client.py`](/Users/sema/Documents/code/work/testImgnai/engines/star_client.py)

## Frontend

- [`public/index.html`](/Users/sema/Documents/code/work/testImgnai/public/index.html)

## Core Infrastructure
- **FastAPI Backend**: Fully asynchronous architecture for non-blocking I/O (DB, Vault, APIs).
- **Postgres (Neon)**: Persistent storage for every generation manifestation and image vault metadata.
- **R2 Vaulting**: Permanent storage for generated images on Cloudflare R2, bypassing ephemeral session expiries.
- **Async DB Migration**: Uses `psycopg_pool` (AsyncConnectionPool) for high-concurrency database access.

## Frontend: Aether Elite Dashboard
- **Progress Matrix**: Real-time diagnostic bar for tracking Manifestation stages (*Link -> Auth -> Weave -> Vault*).
- **Metadata Inspector**: Full "Prophecy Panel" revealing prompts, models, and seeds for every historical image.
- **Deep Cloning**: "Invoke Again" feature to instantly copy settings from the vault back into the generator.
- **Infinite Scroll**: Seamless history exploration without manual pagination.
- **Mobile Bottom Navigation**: Dedicated floating tab bar for Forge, Queue, and Vault access on small screens.
- **UX Automation**: Intelligent console expansion/minimization and tab-switching logic for optimal viewport usage.

## Required Environment Variables
Set these in your local `.env` or Replit Secrets:
- `IMGNAI_USERNAME` / `IMGNAI_PASSWORD`: ImgnAI credentials.
- `DATABASE_URL`: Neon / Postgres connection string.
- `R2_ACCESS_KEY` / `R2_SECRET_KEY`: Cloudflare R2 tokens.
- `R2_VAULT`: (Internal) Identifier for the vault bucket.

---
*If you are an agent, start with [Memory House LOGBOOK](.memory/LOGBOOK.md) to see the latest fixes.*
