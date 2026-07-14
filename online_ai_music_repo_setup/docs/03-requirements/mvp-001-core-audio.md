# MVP-001: Core Audio Generation

## Objective

Provide the first functional AION capability: generate a valid WAV file through an API request.

## Scope

- FastAPI service
- Health endpoint
- Audio generation endpoint
- Configurable frequency
- Configurable duration
- Configurable sample rate
- Local output storage
- Automated tests

## Non-Goals

- Music composition
- Ambient layering
- AI provider integration
- Publishing
- Monetization
- Medical or therapeutic claims

## Acceptance Criteria

1. `GET /health` returns HTTP 200.
2. `POST /api/v1/audio/generate` creates a valid mono WAV file.
3. Invalid frequencies or durations return validation errors.
4. Unit tests pass.
5. The service can run locally or through Docker Compose.
