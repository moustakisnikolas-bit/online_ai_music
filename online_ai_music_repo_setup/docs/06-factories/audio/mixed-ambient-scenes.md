# Mixed Ambient Scenes

## Purpose

Mixed ambient scenes combine multiple original procedural layers into one asset.

## Supported Layers

### Noise Bed

- white noise
- pink noise
- brown noise

### Tone Layer

One or more configurable sine-tone layers.

### Texture Layer

- rain
- wind

## Controls

- noise gain
- tone gain
- texture gain
- deterministic seed
- mono or stereo
- duration
- sample rate
- fades
- output format

## Example

```json
{
  "title": "Rain and Brown Noise",
  "mode": "mixed_ambient",
  "channels": "stereo",
  "noise_mode": "brown_noise",
  "noise_gain": 0.7,
  "texture_mode": "rain",
  "texture_gain": 0.2,
  "layers": [
    {
      "frequency_hz": 432,
      "amplitude": 0.05
    }
  ],
  "tone_gain": 0.2,
  "duration_seconds": 600,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 3,
  "fade_out_seconds": 3,
  "seed": 42,
  "output_format": "wav"
}
```

## Current Nature Texture Scope

The rain and wind textures are procedural synthetic textures.

They are not recordings and therefore do not introduce third-party recording rights.

Future versions may support licensed field recordings with provenance metadata.
