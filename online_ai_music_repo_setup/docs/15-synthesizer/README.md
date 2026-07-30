# Synthesizer Mode

## What this is

A new audio mode that plays real instrument sounds — piano, warm pads,
bells, strings, choir, and more — in a repeating musical pattern you
control, layered under (or as) an AION track. Every other mode AION has
today makes non-melodic sound (tones, noise, textures); this is the first
mode that plays actual notes on an actual instrument.

## Why it exists

You asked for a synthesizer with real controls — not a black box, but
something where you pick the root note, the scale, how the notes move
(up, down, zigzag, or random), and shape the tone with attack/release/
filter knobs, the way a real synthesizer works. You also chose realistic
instrument sounds (via a SoundFont, a bank of sampled instrument tones)
over raw sine/saw waveforms, for a richer, more musical result.

Worth knowing: this is a *sound-design tool*, not an AI composer. AION's
own roadmap already looked at building a full in-house composition engine
for complete songs and chose an external AI model (Stable Audio Open)
instead — that decision stands. Synthesizer mode is a smaller, different
thing that sits alongside it: you're in control of exactly what plays,
note by note.

## How to use it (as a non-technical user)

1. Open AION, set **Mode** to **Synthesizer**.
2. Pick an **Instrument** (e.g. "Warm Pad" for a soft ambient bed, or
   "Acoustic Grand Piano" for a clearer melodic line).
3. Set a **Root note** (e.g. `C4`) and a **Scale** (Major, Natural minor,
   Major pentatonic, Minor pentatonic, or Dorian).
4. Pick a **Pattern**: Up, Down, Up/down (zigzag), or Random.
5. Adjust **Note duration** (how long each note rings) and **Octave
   range** (how wide the pattern spans).
6. Shape the tone with **Attack**, **Release**, **Filter cutoff**
   (brightness), and **Filter resonance** — the same kind of controls a
   real synthesizer has.
7. Click generate. You can layer any of AION's existing textures (rain,
   wind, etc.) underneath it too, exactly like any other mode.

If you see an error saying Synthesizer mode "is not available," it means
the server this is running on doesn't have the instrument-playing software
(FluidSynth) set up yet — see the setup section below. Every other AION
feature keeps working normally either way.

## What's actually happening, in slightly more technical terms

Two independent pieces work together. First, a pure-math "note calculator"
(`music_theory.py`) turns your root note/scale/pattern choice into an exact
list of notes and timings — no audio involved yet. Second, a SoundFont
player (`soundfont_synth.py`, built on the open-source **FluidSynth**
engine) actually plays that note list on the instrument you picked, using
your tone controls, and hands back a finished audio clip. That clip then
flows through the exact same fades/textures/mastering pipeline every other
AION mode already uses.

### Setup (only needed once per machine)

Synthesizer mode needs two things that aren't part of AION's normal
Python install:

1. **FluidSynth** itself (the software, not just the Python wrapper):
   - **Linux / the production server**: `apt-get install fluidsynth` (the
     project's Docker image already does this automatically).
   - **Windows (local dev)**: install via `conda install -c conda-forge
     fluidsynth`, or download a `fluidsynth.dll` build and put it on your
     `PATH`. There's no simple one-line `pip install` for this piece —
     `pip install pyfluidsynth` only installs a thin Python wrapper around
     it, not FluidSynth itself.
2. **A SoundFont file** — see `apps/api/data/soundfonts/README.md` for
   exactly what to download and where to put it (GeneralUser GS, free,
   ~30MB, licensed for commercial use).

If either piece is missing, Synthesizer mode fails with a clear message
instead of crashing — nothing else in AION is affected.

## Deliberately out of scope for v1

- **Long audio (`long_form=True`)**: not supported yet — rejected up front
  with a clear error, the same way several other modes already aren't
  supported there. Carrying note timing and instrument state smoothly
  across the long-form renderer's audio chunks is real extra work this
  version doesn't attempt.
- **The async job-queue path** (`POST /audio/jobs`): Synthesizer mode is
  only reachable through the regular `/audio/generate` endpoint for now.
  The job-queue's own request schema (`audio_job.py`) was already missing
  several other modes' fields before this feature existed — this is a
  pre-existing gap, not a new one.

## Milestones

1. [Music theory module](milestones/01-music-theory-module.md)
2. [SoundFont player wrapper](milestones/02-soundfont-wrapper.md)
3. [Config and dependency wiring](milestones/03-config-and-dependency.md)
4. [Getting the SoundFont file](milestones/04-soundfont-provisioning.md)
5. [Schema changes](milestones/05-schema-changes.md)
6. [Generator dispatch wiring](milestones/06-dispatch-wiring.md)
7. [Web UI section](milestones/07-web-ui.md)
8. [Tests](milestones/08-tests.md)
9. [Docker/deploy updates](milestones/09-deploy-config.md)
10. This documentation
