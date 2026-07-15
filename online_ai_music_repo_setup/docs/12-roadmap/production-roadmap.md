# AION Production & Monetization Roadmap

## Purpose

This roadmap sequences the work needed to take AION from an ambient-audio
engineering MVP to a fully functional tool that generates, packages, and
auto-publishes monetizable tracks to YouTube and, through a distributor, to
Spotify, Apple Music and Amazon Music.

It supersedes phases 4-6 of `mvp-completion-plan.md` with a more detailed
sequence that reflects the current codebase and the monetization goal.

## Milestone 0: Repository Hygiene

Goal: stop the repository from growing unmanageable before more factories
and features get added.

- Add a root `.gitignore` (virtualenvs, `__pycache__`, `.pyc`, `.DS_Store`,
  `.env`, build artifacts).
- Untrack committed virtualenvs (`.venv`, `.venv-python-3.9-...`) and all
  `__pycache__` / `.pyc` files.
- Untrack generated runtime output committed under `data/generated/`
  (sample WAV/PNG/ZIP files that should be produced at runtime, not stored
  as source).
- Decide the fate of `.aion/backups/` (per-update file snapshots that
  duplicate what git history already preserves), `zips/`, and
  `unzipped_folders/` (raw AION update drops at the repo root).
- Add a GitHub Actions CI workflow that runs the test suite on every push.

Definition of done: tracked file count reflects source only; `git status`
stays clean after a fresh `pip install` and a normal generation run; CI runs
pytest on push.

## Milestone 1: Multi-Layer Audio Engine

Goal: let a single track combine an arbitrary number of sound layers,
instead of the current fixed slots (one noise + tone layers + one texture).

- Generalize `MIXED_AMBIENT` (`audio/types.py`, `services/audio_generator.py`,
  `audio/dsp.mix_tracks`) from fixed noise/tone/single-texture slots to an
  ordered list of layers, each with its own source type, gain, and optional
  pan.
- Extend the request schema (`schemas/audio.py`) to accept a
  `layers: list[LayerSpec]` covering mixed layer types (tone, noise,
  texture, sample-based sound).
- Update `test_mixed_ambient.py` for N-layer combinations.

Definition of done: one API request can combine, for example, brown noise +
two tone layers + rain + ocean waves in a single generated track.

## Milestone 2: Natural Sound Sample Library

Goal: natural sounds that actually sound natural, instead of synthesized
approximations.

- Source and license a small library of seamless-loop nature recordings
  (rain, ocean, forest/birds, fire, wind, thunder, night ambience).
- Add a sample-based layer type that loads, loops, time-stretches if
  needed, and crossfades a source file into the mix.
- Store licensing/attribution records per sample, consistent with the
  compliance-first principle in `docs/01-product/vision.md`.

Definition of done: at least five natural sound types are available as
mixable layers, each with a recorded, verifiable commercial license.

Status: engine done, content not sourced yet (by design -- see below).
Added a `sample` ambient layer kind alongside noise/tone/texture: loads a
WAV file, downmixes to mono, resamples if needed, and loops it to fill
the requested duration, mixable with any other layer type. A manifest at
`apps/api/data/sample_library/manifest.json` tracks each sample's id,
category, filename, and license/source, with a
`GET /audio/samples` endpoint reporting which entries actually have their
audio file present (`available: true/false`).

Chose CC0/public-domain sourcing after reading actual license terms (not
marketing copy) from Soundsnap, Sonniss, Pro Sound Effects, A Sound
Effect, and Epic Stock Media: all of them explicitly prohibit using their
content as the primary element of a sold/streamed product -- language
like "primarily a sound product... soundscape albums" is a directly
targeted restriction, not fine print. CC0 is the only sourcing path
that's safe by construction, since there's no license to violate.

This can't be automated from here: sourcing real CC0 recordings means
browsing a catalog (e.g. Freesound filtered to CC0) and verifying the
license per file, which needs either human judgment or API credentials
neither of which exist in this environment. The five manifest entries
committed are placeholders demonstrating the format (ocean, forest birds,
campfire, thunderstorm, night crickets) -- all `available: false` until
real files are added. Full curation workflow in
docs/06-factories/natural-sound-sample-library.md.

Known limitation: looping is simple repeat-and-trim, not a crossfaded
seam, so a source recording that doesn't already loop cleanly will have
an audible seam. Worth revisiting once real samples are in place and the
seam is actually audible to judge against.

## Milestone 3: Engine Performance (numpy rewrite)

Goal: generation speed that can sustain a real publishing cadence.

- Introduce numpy as a dependency; vectorize `dsp.py` (sine/noise/texture
  generation, mixing, fades, normalization). Current generation is
  pure-Python, per-sample, which does not scale to production volume.
- Benchmark before and after on a 60-minute stereo render.
- Keep existing function signatures and tests passing; this is an internal
  rewrite, not an API change.

Definition of done: a 60-minute stereo track renders in seconds, not
minutes.

