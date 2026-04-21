# Aether Server

This repository contains the backend and project docs for Aether / ImgnAI generation.

## Start Here

- [`AGENT_GUIDE.md`](/Users/sema/Documents/code/work/testImgnai/AGENT_GUIDE.md)
- [`DEPLOYMENT.md`](/Users/sema/Documents/code/work/testImgnai/DEPLOYMENT.md)
- [`PROJECT_CHANGES.md`](/Users/sema/Documents/code/work/testImgnai/PROJECT_CHANGES.md)
- [`MISTAKES_AND_FIXES.md`](/Users/sema/Documents/code/work/testImgnai/MISTAKES_AND_FIXES.md)

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
