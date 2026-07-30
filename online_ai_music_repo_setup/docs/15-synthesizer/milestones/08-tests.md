# Milestone 8 — Tests

**Status:** Done

## In plain terms

Prove the music-theory math is correct on every machine (no special
software needed), and prove Synthesizer mode is wired up correctly
everywhere — with a real end-to-end sound check only running on machines
that actually have the instrument-player software installed.

## Technically

- `apps/api/tests/test_music_theory.py` — 19 tests covering note-name
  parsing (including sharps, flats, lowercase, and rejection of malformed
  input), scale interval correctness, deterministic pattern shapes for
  `up`/`down`/`up_down` (asserted against exact expected note sequences,
  no seed needed), seeded reproducibility and cross-seed variation for
  `random`, note-count/timing math, and octave-range expansion. Zero
  dependency on FluidSynth.
- `apps/api/tests/test_synthesizer_audio.py`:
  - Schema-validation tests: missing required fields, unknown instrument,
    unknown scale, malformed root note, and `long_form=True` all rejected
    with clear messages.
  - A dispatch-wiring test that monkeypatches
    `audio_generator.render_pattern` (the same monkeypatch style already
    used for `ffmpeg_available` in `test_audio_encoding.py`) so it runs on
    every machine without real FluidSynth, confirming `generate_audio()`
    reaches the synthesizer branch with the right arguments and returns
    `result.mode == "synthesizer"`.
  - A textures-composition test (also monkeypatched) proving
    textures layer correctly on top of synthesizer output.
  - A test confirming `render_pattern()` raises a clear `ValueError` when
    `soundfont_synth_available()` is `False`.
  - One `pytest.mark.skipif(not soundfont_synth_available(), ...)`-guarded
    real end-to-end test that renders a short pattern and validates the
    WAV shape — only runs where FluidSynth is actually installed.

## Verified by

Full suite run: 257 passed, 1 skipped (the FluidSynth-dependent
end-to-end test, correctly skipped on this development machine), `ruff`
clean.