Status: done for the direct (non-chunked) generation path. A 4-layer
60-minute stereo `mixed_ambient` render went from 320.8s to 27.2s (numpy
vectorization plus streaming layer mixing, so only one layer's array is
held in memory at a time instead of all of them at once, which was the
actual bottleneck on memory-constrained machines). Two follow-ups remain
open, deliberately deferred rather than rushed:

- `long_form_audio.py` (the `long_form=True` chunked renderer, meant for
  genuinely long, memory-bounded output) is untouched and still uses a
  per-sample Python loop; it needs its own pass, particularly to carry
  brown-noise filter state correctly across chunk boundaries.
- Pink noise's 6-section parallel filter bank (6 sequential `lfilter`
  calls) is the dominant remaining cost at longer durations; combining it
  into a single higher-order filter would speed it up further but needs
  care to avoid silently changing its frequency response.

## Milestone 4: YouTube Publishing Integration

Goal: auto-upload generated video packages to a connected YouTube channel.
This is achievable directly — YouTube's Data API v3 supports authenticated
video uploads to a channel you own.

- Implement an OAuth2 connection flow for a YouTube channel and store
  credentials per workspace.
- Wrap `videos.insert` using the metadata and video package already
  produced by `services/video_package.py`.
- Enforce the human-approval gate from `vision.md`: uploads only fire once
  review status is approved.
- Track upload status back onto the catalog entry
  (queued / uploaded / failed + resulting video URL).

Definition of done: an approved catalog entry can be published to YouTube
through one authenticated action, end to end.

Status: implemented (OAuth connect/callback/status routes, resumable
upload via `videos.insert`, review-status gate tied to
`AudioJob.review_status == "approved"`, uploads default to
`privacy_status=private` so a human still reviews on YouTube itself before
anything goes public). Known gaps, called out rather than silently left:

- Not runnable end to end in this environment: there is no live Postgres
  here, and (like the pre-existing `review.py` / `audio_jobs.py` routes)
  the DB-backed parts of this feature have no test coverage against a real
  database. Everything mockable (OAuth URL construction, the
  approval/completion guard, the resumable-upload call, channel lookup,
  request schema validation) has unit tests; the wiring through
  `Depends(get_db)` does not.
- OAuth `state` is generated and required round-trip, but not validated
  against a server-side session store (none exists yet), so it is not a
  complete CSRF defense on its own.
- While adding the migration, found the existing chain is already broken:
  `0007_add_audio_review_workflow.py` declares `down_revision = "0006"`,
  but no `0006` migration file exists in the repo. Not introduced by this
  change; left as-is rather than silently patched over, and worth fixing
  before anyone relies on `alembic upgrade head` against a real database.

## Milestone 5: Distributor Integration (Spotify / Apple / Amazon)

Goal: get tracks onto streaming platforms that pay per stream. None of
these platforms accept direct API uploads from individual developers —
there is no public "publish a track" endpoint on Spotify's API. The only
path in is through a distributor.

- Evaluate distributors with real B2B ingestion APIs (for example
  Revelator, FUGA, SoundOn) versus consumer distributors with no API access
  (DistroKid, TuneCore, CD Baby) that would require manual upload instead.
- Pick one distributor and implement its release-submission API (metadata,
  ISRC/UPC, audio delivery, artwork delivery).
- Extend the catalog/review schema with distributor-specific required
  fields.

Definition of done: an approved catalog entry can be submitted to the
chosen distributor via API, with resulting per-platform status tracked
back into the catalog.

Status: decided, not built. Researched actual license/API terms (not just
marketing pages) across DistroKid, TuneCore, CD Baby, FUGA, Revelator,
SoundOn, RouteNote, LabelGrid, and ToneGrid. Findings:

- DistroKid and CD Baby have no public API; TuneCore only offers an
  enterprise partner API. FUGA and Revelator have real APIs but require
  enterprise sales, and both were acquired by major labels in early 2026
  (FUGA by UMG/Virgin, Revelator by Warner) -- a worse fit for a small
  independent operation, not a better one.
- Neither Spotify nor Apple Music accept direct artist uploads under any
  circumstances; both require an approved distributor. This is a platform
  trust/business relationship, not a technical API gap -- no open-source
  tool can substitute for it.
- LabelGrid is the one option with genuine self-service API access: public
  docs, a sandbox, no sales calls. $119/mo+ for API/automation tiers.
- RouteNote is free (0 upfront, 85/15 royalty split) and reaches Spotify/
  Apple Music/Amazon Music, but has no API at all -- manual dashboard only.
- ToneGrid looks like a cheaper API-first alternative to LabelGrid but
  entered public beta in April 2026 with no disclosed pricing yet --
  unproven, worth revisiting later, not a decision-ready option now.

Chosen: publish manually through RouteNote for now rather than pay for
LabelGrid automation. This means the auto-upload goal for Spotify/Apple/
Amazon is deliberately deferred -- YouTube (Milestone 4) remains the only
automated publishing path until this is revisited.

