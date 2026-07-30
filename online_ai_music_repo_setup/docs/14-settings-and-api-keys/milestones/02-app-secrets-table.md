# Milestone 2 — Database table for saved keys

**Status:** Done

## In plain terms

A new, small "storage box" inside the database, specifically for the
scrambled keys you save through the Settings page — one entry per key
(YouTube Client ID, YouTube Client Secret, Replicate API Token, OpenRouter
API Key).

## Technically

New model `apps/api/app/models/app_secret.py` defines an `AppSecret` table
(`app_secrets`): an id, a `key` name (e.g. `"replicate_api_token"`, unique),
the encrypted value, and a last-updated timestamp. Registered in the two
places this project already lists every model
(`apps/api/app/models/__init__.py` and `database/migrations/env.py`).

New migration `database/migrations/versions/0014_add_app_secrets.py`
(revision `0014`, following `0013`) creates the table and a unique index on
`key`, with a matching `downgrade()`. Applied to the project's real
database the same way as every earlier migration.

## Verified by

`apps/api/tests/test_app_secrets_repository.py` — CRUD operations, a real
encryption round-trip, upsert behavior (saving the same key twice updates
rather than duplicates), and rejection of unknown key names.
