# Visual Package Example

## Generate Artwork

```text
POST /api/v1/visuals/artwork/generate
```

```json
{
  "title": "Night Rain",
  "subtitle": "Original Sleep Audio",
  "preset_name": "spotify-cover",
  "seed": 42
}
```

## Generate a Video Manifest

```text
POST /api/v1/visuals/video/manifest
```

```json
{
  "title": "Night Rain",
  "audio_filename": "night-rain.wav",
  "artwork_filename": "night-rain.png",
  "duration_seconds": 3600,
  "width": 1920,
  "height": 1080,
  "frame_rate": 30
}
```

## Current Limitation

This update creates the visual assets and render manifest.

Actual MP4 rendering is added in the next publishing/export phase.