Revisit trigger (explicit, not vague): build the LabelGrid automation once
monthly income from this project exceeds 2x LabelGrid's monthly API cost
($119/mo Starter tier as of this writing) -- i.e. roughly $238/mo. Below
that, the cost of automating isn't justified by the manual workload it
would save.

## Milestone 6: Catalog & Release Pipeline UX

Goal: turn the current single-page generation form into a content
management experience.

- Add a library view: a grid or list of generated tracks with artwork
  thumbnail, duration, and status.
- Add a persistent audio player that keeps playing while browsing, similar
  to a standard streaming-app player bar.
- Add a release-status pipeline view (draft -> generated -> reviewed ->
  published, per connected platform).

Definition of done: a user can see every track's status across every
connected platform from one screen.

Status: partially done. While scoping this, found that the web UI's
"Generate audio" flow called the stateless `/audio/generate` endpoint,
which never wrote a database row -- meaning nothing generated through the
actual UI was reviewable or publishable, independent of anything else in
this roadmap. Fixed by adding `POST /audio/generate-and-catalog` (same
synchronous generation, reusing the existing service, plus a persisted
`AudioJob` row) and pointing the UI at it instead. Added a Library section
to `index.html`: lists tracks with status/review badges, an inline audio
player, and Approve/Reject buttons wired to the existing review endpoints.

This was verified against a real Postgres for the first time (previously
impossible in this environment -- see the Milestone 4 status note), via a
throwaway local container, not just unit tests: generated a multi-layer
`mixed_ambient` track through `/generate-and-catalog`, confirmed it
appeared in `GET /audio/jobs`, and confirmed approving it flips
`review_status`. Also caught and fixed a real bug along the way: `filename`
on both `AudioGenerationResponse` and `AudioJobResponse` was a plain
`@property`, which Pydantic v2 does not include in JSON output without
`@computed_field` -- it was silently serializing as absent. The frontend
had never hit this because it happened to derive the filename manually
instead of using the field.

Not done: no per-track "publish to YouTube" action in the library yet. The
library only has one platform's worth of connection (YouTube) implemented
and no per-job video file association, so wiring a publish button in
means deciding how a track's audio, video, and artwork tie together as one
release -- that's a real design question (see Milestone 5/7), not a small
addition, so it's left open rather than half-wired.
Mixed_ambient jobs created via `/generate-and-catalog` don't persist their
ambient_layers configuration (no column for it yet -- see the repository
docstring); the catalog only needs the output file and descriptive fields
to display and review, not the exact layer recipe.

## Milestone 7: Visual Polish

Goal: a UI that reads like a real product, not an internal test form.

- Waveform preview/scrubber before export.
- Cover-art picker/preview inline with generation.
- Visual system refinement: consistent spacing, typography, iconography,
  informed by mainstream streaming-app UI patterns.

Definition of done: subjective; validate side by side against a mainstream
streaming app and a video platform's creator studio as reference points.

Status: the three concrete items are implemented:

- Waveform preview/scrubber: client-side decode (Web Audio API) of the
  generated track, drawn to a canvas, with click-to-seek and a moving
  playhead.
- Artwork picker: a "Preview artwork" button generates a real preview with
  a random seed before the full workflow runs; clicking again previews
  another variation. The previewed seed is reused for the actual
  generation, so what was previewed is what you get, rather than the
  preview being disconnected from the final result.
- While building this, found that Milestone 6's per-row `<audio>` players
  broke the moment the library list re-rendered (e.g. after Approve),
  since destroying and rebuilding the row destroyed the element that was
  mid-playback. Replaced per-row players with a single persistent bottom
  player bar (play/pause, seek, elapsed/total time) that lives outside the
  re-rendered list -- this is also literally what Milestone 6's original
  "persistent audio player" ask was, which the per-row approach only
  partly satisfied.

Verified: JS syntax-checked (`node --check`), full pytest suite green
(62/62), and confirmed via TestClient that the served page contains every
new element the script depends on. Not verified: actual in-browser
behavior (waveform rendering, click-to-seek accuracy, playback). There is
no browser automation available in this environment, so this could not be
clicked through -- said explicitly rather than claiming a level of
verification that didn't happen.

Not done: the broader "visual system refinement" (typography, spacing,
iconography pass informed by mainstream streaming-app patterns) beyond
what these three features needed. That's genuinely subjective/open-ended
work best done with visual feedback in hand, i.e. after someone has
actually looked at this in a browser -- doing a large speculative
CSS pass with no way to see the result risked making it worse, not
better.

## Sequencing Notes

- Milestones 0-3 are engine and foundation work and can proceed without any
  platform credentials.
- Milestone 4 (YouTube) only needs a standard OAuth app and can start
  immediately after Milestone 1.
- Milestone 5 (distributor) requires a business decision, and possibly a
  partner agreement, before any code is written against it.
- Milestones 6-7 (UX) intentionally come after the publishing pipeline
  exists, so the UI reflects a real release workflow instead of being
  redesigned twice.
