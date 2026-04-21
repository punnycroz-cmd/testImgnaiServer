# Mistakes And Fixes

This document records the main mistakes we made during the refactor and how we fixed them. The goal is to help future agents avoid repeating the same issues.

## 1. Routing By `nsfw` Instead Of `realm`

### Mistake
- We initially used `nsfw` to decide whether the backend should run Day or Star.
- That worked loosely at first, but it made the logs confusing and allowed the frontend to say one thing while the backend executed another.

### Fix
- We switched routing to use `realm` first.
- `realm = "day"` now routes to Day.
- `realm = "star"` now routes to Star.
- `nsfw` only remains as a fallback compatibility signal.

### Lesson
- Use one explicit field for mode selection.
- Do not let a UI flag silently control the wrong business path.

## 2. Frontend And Backend Model Lists Drifted Apart

### Mistake
- The frontend only showed a short demo list of models.
- The backend had larger Day and Star model catalogs.
- This caused users to select a model in the UI that did not map correctly in the backend.

### Fix
- We restored the full Day model catalog.
- We restored the full Star model catalog.
- We kept the frontend and backend catalogs aligned in `config/models.py`.

### Lesson
- Model names must be a shared source of truth.
- If the backend supports a model, the frontend should not invent or hide it.

## 3. Star Model Fallback To `Gen`

### Mistake
- The Star backend originally only knew about a small subset of models.
- When a model like `Illustrious` was selected, the code fell back to `Gen` silently.

### Fix
- We expanded `STAR_MODEL_CONFIGS` to include the full Star set.
- This removed the silent fallback for valid Star models.

### Lesson
- Do not silently fall back unless that behavior is intentional and visible.
- Missing catalog entries should be treated as a configuration problem.

## 4. Auth Token Detection Was Too Narrow

### Mistake
- We initially looked for a token in only one or two places.
- The Imagine.red auth state was stored in a more complex shape than expected.
- Some token extraction code also lacked the right import or decoding step.

### Fix
- We added broader token discovery:
  - cookies
  - localStorage
  - sessionStorage
  - network requests
- We decoded cookie values before parsing.
- We added recursive token-path debug output.

### Lesson
- Session storage formats can change.
- Always add debug output before making assumptions about hidden auth state.

## 5. Age Gate Was Missed

### Mistake
- The Star login flow did not explicitly handle the 18+ gate.
- That could block login even when credentials were correct.

### Fix
- We added age-gate detection and click handling around the Star login flow.
- We also added screenshots around the age-gate steps.

### Lesson
- If a site has modal gates or age checks, treat them as part of the login flow.
- Capture screenshots around each critical step.

## 6. Login Debugging Was Too Blind

### Mistake
- When login failed, we did not have enough visibility into what happened.
- It was hard to tell whether the page was at login, generate, age-gate, or a logged-in state.

### Fix
- We added step-by-step screenshots:
  - page load
  - login page
  - filled form
  - after Enter
  - after redirect
  - post-login state
- We also added safe debug logging for cookies and storage keys.

### Lesson
- When dealing with browser automation, screenshots are often more useful than logs alone.

## 7. History Recovery Used Local JSON Files

### Mistake
- The early version depended on local JSON files for recovery and history.
- That broke across machines and did not scale well.

### Fix
- We moved history and state into Neon.
- We now store:
  - `request_id`
  - `session_uuid`
  - `task_uuids`
  - final image URLs

### Lesson
- Do not keep important recovery state only on the local filesystem.

## 8. R2 Naming Was Inconsistent

### Mistake
- Day and Star initially used different naming styles for uploaded images.
- That made it harder to trace a batch.

### Fix
- We standardized naming around:
  - timestamp
  - realm
  - session UUID
  - task UUID
- Images from the same generation are grouped together in one folder prefix.

### Lesson
- Naming should reflect the actual generation identity, not just a random filename.

## 9. Frontend Recovery Used The Wrong Identifier

### Mistake
- The frontend originally tried to recover by `client_id`.
- That is a user label, not a generation resume token.

### Fix
- We introduced `request_id` as the retry/resume handle.
- The frontend now stores and reuses it.

### Lesson
- User labels and retry tokens are not the same thing.

## 10. Tokenized Polling Needed More Time

### Mistake
- We treated polling as if it would always finish within a short timeout.
- In reality, some generations, especially higher quality ones, take longer.

### Fix
- We added retry/backoff logic.
- We made polling more patient and allowed resume polling through the saved generation state.

### Lesson
- Long-running generation jobs need resilient polling, not one-shot requests.

## 11. Frontend Controls Kept Getting Reset

### Mistake
- Mode switches re-rendered dropdowns and reset the selected values.

### Fix
- We preserved model, quality, and aspect selections when switching modes.
- We also stored those selections in localStorage.

### Lesson
- Re-rendering UI controls should not wipe user intent.

## 12. Vault Clicks Did Not Open Anything

### Mistake
- Clicking a history group in the vault only flashed the tile.
- It did not open a viewer for the group.

### Fix
- We added a real image viewer for history groups.
- The modal now opens the first image and lets the user switch between thumbnails.

### Lesson
- A clickable UI should always have an obvious result.

## Overall Pattern

The biggest repeated lesson was:

- make the source of truth explicit
- log the hidden state
- persist the important IDs early
- avoid silent fallback
- match the frontend contract to the backend contract exactly

