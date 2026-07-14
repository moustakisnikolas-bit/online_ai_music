# AION Update 005

This update starts the actual application implementation.

## Adds

- FastAPI backend
- SQLAlchemy models
- Alembic migration setup
- PostgreSQL, Redis and MinIO local infrastructure
- Background worker skeleton
- Audio generation endpoint
- WAV tone generator for initial functional testing
- Dockerfiles
- Pytest tests
- Makefile commands
- Environment example

## Suggested commit

```bash
git add .
git commit -m "feat(core): add backend, worker and initial audio generation pipeline"
git push
```
