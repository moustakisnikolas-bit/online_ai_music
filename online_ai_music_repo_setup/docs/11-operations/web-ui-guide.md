# AION Web UI Guide

## Start the API

```bash
make api
```

## Open the Interface

```text
http://127.0.0.1:8000/
```

or:

```text
http://127.0.0.1:8000/app
```

## Current Capabilities

The first interface supports:

- sine tones;
- white noise;
- pink noise;
- brown noise;
- binaural beats;
- isochronic tones;
- presets;
- mono and stereo output;
- duration;
- sample rate;
- amplitude;
- fades;
- deterministic seed;
- audio preview;
- WAV download.

## Current Limitation

Generation is synchronous in this first web interface.

Queue-backed job creation remains available through the API and worker architecture.

A later version should connect the UI to asynchronous jobs with progress reporting.
