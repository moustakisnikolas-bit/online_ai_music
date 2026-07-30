# Milestone 4 — Wiring existing features to use it

**Status:** Done

## In plain terms

Five different parts of AION each used to ask the `.env` file directly for
their key: the YouTube connector, the Replicate AI-artwork generator, the
Replicate instrumental-music generator, the OpenRouter metadata writer, and
the OpenRouter provider check. Each was changed to ask the new
"database-first, `.env`-fallback" logic instead — nothing else about how
they work changed.

## Technically

Added a `db: Session` parameter to:

- `services/provider_config.py` — `require_openrouter_key`
- `services/ai_artwork_generator.py` — `generate_ai_artwork` and its two
  internal Replicate/OpenRouter helpers
- `services/instrumental_generator.py` — `generate_instrumental_clip`
- `services/llm_metadata_generator.py` — `generate_llm_metadata_package`
- `services/youtube_publisher.py` — `build_authorization_url`,
  `exchange_code_for_credentials`, `credentials_from_stored`

Each now calls `resolve_secret(db, key)` (directly, or via
`require_openrouter_key`) instead of reading `get_settings()` for the key
fields specifically. Every *other* setting each of these functions uses —
model names, cost estimates, the YouTube redirect address — is untouched;
only the four secret fields moved over.

Each of these functions is already called from a route that has a database
session open, so this was threading one extra argument through existing
call chains, not a redesign. The four calling route files
(`catalog.py`, `samples.py`, `visuals.py`, `publishing.py`) were updated to
pass `db=db` at each call site.

## Verified by

Existing test files for each of the five services, updated with an
in-memory SQLite `db` fixture and the appropriate `get_settings` patches
for both the module under test and `app.services.secrets`. Full suite green
(`pytest`), `ruff` clean.
