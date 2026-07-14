# AION Update 018A

Fixes validation order in the FFmpeg video renderer.

## Changes

- Validates `output_filename` before checking input files
- Preserves path traversal protection
- Adds a regression test for validation precedence

## Suggested commit

```bash
git add .
git commit -m "fix(export): validate output filename before media lookup"
git push
```
