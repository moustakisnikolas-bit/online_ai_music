# AION Update 006C

Fixes setuptools package discovery failure in the monorepo.

## Changes

- Adds explicit runtime and development requirements files
- Stops using `pip install -e .` for local setup
- Updates macOS and generic setup scripts
- Preserves the monorepo layout
- Keeps imports working through `PYTHONPATH`

## Suggested commit

```bash
git add .
git commit -m "fix(dev): install dependencies without editable monorepo packaging"
git push
```
