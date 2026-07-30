# Milestone 1 — Auto-generated encryption key

**Status:** Done

## In plain terms

Every key you save through the Settings page gets scrambled before it's
written to the database — so if anyone ever got into the database directly,
they couldn't just read your keys in plain text. That scrambling needs its
own secret "master key" to work.

Instead of asking you to create that master key yourself (a manual setup
step you'd have to do once, in a terminal, before anything else would
work), AION now makes one automatically the very first time it's needed,
and remembers it. Think of a padlock that manufactures its own key the
first time you use it, and keeps a spare locked away safely — you never see
it, never type a command for it, never touch a file for it.

## Technically

In `apps/api/app/services/token_encryption.py`, the function that builds
the scrambling tool (`_fernet()`) used to *require* a value called
`token_encryption_key` to already exist in the `.env` file, or it raised an
error. It now tries that first — so setting `TOKEN_ENCRYPTION_KEY`
explicitly still works and takes priority, which matters for a real
deployment (see the note below) — and if it's not set, falls back to a
small file on disk, `apps/api/.local_secret_key`, created automatically on
first use with `cryptography.fernet.Fernet.generate_key()`. That file is
listed in `.gitignore` so it's never accidentally committed or shared.

### Why this matters for a VPS or container deployment

A locally auto-generated key file only exists on the machine that created
it. If AION is deployed to a VPS, and later redeployed, rebuilt, or moved
to a fresh container, a file that isn't part of the deployment's persistent
storage can disappear — and if it does, every secret encrypted with it
becomes permanently unreadable (there's no way to "recover" a scrambled
value without the exact key that scrambled it).

The escape hatch already built into this design handles that: set
`TOKEN_ENCRYPTION_KEY` explicitly in the server's environment for any real
deployment, and the auto-generated file is never even created. A warning is
logged the first time the auto-generated fallback is actually used, calling
this out directly, so it's hard to miss during setup.

## Verified by

`apps/api/tests/test_token_encryption.py` — covers falling back to the
auto-generated key, creating the file on first use, reusing it on later
use, and an explicit `TOKEN_ENCRYPTION_KEY` taking priority over the file.
