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

`.aion/backups/`, `zips/`, and `unzipped_folders/` remain open decisions
for you, not automated cleanup -- still tracked in git as before.

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
