# ENGINES: Generation Mechanics

This room details how the server interacts with the upstream generation engines.

## ☀️ The Day Engine (`realm=day`)

The Day engine is based on a CLI-style automation.

- **Wrapper**: [`engines/day.py`](../engines/day.py)
- **Client**: [`engines/day_api_client.py`](../engines/day_api_client.py)
- **Mechanism**:
  - Subprocess execution of the client.
  - Periodic polling of task IDs.
  - JSON-line feedback for session and task state tracking.
- **Auth**: Uses cookies stored in `cookie/imgnai_cookie.json`.

## ⭐️ The Star Engine (`realm=star`)

The Star engine (formerly `imaginered`) uses browser-based automation via Playwright and direct HTTP API requests.

- **Wrapper**: [`engines/star.py`](../engines/star.py)
- **Helpers**: [`engines/star_client.py`](../engines/star_client.py)
- **Mechanism**:
  - Playwright for login and age-gate handling.
  - Token extraction (cookies, localStorage, session) for subsequent API requests.
  - Patient polling with backoff logic.
- **Auth**: Uses cookies stored in `cookie/imaginered_cookie.json`.

## ⚙️ Model Catalog

All models for both engines must be synchronized in [`config/models.py`](../config/models.py). Addition of new models requires updating both the `MODEL_CONFIGS` and the frontend lists in `index.html`.
