# Audio Output Formats

## WAV

WAV output is generated directly by Python and requires no external encoder.

## FLAC

FLAC output requires FFmpeg.

## MP3

MP3 output requires FFmpeg with MP3 encoder support.

## Verification

```bash
ffmpeg -version
```

## Local UI

The web interface allows selecting:

- WAV;
- FLAC;
- MP3.

When FFmpeg is unavailable, WAV remains fully functional and FLAC or MP3 requests return an explicit error.
