# AION Update 006B

Fixes macOS Python 3.9 environments by installing or locating Python 3.12 via Homebrew.

## Actions

- Detect Apple Silicon and Intel Homebrew paths
- Install `python@3.12` when missing
- Remove an incompatible `.venv`
- Recreate `.venv` with Python 3.12
- Install project dependencies
- Run tests

## Suggested commit

```bash
git add .
git commit -m "fix(dev): provision Python 3.12 on macOS"
git push
```
