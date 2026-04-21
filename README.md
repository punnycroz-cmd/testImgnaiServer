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

## High-Level Summary

- Replit hosts the backend API.
- Render hosts the frontend.
- Neon stores generation state and history.
- Cloudflare R2 stores vaulted images.
- Frontend requests are routed through `request_id` and `realm`.

## Required Environment Variables

Set these before running the backend:

- `IMGNAI_USERNAME`
- `IMGNAI_PASSWORD`
- `DATABASE_URL`
- `R2_ACCESS_KEY`
- `R2_SECRET_KEY`
- `PORT` (optional, defaults to `8080`)
- `LOG_LEVEL` (optional, defaults to `INFO`)

## Notes For New Agents

- Pull the latest `main` branch before making changes.
- Read `AGENT_GUIDE.md` first if you need the file map.
- Read `DEPLOYMENT.md` if you need to understand Render vs Replit.
- Use `request_id` for retries, not `client_id`.
