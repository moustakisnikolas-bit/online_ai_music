# Long-Form Audio Rendering

## Purpose

Long-form rendering generates large audio files without loading the entire asset into memory.

## Supported Modes

- sine
- white_noise
- brown_noise
- binaural_beats
- isochronic_tones

## Rendering Strategy

The renderer:

1. calculates the exact total frame count;
2. generates a bounded chunk of frames;
3. writes the chunk directly to the WAV stream;
4. discards the chunk from memory;
5. reports progress;
6. repeats until completion.

## API Controls

- `long_form`
- `chunk_frames`
- `duration_seconds`
- `sample_rate`
- `channels`
- standard DSP parameters

## Recommended Chunk Size

Default:

```text
65536 frames
```

This provides a practical balance between memory use and write overhead.

## Target Durations

The renderer is designed for:

- 1 minute
- 10 minutes
- 30 minutes
- 1 hour
- 3 hours
- 8 hours

Actual rendering time depends on CPU, sample rate, channel count and output encoding.

## Current Limitations

Pink-noise long-form rendering is not yet included in the streaming path.

Preset and layered-tone long-form rendering should be added in a later update.
