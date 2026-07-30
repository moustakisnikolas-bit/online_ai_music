# Milestone 3 — Database-first, .env-fallback lookup logic

**Status:** Done

## In plain terms

When any part of AION needs a key (say, to talk to Replicate), it now asks
one question in order: "did the user save one through the Settings page?"
If yes, use that. If no, fall back to whatever's in the `.env` file (or
nothing, if that's empty too). This check happens fresh every single
time — nothing is cached — which is *why* saving a key through the Settings
page takes effect immediately. There's no "restart the app" step anywhere
in this flow.

## Technically

New file `apps/api/app/repositories/app_secrets.py`: plain database
read/write functions (`set_secret`, `delete_secret`, `get_secret_value`,
`is_secret_overridden`) scoped to a fixed list of `MANAGED_SECRET_KEYS` —
the four keys this feature manages, and the only key names this repository
will ever accept. This file only talks to the database, nothing external.

New file `apps/api/app/services/secrets.py`: the actual "database wins,
`.env` is the fallback" logic.

- `resolve_secret(db, key)` — returns the database-saved value if one
  exists and is non-empty, else the value from `.env`-backed settings
  (`get_settings()`). No caching of its own, unlike `get_settings()`'s
  `@lru_cache` (which is untouched by this feature — every other config
  value keeps working exactly as before).
- `secret_status(db, key)` — reports, per key, whether it's currently
  `"database"` (saved via the Settings page), `"environment"` (only in
  `.env`), or `"unconfigured"` (neither).
- `all_secret_statuses(db)` — the same, for every managed key at once
  (what the Settings page's status list is built from).

## Verified by

`apps/api/tests/test_secrets_service.py` — precedence (database beats
`.env`), each of the three status values, and that every managed key is
covered.
