# Local Docker Stack

## Components

- PostgreSQL
- Redis
- MinIO
- Alembic migration container
- FastAPI API
- Audio worker

## Start

```bash
docker compose up -d --build
```

## Status

```bash
docker compose ps
```

## Logs

```bash
docker compose logs -f api worker migrate
```

## End-to-End Validation

```bash
./scripts/dev/docker-smoke-test.sh
```

## Stop

```bash
docker compose down
```

## Destructive Local Reset

```bash
./scripts/ops/docker-reset-local.sh
```

The reset helper asks for confirmation before deleting local Docker volumes.

## Expected Workflow

1. API accepts an audio job.
2. PostgreSQL stores the job.
3. Redis queues the job ID.
4. Worker claims the job.
5. Worker creates a WAV file.
6. Worker updates the job status to completed.
7. The generated file appears under `data/generated/audio`.
