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

## Milestone 7: Visual Polish

Goal: a UI that reads like a real product, not an internal test form.

- Waveform preview/scrubber before export.
- Cover-art picker/preview inline with generation.
- Visual system refinement: consistent spacing, typography, iconography,
  informed by mainstream streaming-app UI patterns.

Definition of done: subjective; validate side by side against a mainstream
streaming app and a video platform's creator studio as reference points.

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
