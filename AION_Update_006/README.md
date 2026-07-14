# AION Update 006

Adds persistent audio generation jobs backed by PostgreSQL and Redis.

## Adds

- AudioJob database model
- PostgreSQL persistence
- Redis queue producer
- Worker queue consumer
- Job status endpoints
- Project creation endpoint
- Migration 0002
- Queue and service tests
- Updated Docker and local commands

## Suggested commit

```bash
git add .
git commit -m "feat(audio): add persistent queue-backed audio jobs"
git push
```
