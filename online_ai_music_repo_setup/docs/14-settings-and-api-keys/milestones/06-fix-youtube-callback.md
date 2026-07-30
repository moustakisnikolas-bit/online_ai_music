# Milestone 6 — Fixing the YouTube "Connect" bug

**Status:** Done

## In plain terms

When you click "Connect YouTube," Google shows its own login/approval
screen, then sends your browser back to AION to finish the connection. The
way AION was originally built to receive that "come back" step didn't
match how Google (or any OAuth2 provider) actually sends it — so the
handoff would have failed every time, even with valid credentials
configured. This was a real, pre-existing bug, found while designing the
Settings page — a "Connect YouTube" button that could never actually
connect wasn't worth shipping alongside it.

The mismatch: Google always redirects the browser with a plain `GET`
request, with the result in the web address itself
(`...?code=...&state=...`, or `...?error=...` if you declined). AION's
`/callback` route was built to expect a `POST` request with that same
information inside a JSON body — a shape no browser redirect ever
produces.

## Technically

In `apps/api/app/api/routes/publishing.py`, `/callback` changed from
`@router.post(...)` expecting a `YouTubeCallbackRequest` body, to
`@router.get(...)` reading `code`, `state`, and `error` as query
parameters — exactly what Google sends. After processing, it redirects the
browser with `RedirectResponse` to `/app?youtube_connect=success` on
success, or `/app?youtube_connect=error&reason=...` for any failure
(missing parameters, an invalid/expired state token, a provider-reported
`error`, or an exchange failure) — so the page can show a clear result
instead of leaving the user on a bare JSON response.

The `YouTubeCallbackRequest` schema (no longer used, since the endpoint
now reads query parameters instead of a body) was removed from
`apps/api/app/schemas/publishing.py`.

Everything that actually *does* the connecting — exchanging the code for
credentials, fetching the channel identity, saving the credential record —
was already correct and unchanged; only how the handoff itself is received
was wrong.

## Verified by

`apps/api/tests/test_publishing_api.py` — a bare `GET` (no params) reaches
the handler and redirects with a reason, rather than erroring as a
malformed request; a provider-reported `error` is reflected in the
redirect; an invalid/unissued state redirects with the correct reason; and
a full successful exchange (with the Google API calls mocked) redirects to
`success` and actually persists the YouTube credential. Also confirmed live
against a running server.
