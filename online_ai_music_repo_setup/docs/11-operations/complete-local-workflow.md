# Complete Local Workflow

## Start the Application

```bash
make api
```

Open:

```text
http://127.0.0.1:8000/
```

## Workflow

The complete browser workflow performs:

1. audio generation;
2. metadata generation;
3. artwork generation;
4. optional MP4 rendering;
5. export ZIP creation.

## Generated Outputs

### Audio

Stored under:

```text
data/generated/audio
```

### Artwork

Stored under:

```text
data/generated/artwork
```

### Video

Stored under:

```text
data/generated/video
```

### Export Bundle

Stored under:

```text
data/generated/exports
```

## FFmpeg Behavior

When FFmpeg is unavailable:

- WAV generation still works;
- metadata generation still works;
- artwork generation still works;
- MP4 generation is skipped or returns an explicit error;
- the export bundle can still be created without video.

## Publishing

The ZIP is a preparation package.

It is not uploaded automatically and should be reviewed before distribution.
