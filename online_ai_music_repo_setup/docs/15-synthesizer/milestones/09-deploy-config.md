# Milestone 9 — Docker/deploy updates

**Status:** Done

## In plain terms

Make sure the version of AION that eventually runs on your real server has
the instrument-player software installed, and make it easy to drop the
sound-bank file onto that server without rebuilding the whole container
every time.

## Technically

- `apps/api/Dockerfile` — added `apt-get install -y --no-install-recommends
  fluidsynth` before the `pip install` step. The base image
  (`python:3.12-slim`) had zero OS-package steps before this — it's the
  first one.
- `docker-compose.yml` — added `SOUNDFONT_PATH:
  /app/data/soundfonts/GeneralUser-GS.sf2` to the `api` service's
  environment (matching the existing `GENERATED_AUDIO_DIR` absolute-path
  convention already used there), and a
  `./data/soundfonts:/app/data/soundfonts` volume mount (matching the
  existing `./data/generated:/app/data/generated` mount) — so the `.sf2`
  file lives on the host and doesn't need to be baked into the image or
  re-copied on every rebuild.
- `apps/worker/Dockerfile` intentionally does **not** get this change in
  v1, since the async job-queue path is out of scope (see the README's
  "out of scope" section).

## Verified by

Not yet run against a real deployment (this repo is still in local/dev
testing) — this milestone covers the configuration being in place and
consistent with the project's existing Docker conventions. The full "How
we'll know it actually works" check for the real VPS deployment is:
build the image, confirm `fluidsynth` is present in the container, drop a
soundfont file into the mounted host folder, and generate a Synthesizer
clip through the deployed API.
