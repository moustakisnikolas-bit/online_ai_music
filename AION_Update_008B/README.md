# AION Update 008B

Restores backward-compatible audio response fields.

## Changes

- Restores `frequency_hz` in `AudioGenerationResponse`
- Returns the requested frequency for sine-mode output
- Returns `null` for modes without a single primary frequency
- Adds regression tests for sine and noise responses

## Suggested commit

```bash
git add .
git commit -m "fix(audio): restore frequency in generation responses"
git push
```
