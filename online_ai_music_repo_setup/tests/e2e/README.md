# End-to-End Tests

The first AION end-to-end test runs against the complete local Docker stack.

Run:

```bash
./scripts/dev/docker-smoke-test.sh
```

The test validates:

1. PostgreSQL startup
2. Redis startup
3. Alembic migrations
4. FastAPI readiness
5. Project persistence
6. Audio job persistence
7. Redis queue delivery
8. Worker processing
9. WAV output creation
10. WAV header and duration
