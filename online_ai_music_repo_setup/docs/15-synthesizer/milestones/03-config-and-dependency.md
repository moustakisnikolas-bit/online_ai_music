# Milestone 3 — Config and dependency wiring

**Status:** Done

## In plain terms

Tell AION where to find the instrument sound-bank file on this particular
machine, and add the new software it depends on to the project's install
list.

## Technically

- `apps/api/app/core/config.py` — added `soundfont_path: str =
  "data/soundfonts/GeneralUser-GS.sf2"` to `Settings`, matching the plain
  relative-path-string style already used for `generated_audio_dir`.
- `requirements/runtime.txt` — added `pyfluidsynth>=1.3,<2.0`, flagged in
  a comment as the first dependency in this project's history that needs a
  native library (`libfluidsynth`) installed separately from `pip install`
  — everything else the project uses (`numpy`, `scipy`, `pyloudnorm`) is a
  pure-Python-wheel install.
- `.env.example` — documented `SOUNDFONT_PATH` alongside
  `GENERATED_AUDIO_DIR`.
- The repo-root `.env` (used when running the app with its working
  directory at the repo root, e.g. via the Makefile targets) got a matching
  absolute-path override — the same pattern `GENERATED_AUDIO_DIR` already
  used there, since these `data/...` paths resolve relative to whatever
  directory the process happens to be run from.

## Verified by

Full test suite still green after the config addition — no existing
behavior changed, since `soundfont_path` is a brand-new field nothing else
reads yet.
