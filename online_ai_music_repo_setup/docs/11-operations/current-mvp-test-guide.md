# Current MVP Test Guide

## Automated Tests

```bash
make test
```

## Local API

```bash
make api
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Synchronous Audio Generation

Use:

```text
POST /api/v1/audio/generate
```

Example:

```json
{
  "title": "432 Hz Stereo Test",
  "mode": "sine",
  "channels": "stereo",
  "frequency_hz": 432,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1,
  "seamless_loop": false
}
```

The response contains a generated file path.

Use the returned filename with:

```text
GET /api/v1/audio/assets/{filename}
GET /api/v1/audio/assets/{filename}/download
```

## Binaural Example

```json
{
  "title": "10 Hz Alpha Binaural",
  "mode": "binaural_beats",
  "channels": "stereo",
  "left_frequency_hz": 200,
  "right_frequency_hz": 210,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1
}
```

## Isochronic Example

```json
{
  "title": "10 Hz Alpha Isochronic",
  "mode": "isochronic_tones",
  "channels": "mono",
  "frequency_hz": 220,
  "pulse_frequency_hz": 10,
  "modulation_depth": 1.0,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1
}
```
