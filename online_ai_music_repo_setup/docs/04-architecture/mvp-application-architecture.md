# MVP Application Architecture

## Runtime Components

- FastAPI API
- PostgreSQL
- Redis
- MinIO
- Background worker

## Initial Data Flow

1. Client submits an audio generation request.
2. API validates the request.
3. Generator creates a WAV asset.
4. Asset is written to local generated storage.
5. API returns asset metadata.

## Current Limitations

- Synchronous generation
- Local file output
- No database persistence in the endpoint yet
- No queue-backed jobs yet
- No authentication yet

These limitations are intentional for the first working vertical slice.
