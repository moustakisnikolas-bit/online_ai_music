# Export Bundle

## Purpose

The export bundle packages all assets required for manual review and later publishing.

## Package Contents

- audio asset;
- optional artwork;
- optional video;
- metadata JSON;
- catalog manifest;
- SHA-256 checksums.

## Catalog Manifest

The manifest records:

- package ID;
- title;
- creation timestamp;
- included files;
- file sizes;
- checksums;
- approval requirement;
- publishing status.

## Current Publishing Status

Bundles are created with:

```text
publishing_status = not_published
```

The application does not upload automatically in this MVP.
