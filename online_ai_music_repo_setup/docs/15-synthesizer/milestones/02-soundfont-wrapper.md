# Milestone 2 — SoundFont player wrapper

**Status:** Done

## In plain terms

This is the piece that actually makes sound. It loads the "instrument
sound bank" file, picks the instrument you chose, applies your tone-shaping
knobs, and plays the note list from Milestone 1 into an audio clip. It also
knows how to say "sorry, that's not available right now" cleanly if the
instrument-playing software isn't installed on this particular machine,
instead of crashing.

## Technically

New file `apps/api/app/audio/soundfont_synth.py`. Imports the `fluidsynth`
Python package only *inside functions*, never at module top level, so this
file — and schema validation, and every test that doesn't touch real
rendering — keeps working even on a machine without FluidSynth installed.

- `soundfont_synth_available() -> bool` — tries to import `fluidsynth`,
  create a throwaway `Synth`, and load the configured soundfont; returns
  `False` on any failure. Cached with `@lru_cache`, matching
  `get_settings()`'s caching pattern, since this doesn't change during a
  process's lifetime.
- A lazy, per-sample-rate cache of `(Synth, soundfont_id)` pairs —
  FluidSynth's internal sample rate is fixed at construction and can't
  change afterward, and reloading the multi-MB soundfont file on every
  request would be slow, so it's loaded once per distinct sample rate and
  reused.
- `GM_INSTRUMENTS: dict[str, int]` — a curated 25-entry palette of General
  MIDI program numbers spanning piano/keys, mallets/bells, strings, choir,
  winds, and pads/atmosphere — chosen for sleep/relaxation/focus-appropriate
  timbres, not all 128 GM instruments. Schema validation only ever accepts
  a name from this dict, never a raw program number.
- Attack/release/cutoff/resonance are applied via real MIDI Control Change
  messages (`synth.cc(channel, controller, value)`): CC73 (attack), CC72
  (release), CC71 (resonance), CC74 (cutoff/brightness) — the standard
  General MIDI mechanism for shaping an instrument's envelope/filter.
  `build_cc_values()` maps your seconds/0-1 values to the 0-127 MIDI range
  FluidSynth expects.
- `render_pattern(events, duration_seconds, sample_rate, program_number,
  cc_values) -> np.ndarray` — selects the instrument, applies the CC
  values, walks the note timeline calling FluidSynth's `get_samples()`
  between events and `noteon()`/`noteoff()` at the right frames, renders a
  little past the nominal duration so a note's release tail isn't cut off,
  then trims to exactly `duration_seconds * sample_rate` frames (matching
  every other generator's contract). FluidSynth returns interleaved stereo
  16-bit audio, converted to float32 and downmixed to mono (matching how
  every other non-binaural mode works), then scaled by the request's
  `amplitude`, same as every other generator.
- Because a single `Synth` instance isn't safe for two requests to render
  on at the exact same instant, rendering is guarded by a lock so only one
  render happens at a time process-wide — a deliberate, simple v1 choice.

## Verified by

`apps/api/tests/test_synthesizer_audio.py`'s dispatch tests (monkeypatched,
run everywhere) and one real end-to-end render test
(`pytest.mark.skipif`-guarded, only runs where FluidSynth is actually
installed).
