# Milestone 5 — Save/status API endpoints

**Status:** Done

## In plain terms

The Settings page in the browser needs somewhere to send a pasted-in key
to, and somewhere to ask "what's currently saved?" — without ever getting a
real key back. For security, the app will only ever say "yes, this one's
saved" or "no, it's not," never the key's actual value.

## Technically

New file `apps/api/app/schemas/settings.py`:
`SecretUpsertRequest` (`{"value": "..."}`), `SecretStatusResponse`
(`{"key", "configured", "source"}`), `SecretStatusListResponse`
(a list of the above).

New file `apps/api/app/api/routes/settings.py`, registered in `main.py`
under `/api/v1`:

- `GET /settings/secrets` — status of all four managed keys.
- `PUT /settings/secrets/{key}` — save a value for one key. Rejects
  unrecognized key names with `404`.
- `DELETE /settings/secrets/{key}` — clear a saved value (falls back to
  `.env`, or to "unconfigured," depending what's there).

## Verified by

`apps/api/tests/test_settings_api.py` — full status list, save-then-status,
unknown-key rejection on both `PUT` and `DELETE`, delete-then-status
fallback. Also confirmed live: server started, all four keys showed
"not set up," a test value was saved and its status updated to "saved" with
no restart, then cleared back to "not set up."
