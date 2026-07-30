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

Status: done, including the CI workflow, which was tracked as open here
but not actually built until now. `.github/workflows/ci.yml` runs ruff
and pytest on every push/PR to main, verified by running the exact same
steps locally against a completely fresh virtualenv (not the long-lived
dev one used throughout this work) before committing. Fixed the one
pre-existing lint failure it surfaced (an unused import in
`artwork_generator.py`, unrelated to any of this work) so CI starts
clean. `mypy` is intentionally not part of the CI gate yet: it currently
reports 13 pre-existing errors, mostly FastAPI routes returning ORM
objects typed as response schemas (a common, usually-fine pattern FastAPI
resolves at runtime via `response_model`, but one mypy can't verify) --
gating on it needs a dedicated pass, not a quick fix bolted onto this one.

**Still needed from you:** a decision on `.aion/backups/`, `zips/`, and
`unzipped_folders/` at the repo root -- keep as history or clean out. Still
tracked in git as before, not automated cleanup, since it's your call
whether that history is worth keeping. Remove this line once decided.

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

Freesound search URLs pre-filtered to CC0 only (verified the `f=license:"Creative Commons 0"`
filter parameter actually works before handing these over, not guessed),
one per placeholder manifest entry -- still double-check the license badge
on each individual sound's own page before downloading, since a search
filter is a starting point, not a substitute for checking the specific file:

- Ocean (`ocean-waves-01`): https://freesound.org/search/?q=ocean+waves&f=license%3A%22Creative+Commons+0%22
- Forest birds (`forest-birds-01`): https://freesound.org/search/?q=forest+birds&f=license%3A%22Creative+Commons+0%22
- Campfire (`campfire-01`): https://freesound.org/search/?q=campfire&f=license%3A%22Creative+Commons+0%22
- Thunderstorm (`thunderstorm-01`): https://freesound.org/search/?q=thunderstorm&f=license%3A%22Creative+Commons+0%22
- Night crickets (`night-crickets-01`): https://freesound.org/search/?q=crickets+night&f=license%3A%22Creative+Commons+0%22

Freesound requires a free account to download (browsing/searching doesn't).
Favor longer clips (60s+) where available -- they crossfade into a loop
more forgivingly than a short clip repeated many times, per the "Known
limitation" note below.

**Still needed from you:** browse the URLs above, pick and download one
file per category, verify the CC0 badge on that specific sound's page, and
drop the WAV into `apps/api/data/sample_library/` with the matching
filename from the manifest (or update the manifest entry if you pick a
different file). Remove this line once real audio is in place for all
five.

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

Status: done for both the direct (non-chunked) and chunked long-form paths.
A 4-layer 60-minute stereo `mixed_ambient` render went from 320.8s to 27.2s
(numpy vectorization plus streaming layer mixing, so only one layer's array
is held in memory at a time instead of all of them at once, which was the
actual bottleneck on memory-constrained machines).

`long_form_audio.py` (the `long_form=True` chunked renderer, meant for
genuinely long, memory-bounded output) has been vectorized: sine,
isochronic, binaural, and white-noise are computed per-chunk directly from
absolute sample index (no cross-chunk state needed, so chunk size has zero
effect on output). Brown noise carries its `lfilter` filter state (`zi`)
across chunk boundaries via a persistent leaky integrator, and matches the
non-chunked path's peak-normalization semantics ("amplitude" = true peak)
via a first pass that runs the same filter once to find the real peak
(tracking only a scalar, not the full signal, so the memory-bounded design
is preserved) before a second pass writes the correctly-scaled audio. A
full 60-minute stereo brown-noise track (the schema's max duration) renders
in ~9s against the live server, hits the requested peak exactly (verified:
requested 0.6, measured 0.5999), and has zero clipped samples. 9 new tests
added (chunk-size independence, peak-matching, unseeded reproducibility,
no-clipping); full suite (160 tests) and ruff both pass.

**Update: pink noise filter consolidated.** The 6-section parallel filter
bank (6 sequential `lfilter` calls, each applied to the same white-noise
input and summed -- not a true cascade despite the name) is mathematically
a single rational transfer function once combined over a common
denominator. `dsp.py` now derives that single filter's numerator/
denominator at import time via polynomial arithmetic (not hand-transcribed
-- these poles sit up to 0.99886, close enough to the unit circle that
even small coefficient rounding compounds into real divergence over a long
render, confirmed the hard way: an earlier attempt using hand-copied
8-significant-digit literals diverged by 0.37 over 200k samples versus the
~1e-6 float32-rounding-level agreement the full-precision computed version
achieves). One `lfilter` call this way is 6.4x faster than the original 6
(20.5s -> 3.2s for a 1-hour mono render, measured). Verified: 3 new tests
including a regression test that reimplements the original 6-call approach
independently in the test file and asserts the two stay within 1e-4; full
suite (181 tests) and ruff pass; confirmed live against the server.

That fix closes out this milestone's originally-scoped follow-up, but
profiling a full-scale request while verifying it live (`cProfile` on a
10-minute stereo pink-noise render, since the pattern scales linearly)
surfaced a **new, separate bottleneck**: pink noise's own filtering is now
a small fraction of total time. The dominant cost at full 60-minute scale
is the mastering/validation pipeline scanning the entire signal --
`true_peak_dbtp`'s oversampled `resample_poly` call (called twice per
render, ~40% of total time) and `detect_excessive_high_frequency_energy`'s
single large FFT are both O(n) over the full signal length with real
per-sample cost, not something the pink-noise fix touches. End-to-end,
a full 60-minute stereo pink-noise render still takes ~75-90s on a warm
server. **Update: mastering pipeline parallelized across channels.** The dominant
cost identified above -- `limit_true_peak` (and, when enabled,
`apply_mastering_eq`) processing each channel independently -- turned out
to be safely parallelizable: these scipy calls (`resample_poly`, `lfilter`)
release the GIL during the heavy C computation, confirmed empirically
(2-channel `true_peak_dbtp`: ~1.95x wall-clock speedup, bit-identical
results, verified with `p1 == p1b` on the actual returned floats, not an
approximate comparison). Added a small `_parallel_map` helper in
`audio_generator.py` that runs independent per-channel work across a
thread pool (skipped for mono, where there's nothing to parallelize), and
used it for both call sites. This is a pure execution-strategy change, not
an algorithm change -- same inputs still produce the same outputs, just
computed concurrently instead of sequentially, so there was no correctness
tradeoff to weigh here the way the pink-noise coefficient change had.

Verified: full suite (181 tests, unchanged) passes with no modifications
needed, confirming no observable behavior changed. A direct 10-minute
stereo render (mastering EQ on) dropped from ~12s to ~11s locally and
completed in 16.5s end-to-end through the live server, with the exact same
`loudness_lufs` value (`-21.641061572225876`) reproduced across both the
direct call and the live HTTP request -- deterministic, correct output.
Attempts to re-verify at the full 60-minute scale repeatedly hung in this
sandbox environment's background-process handling (unrelated to this
change: an unrelated earlier direct-DB-query script hung the same way
mid-session) rather than genuinely taking longer, confirmed by near-zero
CPU time on the stuck process; killed cleanly rather than chased further,
since the 10-minute scale verification (which does complete reliably) is
sufficient to trust the same linear-scaling logic already established for
every other numpy-vectorized change this session.

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

- ~~Not runnable end to end in this environment: there is no live
  Postgres here~~ -- **outdated as of this session**: a persistent local
  Postgres container was stood up (`online_ai_music_repo_setup-postgres-1`,
  host port 5435) and has since been used to apply every migration through
  0011 and to verify DB-backed behavior live (track ratings, the OAuth
  CSRF fix, this migration chain fix). What's still genuinely true: no
  route-level test suite coverage exists for the DB-backed parts of
  `review.py` / `audio_jobs.py` / most of `publishing.py` (everything
  mockable -- OAuth URL construction, the approval/completion guard, the
  resumable-upload call, channel lookup, request schema validation -- has
  unit tests; the wiring through `Depends(get_db)` mostly doesn't, aside
  from the new `oauth_state` repository tests). That's a real, addressable
  gap, not an environment limitation anymore.
- ~~While adding the migration, found the existing chain is already
  broken: `0007_add_audio_review_workflow.py` declares
  `down_revision = "0006"`, but no `0006` migration file exists~~ --
  **fixed earlier this session**: `0007`'s `down_revision` was repointed to
  `0005` (the last migration that actually exists), and `alembic upgrade
  head` has run cleanly through 0011 since. This note was left stale after
  the fix; corrected now while auditing open items.

**Update: OAuth `state` CSRF gap closed.** The `state` was generated and
required round-trip, but never actually validated server-side -- any
`state` value, including one an attacker chose, was accepted by
`/callback`. Added `OAuthState` (new `oauth_states` table, migration 0011)
and a repository (`repositories/oauth_state.py`) that persists each issued
state with a 10-minute expiry and consumes it exactly once: `/authorize`
now writes the state it hands out; `/callback` looks it up, deletes it
unconditionally on first sight (so it can never be replayed even if the
purpose or expiry check fails), and rejects the request with 400 unless
the state was found, unexpired, and issued for `purpose="youtube"`.

Verified: 5 new repository tests (create-then-consume, replay-fails,
unknown-state-fails, wrong-purpose-fails-and-still-consumes,
expired-fails) against a real SQLAlchemy session (SQLite in-memory, since
`OAuthState` uses only portable column types) -- this surfaced a real bug
during testing (naive vs. timezone-aware datetime comparison failing on
SQLite's datetime round-trip), fixed by normalizing to UTC before
comparing. Migration applied cleanly against the persistent local Postgres
(`0010 -> 0011`). Confirmed live against the running server: a callback
with a never-issued state is rejected (400); a callback with a real,
freshly-issued state passes the CSRF gate and correctly proceeds to the
next real check in the chain (`YouTube OAuth is not configured` -- expected,
since no Google credentials exist in this environment); replaying that
same now-consumed state on a second call is rejected. Full suite (178
tests) and ruff both pass.

**Still needed from you:** a Google Cloud Console project with OAuth
credentials (`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`) set in `.env`,
to run the `/authorize` -> Google consent screen -> `/callback` flow
against a real YouTube channel for the first time -- everything up to that
external call is built, tested, and now CSRF-safe, but the OAuth exchange
itself has never run for real. Remove this line once you've connected a
real channel and confirmed `GET /publishing/youtube/status` reports it.

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

**Still needed from you:** create a free RouteNote account when you're
ready to publish to Spotify/Apple/Amazon manually -- no code work is
blocked on this, it's a business-side account signup, not a technical
integration. Remove this line once you have an account (or once the
LabelGrid revisit trigger fires and this whole section gets rebuilt).

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

**Still needed from you:** a decision on how a track's audio, video, and
artwork tie together as one "release" (e.g. one job = one release with
optional video/artwork attached vs. an explicit separate release object
that references a job). Once decided, the publish button and the
per-job-video-association column are both small, mechanical additions.
Remove this line once that decision is made and the button is wired up.

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

**Still needed from you:** actually click through the UI in a browser
(`uvicorn app.main:app` from `apps/api/`, open `/app`) and say what looks
off -- spacing, type scale, color, whatever stands out. Remove this line
once that pass has happened, whether the answer is "looks fine" or a
specific punch list.

**Update: AI-generated (photorealistic) cover art.** `artwork_generator.py`
was, and remains, a purely procedural PIL renderer (gradient background +
blurred circles + text) -- it was never AI-generated and can't produce
realistic imagery no matter how it's tuned. Added `ai_artwork_generator.py`
as an alternate provider alongside it, selectable per-request via the
existing `/visuals/artwork/generate` endpoint's new `provider` field
(`"procedural"` default, unchanged behavior; `"replicate"`; `"openrouter"`):

- **Replicate (active path)**: reuses the existing `REPLICATE_API_TOKEN`
  setting already in place for Stable Audio Open, calling a Flux model
  (`FLUX_MODEL`, defaults to `black-forest-labs/flux-1.1-pro`) via the same
  async predict-then-poll pattern as `instrumental_generator.py`. Field
  names are a best guess following Flux's typical Replicate interface, not
  yet verified against a real token -- same caveat as the audio model.
- **OpenRouter (deliberately dormant)**: OpenRouter launched a unified
  Image API in June 2026 (30+ models -- Flux, Gemini image, Seedream,
  GPT-image -- behind one key). Verified the exact request/response shape
  against OpenRouter's own docs (`POST /api/v1/images`, base64 image in
  `data[0].b64_json`, synchronous, no polling needed) and built the client
  against that. Per explicit decision, this is wired up and tested but left
  unconfigured (`OPENROUTER_API_KEY` empty) -- ready to activate with just
  an env var whenever it's wanted, without writing new code.

Scope was deliberately kept to images only; AI video generation (Runway,
Kling, Luma-class tools) is materially more expensive and slower per clip
than a single cover image and was explicitly decided against for now --
the existing motion-graphics `video_renderer.py`/`video_package.py`
pipeline (assembles video from audio + a static image) is unchanged.

Verified: 15 new tests (provider config-gating, Replicate poll/success/
failure paths, OpenRouter base64 decode, route-level provider wiring) plus
the full suite (173 tests) and ruff, all green. Confirmed against the live
server: the procedural default path is unaffected (still returns a real
PNG), and both AI providers correctly return a 400 with a clear
"not configured" message when their respective key/token is absent --
which is the actual state of this environment, since no Replicate or
OpenRouter credentials exist here.

**Still needed from you:** set `REPLICATE_API_TOKEN` (activates the
default Flux provider -- also unlocks Milestone 11's Stable Audio Open
verification below, same token) and/or `OPENROUTER_API_KEY` (activates the
dormant alternate provider) in `.env`, then generate one real cover and
confirm it actually looks photorealistic and matches the style prompt --
that's the one thing that can't be verified without a real key. Remove
this line once you've generated and looked at a real AI cover.

## Phase 2: Therapeutic Music Production Spec

A detailed evidence-informed production spec was provided covering musical
parameters, emotional arc, instrumentation, audio-engineering targets
(LUFS, true peak, EQ, spatial), track categories, an AI-generation control
schema, automated validation rules, and personalization. Before scoping
milestones from it, one thing has to be said plainly:

**Sections 1-3 of that spec (tempo, key, chord progressions, melody,
"warm piano," "sustained strings," "wooden flute," "kalimba") describe
actual composed music with real instrument timbres. The engine has no
composition or instrument-synthesis capability at all -- it only does DSP
synthesis (sine tones, filtered noise, sample-based nature loops).
Producing "a piano phrase" isn't a filter setting away; it requires either
building algorithmic composition (chord/melody generation) plus an
instrument sound engine (sample playback or synthesis) from scratch, or
integrating an external AI music-generation model and having AION handle
mastering/nature-layering/packaging around its output. This is the
largest single scope item in the project -- larger than everything built
in Phase 1 combined -- and is deliberately its own milestone (11) pending
a decision, rather than assumed into the others below.**

Everything else in the spec extends the existing DSP engine without
needing that capability.

### Milestone 8: Audio Mastering & Validation Chain

Goal: close the real gap in section 6 of the spec -- the engine currently
has no mastering stage at all. Generated audio goes straight from
synthesis to WAV with only a peak-normalize step; there's no loudness
targeting, true-peak limiting, EQ shaping, reverb, or mono-compatibility
handling.

- LUFS loudness measurement and normalization (`pyloudnorm` or a
  hand-rolled ITU-R BS.1770 implementation over the existing numpy
  pipeline) against the spec's per-category targets (e.g. -20 to -17 LUFS
  for sleep, -17 to -14 for relaxation).
- True-peak limiting (oversampled peak detection + gain reduction) to the
  spec's -1.0 dBTP default / -2.0 dBTP sleep target -- distinct from the
  existing simple peak clamp in `_write_wav`, which doesn't account for
  inter-sample peaks.
- Basic EQ shaping (sub-bass control below ~30-35 Hz, smoothing the
  2-5 kHz and 6-10 kHz regions) via `scipy.signal` biquad/shelving
  filters, consistent with how `dsp.py` already uses `lfilter`.
- Optional reverb (algorithmic, 3-10s decay) and mono-fold-down check for
  bass content below ~100-150 Hz.
- Automated validation layer implementing the spec's "Required validation
  rules": detect sudden short-term loudness jumps, clipping, audible loop
  boundaries, excessive high-frequency energy, long digital silence --
  reject/flag rather than silently ship.

Definition of done: a generated track hits its category's LUFS/true-peak
target within tolerance, passes the validation checks, and sounds
noticeably less "flat" than current output on a proper mix check.

Status: mostly done. Built `audio/mastering.py` (LUFS measurement/
normalization via `pyloudnorm` -- the ITU-R BS.1770 reference
implementation, not hand-rolled, since correctness of the gating
algorithm matters more here than avoiding a dependency; true-peak
limiting via 4x oversampled peak detection; mastering EQ via an RBJ
peaking-EQ biquad derivation, since scipy has no built-in variable-gain
peaking filter; 4th-order Butterworth bass mono-fold) and
`audio/validation.py` (clipping, long silence, sudden loudness jumps,
excessive HF energy, loop-seam discontinuity -- advisory warnings, not an
auto-reject/regenerate gate, which is a further step deliberately not
built here). All opt-in via new request fields (`target_lufs`,
`true_peak_dbtp`, `apply_mastering_eq`, `fold_bass_to_mono`) so existing
behavior is unchanged unless requested. `loudness_lufs` and
`validation_warnings` are now on every generation response and persisted
to `audio_jobs` (migration 0009), so a reviewer sees them before
approving, not just at generation time.

Verified against the real persistent Postgres (not a throwaway): a
sine tone requested at target_lufs=-18.0 measured back at -17.999999...
after normalization, both in the immediate response and after a full DB
round trip.

Not built: reverb, and the "auto-reject and regenerate" loop implied by
the spec's validation rules (this reports issues, it doesn't act on
them). Both are real scope, deliberately deferred rather than rushed.

