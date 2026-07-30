# Milestone 4 — Getting the SoundFont file

**Status:** Done (documentation + folder ready; downloading the actual
file is a manual one-time step per machine, see below)

## In plain terms

Download the actual "instrument sound bank" file AION uses to make its
piano/pad/bell/string sounds.

## Technically

Recommended: **GeneralUser GS** by S. Christian Collins — free, about
30MB, explicitly licensed for commercial use and redistribution (the only
restriction is not reselling the soundfont file itself as a standalone
product), with solid piano/pad/strings/bell/choir patches matching this
feature's target sound. **FluidR3_GM** is documented as a fallback
alternative if GeneralUser GS's hosting ever moves.

Goes at `apps/api/data/soundfonts/GeneralUser-GS.sf2` for local
(non-Docker) development — a new sibling to the existing
`apps/api/data/sample_library/` folder. **Not committed to git**: added
`**/data/soundfonts/*.sf2` to the repo-root `.gitignore`, alongside the
existing generated-files rules. A committed `apps/api/data/soundfonts/README.md`
explains what the folder is, the download link, and the license.

Because this project's `data/...` paths resolve relative to wherever the
process is actually run from (an existing, pre-existing quirk — see
Milestone 3), the file may need to exist in more than one place depending
on how you run AION:
- Local dev with the working directory at `apps/api/`: `apps/api/data/soundfonts/GeneralUser-GS.sf2`.
- Running with the working directory at the repo root (Makefile-style):
  covered by the repo-root `.env`'s absolute `SOUNDFONT_PATH` override,
  which points at the same `apps/api/data/soundfonts/...` location.
- Docker: `data/soundfonts/GeneralUser-GS.sf2` at the *repo root* (a
  separate folder from `apps/api/data/soundfonts/`), mounted into the
  container — see Milestone 9.

## Verified by

`soundfont_synth_available()` returning `False` cleanly (and Synthesizer
mode failing with a clear error, not a crash) when the file isn't present
yet — confirmed via the "not available" test in
`test_synthesizer_audio.py` and live against a running server with no
soundfont configured.
