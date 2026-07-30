# Milestone 5 — Schema changes

**Status:** Done

## In plain terms

Teach AION's "request form" about the new mode's options — instrument,
root note, scale, pattern shape, note length, octave range, and the four
tone-shaping knobs — and make sure it clearly rejects incomplete or
nonsensical requests (missing root note, unknown instrument name, etc.)
before any audio work starts, the same way every other mode already
validates its own required fields.

## Technically

- `apps/api/app/audio/types.py` — added `SYNTHESIZER = "synthesizer"` to
  `AudioMode`.
- `apps/api/app/schemas/audio.py` — added 10 new optional fields to
  `AudioGenerationRequest` (`synth_instrument`, `synth_root_note`,
  `synth_scale`, `synth_pattern`, `synth_note_duration_seconds`,
  `synth_octave_range`, `synth_attack_seconds`, `synth_release_seconds`,
  `synth_filter_cutoff`, `synth_filter_resonance`), following the same
  flat-optional-field pattern `preset_name` already uses.
- A new block in the existing `validate_mode_configuration` model
  validator requires `synth_instrument`/`synth_root_note`/`synth_scale`/
  `synth_pattern` when `mode == SYNTHESIZER`, and validates each against
  its allowed set (`GM_INSTRUMENTS`, `SCALES`, the four pattern types,
  and `parse_note_name` for the root note) — reusing `music_theory.py`
  and `soundfont_synth.py` directly rather than duplicating the lookup
  tables in the schema layer.
- A second new check, next to the existing `long_form` incompatibility
  checks, rejects `long_form=True` with `mode == SYNTHESIZER` — see
  Milestone 6 for why.
- **Deliberately not touched**: `apps/api/app/schemas/audio_job.py` (the
  separate, already out-of-sync schema behind the async `/audio/jobs`
  path) does not get the new fields in v1 — see the README's "out of
  scope" section.

## Verified by

`apps/api/tests/test_synthesizer_audio.py`'s schema tests: missing
required fields rejected, unknown instrument/scale rejected, malformed
root note rejected, `long_form=True` + `synthesizer` rejected — all with
clear, specific error messages.
