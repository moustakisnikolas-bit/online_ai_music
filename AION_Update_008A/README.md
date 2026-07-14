# AION Update 008A

Fixes short-duration audio generation after Update 008.

## Changes

- Changes default fade-in from 1.0s to 0.1s
- Changes default fade-out from 1.0s to 0.1s
- Updates API schemas
- Updates AudioJob database defaults
- Adds migration 0004
- Adds regression test for one-second clips

## Suggested commit

```bash
git add .
git commit -m "fix(audio): support short clips with safe fade defaults"
git push
```
