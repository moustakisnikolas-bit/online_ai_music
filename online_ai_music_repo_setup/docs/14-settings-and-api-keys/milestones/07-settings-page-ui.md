# Milestone 7 — The Settings page itself

**Status:** Done

## In plain terms

A new section at the very top of AION's main page — before everything
else, since setting up your keys comes before using them — with one row
per key (YouTube Client ID, YouTube Client Secret, Replicate API Token,
OpenRouter API Key). Each row has a box to paste the key into, a Save
button, a Clear button, and a badge showing whether it's currently
**Saved**, **Using .env**, or **Not set**. A **Connect YouTube channel**
button sits below the rows.

Clicking Connect sends you to Google's own approval screen; after you
approve (or decline), you land back on this page with a plain-language
banner saying whether it worked.

## Technically

New section added to `apps/api/app/web/index.html`, placed first (existing
sections 1–4 renumbered to 2–5), matching the existing look exactly — same
dark theme, same button and badge conventions already used elsewhere on
the page (`.library-row`, `.badge`), plus three new badge color variants
(`.badge-database`, `.badge-environment`, `.badge-unconfigured`) and a
small `.secret-row-controls` layout for the input/Save/Clear row.

New JavaScript, following the page's existing patterns:

- `loadSecretStatuses()` — fetches `GET /api/v1/settings/secrets` and
  renders one row per key via `renderSecretRow()`.
- Save/Clear handlers on each row call `PUT` / `DELETE
  /api/v1/settings/secrets/{key}` and re-render on success. The input is
  always cleared after a successful save and never pre-filled with a real
  value — the app never echoes a saved key back to the browser.
- `connectYouTube()` — fetches `GET /api/v1/publishing/youtube/authorize`
  and navigates the browser to the returned Google authorization URL.
- `refreshYouTubeConnectionStatus()` — fetches
  `GET /api/v1/publishing/youtube/status` and shows "Connected: ..." or
  "Not connected" next to the Connect button.
- `showYouTubeConnectNotice()` — reads `?youtube_connect=success` or
  `?youtube_connect=error&reason=...` from the URL (left there by the
  callback redirect from [milestone 6](06-fix-youtube-callback.md)),
  shows a plain-language banner, then cleans the URL so the banner doesn't
  reappear on refresh.

## Verified by

Started the API server locally and confirmed live: the page serves with
the new section present, `GET /api/v1/settings/secrets` returns all four
keys as unconfigured on a clean database, saving a value via the API
updates its status without a restart, and the OAuth callback redirects to
`/app` with the expected query parameters for the "no parameters" case.
