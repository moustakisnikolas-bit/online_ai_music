# AION Update 014

Adds bounded-memory long-form WAV rendering.

## Adds

- Chunked streaming WAV writer
- Long-form generation service
- Progress callback support
- Duration presets up to 8 hours
- Memory-safe sine, binaural, isochronic and noise rendering
- Regression tests for frame accuracy and bounded chunk size
- Long-form rendering documentation

## Suggested commit

```bash
git add .
git commit -m "feat(audio): add bounded-memory long-form rendering"
git push
```
