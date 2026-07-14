# MP4 Rendering

## Requirement

FFmpeg must be installed.

Verify:

```bash
ffmpeg -version
```

## Endpoint

```text
POST /api/v1/exports/video/render
```

Example:

```json
{
  "audio_filename": "sound.wav",
  "artwork_filename": "cover.png",
  "output_filename": "night-rain.mp4",
  "width": 1920,
  "height": 1080,
  "frame_rate": 30
}
```

## Export Bundle

```text
POST /api/v1/exports/bundle
```

The generated ZIP can contain audio, artwork, video, metadata and a catalog manifest.
