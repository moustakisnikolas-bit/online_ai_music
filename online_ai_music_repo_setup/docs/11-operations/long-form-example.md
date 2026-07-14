# Long-Form Generation Example

Run the API:

```bash
make api
```

Submit:

```json
{
  "title": "One Hour Brown Noise",
  "mode": "brown_noise",
  "channels": "stereo",
  "duration_seconds": 3600,
  "sample_rate": 44100,
  "amplitude": 0.12,
  "fade_in_seconds": 5,
  "fade_out_seconds": 5,
  "seed": 42,
  "output_format": "wav",
  "long_form": true,
  "chunk_frames": 65536
}
```

Endpoint:

```text
POST /api/v1/audio/generate
```

For very long assets, the queue-backed worker should be preferred over synchronous HTTP generation.
