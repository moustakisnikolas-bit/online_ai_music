# Ambient Audio Engine

## Supported Modes

- sine
- layered_tones
- white_noise
- pink_noise
- brown_noise
- preset

## Initial Presets

- calm-432
- focus-alpha-bed
- deep-brown
- soft-pink

## Generation Controls

- duration
- sample rate
- amplitude
- frequency
- tone layers
- deterministic seed
- fade-in
- fade-out

## Safety and Product Language

Frequency-based content must be described as ambient, relaxation, meditation, sleep or focus content.

The product must not claim that a frequency:

- cures disease;
- repairs DNA;
- removes toxins;
- replaces medical care;
- guarantees neurological outcomes.

## Technical Limits

- Maximum duration through the API: 3600 seconds
- Maximum tone layers: 16
- Maximum frequency: 20 kHz
- Maximum amplitude: 1.0
- Mono 16-bit PCM WAV output in the current version

## Future Work

- Stereo rendering
- Binaural channel separation
- Isochronic modulation
- Nature-sound layering
- Seamless loops
- Streaming generation
- Chunked long-form rendering
- FLAC and MP3 encoding
