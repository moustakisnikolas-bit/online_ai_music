# Milestone 7 — Web UI section

**Status:** Done

## In plain terms

Add "Synthesizer" to AION's mode dropdown, and the new input boxes —
instrument, root note, scale, pattern, note length, octave range, and the
four tone controls — that only appear once you pick it.

## Technically

In `apps/api/app/web/index.html`:

- Added `<option value="synthesizer">Synthesizer</option>` to
  `<select id="mode">`.
- Added a hardcoded `<select id="synth-instrument">` with one `<option>`
  per `GM_INSTRUMENTS` entry (matching how `mode`/`channels`/`noise-mode`
  are already hardcoded rather than fetched from an endpoint — this is a
  small, fixed, code-defined set, not user-created/stored data).
- Added new `<label id="synth-...-group" class="hidden">` blocks for root
  note (text input), scale (select), pattern (select), note duration,
  octave range, and the four tone controls (all plain
  `<input type="number">`, matching the existing convention — no sliders
  exist anywhere in this file).
- `updateConditionalFields()` — added a `synth` boolean and a loop toggling
  all ten new field groups; added `"synthesizer"` to the existing
  `frequency-group` hide-list (synth mode doesn't use the plain
  `frequency_hz` field, it uses its own root-note field).
- `buildAudioPayload()` — added a `if (mode === "synthesizer") { ... }`
  block reading the ten new fields into the request JSON, placed alongside
  the existing `preset`/`mixed_ambient` blocks.

## Verified by

Manual tag-balance check (`<label>`/`</label>`, `<select>`/`</select>`,
`<script>`/`</script>` counts match) and a live server request with a
missing-FluidSynth environment confirming the mode selection, field
show/hide, and payload submission all work end-to-end up to the point
where FluidSynth itself would take over.
