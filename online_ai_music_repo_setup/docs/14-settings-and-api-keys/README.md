# Settings & API Keys

## What this is

A page inside AION itself — no text editor, no terminal — where you paste in
the outside keys AION needs (YouTube, Replicate, OpenRouter) and click Save.
The change works immediately. You never restart anything.

## Why it exists

Before this feature, connecting AION to an outside service meant opening a
file called `.env` in a code editor and typing a line like
`REPLICATE_API_TOKEN=...` by hand. That's a reasonable way to configure a
server, but not something you should have to do just to try out a feature.

Building this also uncovered a real bug: the "Connect your YouTube channel"
button was wired up in a way that could never actually finish connecting.
Google was sending your browser back to AION in one shape (a plain web
address with `?code=...&state=...` at the end), and AION was only listening
for a completely different shape (a background request with the same
information buried inside it). That mismatch is fixed as part of this same
piece of work — see [milestone 6](milestones/06-fix-youtube-callback.md).

## How to use it (as a non-technical user)

1. Open AION in your browser (`http://localhost:8000/app`, or wherever it's
   running).
2. At the very top of the page, under **"1. Settings — API Keys"**, you'll
   see one row per key: YouTube Client ID, YouTube Client Secret, Replicate
   API Token, OpenRouter API Key.
3. Each row has a badge showing its current state:
   - **Not set** — nothing configured yet. That feature is simply
     unavailable until you add a key; nothing breaks.
   - **Using .env** — a value exists in the server's `.env` file (set up by
     whoever deployed AION), but you haven't overridden it here.
   - **Saved** — you've saved a value through this page. It's now in use.
4. To add or replace a key: paste it into the box and click **Save**. The
   badge updates immediately.
5. To remove a key you saved here (falling back to `.env` if one exists
   there, or back to "not set" if not): click **Clear**.
6. To connect a YouTube channel: click **Connect YouTube channel**. You'll
   be sent to Google's own login/approval screen. Approve access, and
   you'll land back on this page showing "connected."

You never see your keys echoed back to you after saving — for security, the
app only ever tells you whether a key is set, never what it is.

## What's actually happening, in slightly more technical terms

Every key you save is scrambled (encrypted) before it's written to the
database, using a secret "master key" that AION generates and stores for
itself the very first time it needs one — you never have to create or
manage that master key yourself. See
[milestone 1](milestones/01-auto-encryption-key.md) for how that works, and
why it matters if AION is ever moved to a different server.

When any part of AION needs one of these keys (to call Replicate, to talk to
YouTube, and so on), it checks the database first, and only falls back to
`.env` if nothing's saved there. That check happens fresh on every single
use — nothing is cached — which is exactly why saving a key through this
page works right away, with no restart. See
[milestone 3](milestones/03-resolve-secret-logic.md) for the underlying
logic.

## Milestones

1. [Auto-generated encryption key](milestones/01-auto-encryption-key.md)
2. [Database table for saved keys](milestones/02-app-secrets-table.md)
3. [Database-first, .env-fallback lookup logic](milestones/03-resolve-secret-logic.md)
4. [Wiring existing features to use it](milestones/04-wire-up-existing-features.md)
5. [Save/status API endpoints](milestones/05-settings-api-endpoints.md)
6. [Fixing the YouTube "Connect" bug](milestones/06-fix-youtube-callback.md)
7. [The Settings page itself](milestones/07-settings-page-ui.md)
8. This documentation
