# Advanced DSP Modes

## Binaural Beats

Binaural output requires stereo audio.

The left and right channels use separate carrier frequencies. The perceived beat frequency is their absolute difference.

Example:

- left: 200 Hz
- right: 210 Hz
- difference: 10 Hz

This feature is intended for ambient, meditation and relaxation content. It must not be presented as medical treatment.

## Isochronic Tones

Isochronic tones use amplitude modulation of a carrier tone.

Parameters:

- carrier frequency;
- pulse frequency;
- modulation depth;
- amplitude;
- duration.

## Stereo Output

Supported modes can be rendered as:

- mono;
- stereo duplicated channels;
- true stereo binaural channels.

## Seamless Looping

When enabled, the engine applies a boundary crossfade to reduce discontinuity between the end and beginning of the asset.

This first implementation reduces edge mismatch. Future versions should support phase-aware and content-aware loop construction.