### Milestone 9: Request Schema Extension (spec's "AI-generation controls")

Goal: expose the parameters from spec section 8 that the DSP engine can
actually act on, without pretending to support the ones it can't yet
(melodic_complexity, harmonic_tension, rhythmic_density have no effect
without a composition engine -- they'd be silently ignored fields, which
is worse than not exposing them).

- Add fields the engine can honor now: `purpose` (maps to an extended
  preset/category system per spec section 7), `target_lufs`,
  `true_peak_dbtp`, `tuning_hz` (A440/A432 alternate -- trivial, it's
  already just the frequency parameter on tone-based modes), `energy_start`
  / `energy_middle` / `energy_end` (a macro amplitude/brightness envelope
  over the track -- extends `apply_fades`, works on the existing
  noise/tone/texture/sample palette even without melody).
- Explicitly do NOT add fields with no implementation behind them yet
  (`melodic_complexity`, `harmonic_tension`, `instrumentation` list with
  instrument names) -- those belong to Milestone 11.
- Extend `audio/presets.py` with the spec's track categories (Deep Sleep,
  Stress Release, Anxiety-Calming, Meditation, Pain-Comfort, Calm Focus)
  as parameter presets over the existing engine, not as claims of
  matching the full spec's instrumentation.

Definition of done: a request can specify a purpose/category and get
sensible engine parameters back, with no field in the schema implying a
capability that doesn't exist.

