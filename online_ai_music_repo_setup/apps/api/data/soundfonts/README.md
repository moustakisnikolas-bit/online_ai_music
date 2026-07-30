# SoundFonts

This folder holds the `.sf2` SoundFont file AION's Synthesizer mode uses to
play realistic instrument sounds (piano, pads, bells, strings, choir, etc.)
via [FluidSynth](https://www.fluidsynth.org/). The file itself is **not**
committed to git (it's a multi-megabyte binary asset, listed in the
repo-root `.gitignore`) — you need to download it once per machine.

## What to download

**GeneralUser GS** by S. Christian Collins — free, about 30MB, explicitly
licensed for commercial use and redistribution (the only restriction is not
reselling the soundfont file itself as a standalone product). It has solid
piano/pad/strings/bell/choir patches, which is exactly what this feature
needs.

Download it from the author's site (search "GeneralUser GS soundfont") and
save the `.sf2` file as:

```
apps/api/data/soundfonts/GeneralUser-GS.sf2
```

This exact path matches the `soundfont_path` default in
`apps/api/app/core/config.py`. If you save it somewhere else, set
`SOUNDFONT_PATH` in your `.env` file to match.

If GeneralUser GS's hosting ever moves, **FluidR3_GM** is a documented
fallback alternative (larger, ~140MB, also widely used, but check its
license terms for your specific use case before using it commercially).

## If FluidSynth itself isn't installed

This file alone isn't enough — you also need the FluidSynth software
installed on the machine (not just the Python `pyfluidsynth` package, which
is just a thin wrapper around it). See `docs/15-synthesizer/README.md` for
setup instructions on Windows, Linux, and Docker. Without both pieces,
Synthesizer mode will return a clear "not available" error rather than
crashing — every other AION feature works normally either way.
