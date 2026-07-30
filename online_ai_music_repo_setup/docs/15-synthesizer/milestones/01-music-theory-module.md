# Milestone 1 — Music theory module

**Status:** Done

## In plain terms

Before AION can play "C major, starting at C4, going up two octaves in a
zigzag," something needs to turn that plain-English request into an exact
list of notes and exact timings. This step built just that calculator —
pure math, no audio involved yet.

## Technically

New file `apps/api/app/audio/music_theory.py`, pure Python/NumPy, zero new
dependencies:

- `SCALES: dict[str, tuple[int, ...]]` — semitone-interval patterns for
  `major`, `natural_minor`, `major_pentatonic`, `minor_pentatonic`, and
  `dorian`.
- `parse_note_name("C4") -> 60` — standard scientific pitch notation to a
  MIDI note number (middle C = 60), supporting sharps (`#`) and flats
  (`b`).
- `midi_to_hz(midi_note, tuning_hz=440.0)` — for reference/debugging (not
  consumed by the FluidSynth path, which takes MIDI note numbers
  directly).
- `NoteEvent` — a frozen dataclass (`midi_note`, `start_time_seconds`,
  `duration_seconds`, `velocity`).
- `generate_pattern(root_note, scale_name, pattern_type, octave_range,
  note_duration_seconds, duration_seconds, seed)` — returns an ordered
  `list[NoteEvent]`. `up`/`down`/`up_down` are fully deterministic (no
  randomness); `random` is seeded via `np.random.default_rng`, matching
  the determinism convention every other seeded generator in `dsp.py`
  already uses. Note count is derived from
  `duration_seconds / note_duration_seconds`, not a separate field.

## Verified by

`apps/api/tests/test_music_theory.py` — note-name parsing (including
sharps/flats/lowercase/invalid input), scale interval correctness,
deterministic pattern shapes (`up`/`down`/`up_down`, including that
`up_down` doesn't repeat its peak note), seeded reproducibility for
`random`, note-count/timing math, and octave-range expansion.