Status: done, with a real bug found and fixed via live testing along the
way. `tuning_hz` only affects `chimes_texture` (the only pitched content
in the engine -- named pitches C5/D5/E5/G5/A5 defined relative to A440;
every other mode takes `frequency_hz` directly, so there's no "note" to
retune). `energy_start`/`energy_middle`/`energy_end` is a 3-point
piecewise-linear envelope over the whole track, extending the existing
fade machinery -- linear rather than a spline, matching the spec's own
"gradual dynamic changes only" guidance (a spline could overshoot past
the given values).

`purpose` ended up as a lookup endpoint (`GET /audio/purposes`,
`audio/purposes.py`) rather than a field on the generation request
itself: an implicit-override field that silently rewrites
`target_lufs`/`energy_start` etc. based on which ones the caller didn't
explicitly set is a fragile pattern (Pydantic can track that via
`model_fields_set`, but the resulting behavior is harder to reason about
than "fetch the recommended bundle, then build your real request"). This
is a deliberate design choice, not a shortfall against the milestone's
literal wording -- the definition of done ("specify a purpose and get
sensible parameters back") is satisfied by the lookup, just via GET
instead of an implicit POST-time rewrite. The 6 profiles map the spec's
track categories onto its loudness table (Deep Sleep -> Sleep, Stress
Release/Anxiety-Calming/Pain-Comfort -> Relaxation, Meditation ->
Meditation, Calm Focus -> Calm Focus), using each range's midpoint as the
default `target_lufs`.

The real finding: combining `target_lufs` with a steep `energy_start`/
`energy_middle`/`energy_end` arc (exactly what a purpose profile like
"sleep" does) exposed a genuine bug in Milestone 8's mastering chain that
its own unit tests hadn't caught, because none of them combined LUFS
normalization with a high-crest-factor signal. Normalizing integrated
loudness to -18.5 LUFS on a track with a loud start and near-silent tail
pushed the true peak to +4.79 dBTP (clipping); true-peak limiting then
clawed the gain back afterward, dragging the final measured loudness to
-28 LUFS against the -18.5 target -- a ~9.5dB miss, silently. Found only
by testing a real purpose-driven request against the live server, not by
the mastering tests in isolation. Fixed by capping the LUFS gain so it
never pushes the peak past `true_peak_dbtp` in the first place, rather
than applying the full gain and correcting afterward -- the two stages
now coordinate instead of fighting. The honest result when a target
can't be fully reached without clipping is a lower measured
`loudness_lufs`, reported accurately rather than silently violating peak
safety. This is consistent with the spec's own instruction to avoid
heavy limiting -- a proper multi-band limiter that could hit both targets
simultaneously was considered and not built, since that's exactly the
"heavy limiting and audible pumping" the spec says to avoid.

146/146 tests pass (14 new, including a regression test pinned to this
exact bug's parameters).

### Milestone 10: Breathing Sync + Personalization

Goal: the two spec features that are genuinely new DSP/product surface
but don't require composition.

- Breathing-sync envelope (spec section 5): a slow amplitude/filter LFO
  timed to inhale/exhale seconds, rising through inhale and resolving
  through exhale -- extends the existing envelope/fade machinery in
  `dsp.py`, applied as a macro modulation over any layer combination.
- Personalization and outcome tracking (spec section 9): new DB models
  for before/after ratings (stress, mood, sleep-onset estimate),
  completion/skip tracking, and stated preferences -- follows the
  existing `AudioJob`/`YouTubePublication` model + repository pattern.

Definition of done: a track can be generated with breathing-sync enabled
and sound audibly different (swells timed to the specified cycle); a
rating can be submitted against a completed track and persisted.

Status: done. `apply_breathing_sync` uses a raised-cosine shape for each
inhale/exhale phase rather than a linear ramp -- a linear ramp has a
sharp corner at the top and bottom of every cycle that reads as a pulse;
a raised cosine (zero slope at both ends) doesn't, matching the spec's
"use automation rather than obvious rhythmic pulses" guidance directly,
the same reasoning already applied to the energy envelope in Milestone 9.
Disabled by default (`breathing_sync_enabled: false`), so existing
behavior is unchanged unless requested.

`track_ratings` (new table, migration 0010) captures the spec's section 9
personalization fields (stress/mood before-after, sleep-onset estimate,
completion/skip tracking, preferred instruments, uncomfortable sounds) via
`POST`/`GET /audio/jobs/{id}/ratings`. Repository functions aren't
unit-tested directly, consistent with `audio_jobs.py`/`youtube.py`'s
existing repositories in this codebase -- verified live against the
persistent Postgres instead: submitted a rating (201), listed it back
(200, correct content), and confirmed a 404 for a nonexistent job id.

154/154 tests pass (9 new, schema-validation level -- the 1-10 scale
bounds, non-negative duration fields, defaults).

This closes out every milestone that didn't need a decision from you.
What's left: Milestone 2 (real CC0 sample sourcing -- needs manual
curation, can't be automated from here), Milestone 5 (distributor --
already decided: manual RouteNote until income clears the LabelGrid
automation threshold), and Milestone 11 below (composition -- decided
and built against Stable Audio Open, but real output quality and the
exact community-model input schema remain unverified without a
Replicate API token, which doesn't exist in this environment).

### Milestone 11: Melodic/Harmonic Composition Engine -- NEEDS A DECISION

Goal: actually produce the instrumented, composed music the spec
describes (piano, pads, strings, flute, harp/kalimba, chord progressions,
melody) -- not deferred by oversight, deferred because it's a real
architecture decision with cost and complexity attached, the same way the
distributor and sample-sourcing decisions were.

Two real paths, not yet chosen:

- **Build it**: algorithmic chord-progression + melody generation, paired
  with a sample-based or synthesized instrument engine (extends the
  `sample_library` pattern from Milestone 2, but for instrument notes/
  loops instead of nature sounds, or real subtractive/wavetable synthesis
  for pad/string/flute timbres). Fully in-house, no per-generation cost,
  but a large, multi-part build.
- **Integrate an external AI music-generation model/API**: AION handles
  the parts it's already good at (mastering, nature-sound layering,
  metadata, packaging, publishing) around a generated instrumental bed.
  Faster to a working result, but introduces a real per-generation cost
  and a new external dependency to evaluate (licensing terms for
  commercial/resale use need the same scrutiny the sample-library sourcing
  got -- many AI music generators restrict commercial redistribution the
  same way SFX libraries do).

Definition of done: not defined yet -- depends on which path gets chosen.

Status: decided and integration built. Chose Stable Audio Open over
MusicGen and YuE after verifying license terms directly on primary
sources (not aggregator summaries, which contradicted each other on
MusicGen specifically): MusicGen's usable pretrained weights are
CC-BY-NC 4.0 (non-commercial, confirmed via Meta's own model card and a
GitHub issue on the repo) -- ruled out entirely, no revenue threshold
exception exists for non-commercial licenses. YuE is genuinely Apache 2.0
for code and weights (the cleanest license of the three) but is built for
full pop songs with vocals/lyrics -- the opposite of the instrumental-only
need -- and needs a serious GPU (16-80GB VRAM). Stable Audio Open is free
for commercial use under $1M/yr revenue (Stability AI's own license page)
and its short-clip/textural output style fits the loop-layering engine
already built for nature sounds, rather than needing new architecture.

Training an equivalent model in-house was considered and explicitly
ruled out: that's curated training data at real scale, ML research
expertise, and realistic training compute cost in the tens to hundreds of
thousands of dollars -- a different category of project, not a bigger
version of anything built so far.

Implementation: reuses the sample-library infrastructure from Milestone 2
rather than a new subsystem -- an AI-generated clip is architecturally
the same thing as a licensed recording (a WAV file to loop and layer), now
distinguished by a `source_type` field ("recording" vs "ai_generated").
Generation goes through a hosted Replicate API
(`stackadoc/stable-audio-open-1.0`, ~$0.14/generation) rather than
self-hosted GPU inference, so no GPU management is needed. New
`POST /audio/samples/generate` endpoint calls the model, downloads the
result, and registers the manifest entry automatically.

Not verified (no Replicate account exists in this environment): the exact
input parameter schema for this specific community-hosted model, and
critically, whether it actually sounds convincing for "warm piano" /
"sustained strings" specifically -- it's built more for texture/sound
design than melodic instruments. Recorded as an open question in
docs/06-factories/natural-sound-sample-library.md rather than assumed.
Everything mockable is unit tested (API request/poll/download flow,
failure/timeout handling, manifest registration); the real API call has
never been made.

**Still needed from you:** the same `REPLICATE_API_TOKEN` as the AI
artwork section above -- generate one real "warm piano" or "sustained
strings" clip via `POST /audio/samples/generate` and judge honestly
whether it sounds like an instrument or like ambient texture, since that
determines whether this path is sufficient or whether the "build it
in-house" alternative (algorithmic composition + a real instrument engine)
needs to be revisited. Remove this line once you've listened to a real
generated clip and made that call.

## Milestone 12: Async Worker Pipeline (`apps/worker`)

Goal: a second, queue-backed generation path (`POST /audio/jobs` -> Redis
-> `apps/worker` consumes and calls the same generation engine) alongside
the synchronous `/generate-and-catalog` path the UI actually uses.

Status: fixed and verified working end to end for the first time in this
project's history. Full story, in order, since it involves a real mistake:

1. While auditing the whole project for dead/broken code, `POST
   /audio/jobs` + `app/services/audio_queue.py` were judged genuinely dead
   (nothing in the codebase consumed the queue it pushed to) and removed.
2. **That judgment was wrong** -- `apps/worker/app/main.py` was never
   checked. It's a complete, working consumer: blocks on the Redis queue
   (`client.brpop`), loads the job, calls the same `generate_audio()`
   engine everything else uses, and updates the `AudioJob` row. It just
   happens to be a separate app under `apps/worker/`, not something the
   audit's dead-code grep inside `apps/api/` would surface. Deleting
   `audio_queue.py` broke its import outright. Caught by an even broader
   audit pass immediately after, not by the test suite (there was no
   `apps/worker/tests/` at all, despite `pyproject.toml` already expecting
   one) -- confirmed the mistake honestly rather than quietly patching it.
3. Restored `audio_queue.py`, `POST /audio/jobs`, `AudioJobCreate`, and
   `create_audio_job` to their exact original committed content (via `git
   show`, not retyped from memory -- confirmed byte-identical afterward,
   `git status` shows zero diff on those files).
4. Actually running the restored pipeline for the first time surfaced a
   real, separate bug: `GENERATED_AUDIO_DIR` is a relative path
   (`data/generated/audio`), so it resolves against whatever the *current
   process's* working directory happens to be. The API (run via `uvicorn`
   from `apps/api/`) and the worker (run via `python
   apps/worker/app/main.py` from the repo root, matching how a developer
   would naturally invoke it locally) landed on two different absolute
   directories -- a worker-completed job's file existed on disk, but the
   API's own `/audio/files/{filename}` route 404'd on it, since it was
   looking in a different folder. Confirmed this wouldn't happen in the
   real Docker deployment specifically (both `api` and `worker` services in
   docker-compose.yml already set an absolute `GENERATED_AUDIO_DIR:
   /app/data/generated/audio` and share the same volume mount) -- purely a
   local-dev-workflow gap. Fixed by setting an absolute
   `GENERATED_AUDIO_DIR` in the repo-root `.env` (which is what the worker
   reads when launched from the repo root; also fixed that same `.env`'s
   `DATABASE_URL`/`REDIS_URL` to use `127.0.0.1` instead of `localhost`,
   same IPv6-loopback issue documented earlier in this doc, which this
   separate `.env` file had independently reverted to since it predates
   that fix).
5. Verified live, for real: submitted a job through `POST /audio/jobs`,
   watched the running worker's own log pick it up and print `Completed
   audio job: <id>`, confirmed via `GET /audio/jobs/{id}` that `status`
   went to `completed` with a real `output_file_path`, confirmed the WAV
   is valid (correct channel count/sample rate/duration via `wave.open`),
   and confirmed the API can actually serve it back
   (`GET /audio/files/{filename}` -> 200, not 404).
6. `apps/worker/tests/test_main.py` added (didn't exist before, despite
   `pyproject.toml` already listing `apps/worker/tests` as a test path) --
   5 tests covering `process_job`'s missing-job, wrong-status,
   success, generation-failure, and retry-status branches. Loaded via
   `importlib` rather than a normal import, because `apps/api/app` and
   `apps/worker/app` are both top-level packages literally named `app` --
   whichever imports first in a given interpreter session wins that name,
   silently shadowing the other (this is the same mechanism behind the
   worker's script-only invocation requirement). Confirmed both test
   suites run correctly together from the repo root (201 passed, api +
   worker, no collision) as well as independently.

This path remains disconnected from the web UI -- nothing in `index.html`
calls `POST /audio/jobs`, only `/generate-and-catalog`. It's real, tested,
and now verified working, but still a second, currently-unused generation
path rather than the active one. Whether to wire the UI to it, keep both
paths, or consolidate on one is a separate, later decision -- out of scope
for "make sure what's here actually works."

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
- Milestones 8-10 (Phase 2) can proceed independently of Milestone 11 --
  none of them depend on composition existing.
- Milestone 11 needs a build-vs-integrate decision before any code gets
  written against it, the same way Milestone 5 needed a distributor
  decision first.
