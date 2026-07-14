# Artwork and Video Packages

## Artwork Presets

### Spotify Cover

- 3000 × 3000
- square PNG
- intended for distributor and streaming cover workflows

### YouTube Thumbnail

- 1280 × 720
- landscape PNG
- intended for YouTube thumbnail workflows

### Square Preview

- 1080 × 1080
- intended for previews and social media

## Artwork Generation

Artwork is generated procedurally from:

- title;
- subtitle;
- visual preset;
- deterministic seed.

The current version does not call an external image-generation API.

## Video Manifest

The video manifest describes:

- audio filename;
- artwork filename;
- duration;
- resolution;
- frame rate;
- output filename;
- render mode.

A later rendering stage can consume the manifest and call FFmpeg.

## Copyright Position

The procedural artwork is created by the application.

Do not add third-party logos, protected characters, album artwork or recognizable artist branding.
