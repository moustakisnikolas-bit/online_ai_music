# MVP-003: Audio Asset Retrieval

## Objective

Allow generated WAV files to be inspected and downloaded safely through the API.

## Functional Requirements

- Retrieve WAV metadata by filename.
- Download a WAV file.
- Calculate SHA-256 checksum.
- Return duration, channel count, sample rate and frame count.
- Reject nested paths.
- Reject path traversal attempts.
- Return HTTP 404 for missing files.
- Return HTTP 422 for invalid WAV files.

## Endpoints

```text
GET /api/v1/audio/assets/{filename}
GET /api/v1/audio/assets/{filename}/download
```

## Current Scope

Only simple `.wav` filenames located directly inside the configured generated-audio directory are accepted.

This intentionally prevents arbitrary filesystem access.
