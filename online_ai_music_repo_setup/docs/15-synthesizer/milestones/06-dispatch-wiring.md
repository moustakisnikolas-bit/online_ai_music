# Milestone 6 — Generator dispatch wiring

**Status:** Done

## In plain terms

Connect the "what notes to play" piece (Milestone 1) and the "how to
actually play them" piece (Milestone 2) into AION's main generation
pipeline, so picking Synthesizer mode produces a real WAV file that then
automatically gets the same fades, textures, and mastering every other
mode already gets.

## Technically

In `apps/api/app/services/audio_generator.py`'s `_mono_samples()`, added a
branch right after the existing `PRESET` branch: builds the note events via
`generate_pattern()`, builds the CC values via `build_cc_values()`, and
returns `render_pattern(...)`. Everything downstream of `_mono_samples()`
— texture layering, fades/energy-envelope/breathing-sync, stereo
duplication, bass-mono-fold, mastering EQ, LUFS normalization, true-peak
limiting — applies automatically with zero extra code, exactly as already
confirmed for `PRESET` mode.

`render_pattern()` raises a plain `ValueError` if
`soundfont_synth_available()` is `False`. Both existing routes
(`/audio/generate`, `/audio/generate-and-catalog` in
`apps/api/app/api/routes/audio.py`) already catch `ValueError` (among
`OSError`/`RuntimeError`) and turn it into a clean HTTP 400 with the error
message — so **no new route code was needed** for the "not configured"
case; it falls straight into the existing error-handling path both
endpoints already had.

`long_form=True` is explicitly rejected for `SYNTHESIZER` mode at the
schema layer (Milestone 5) rather than left to fail at generation time,
because `long_form_audio.py` has its own, completely separate chunked
dispatch chain with no concept of carrying note-timing/instrument state
across chunk boundaries — building that is real extra work this version
deliberately doesn't attempt.

## Verified by

`apps/api/tests/test_synthesizer_audio.py`: a monkeypatched dispatch test
confirming `generate_audio()` reaches `render_pattern()` with the right
arguments (note count, duration, sample rate, correct GM program number,
all four CC values) and returns `result.mode == "synthesizer"`; a textures-
composition test; and a live HTTP test confirming the "not available" path
returns a clean 400, not a raw traceback or 500.
