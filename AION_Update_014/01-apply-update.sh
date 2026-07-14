#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-014-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "apps/api/app/services/audio_generator.py" \
  "apps/api/app/schemas/audio.py"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

mkdir -p apps/api/app/services
mkdir -p apps/api/tests
mkdir -p docs/06-factories/audio

cat > apps/api/app/services/long_form_audio.py <<'EOF'
import math
import random
import struct
import wave
from collections.abc import Callable
from pathlib import Path

ProgressCallback = Callable[[float], None]


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _fade_gain(
    frame_index: int,
    total_frames: int,
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> float:
    gain = 1.0

    fade_in_frames = int(fade_in_seconds * sample_rate)
    fade_out_frames = int(fade_out_seconds * sample_rate)

    if fade_in_frames > 0 and frame_index < fade_in_frames:
        gain *= frame_index / fade_in_frames

    if fade_out_frames > 0 and frame_index >= total_frames - fade_out_frames:
        remaining = total_frames - frame_index - 1
        gain *= max(0.0, remaining / fade_out_frames)

    return gain


def render_long_form_wav(
    *,
    output_path: Path,
    mode: str,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    channels: int = 1,
    frequency_hz: float = 432.0,
    left_frequency_hz: float = 200.0,
    right_frequency_hz: float = 210.0,
    pulse_frequency_hz: float = 10.0,
    modulation_depth: float = 1.0,
    fade_in_seconds: float = 0.1,
    fade_out_seconds: float = 0.1,
    seed: int | None = None,
    chunk_frames: int = 65536,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    if channels not in {1, 2}:
        raise ValueError("channels must be 1 or 2")

    if chunk_frames <= 0:
        raise ValueError("chunk_frames must be positive")

    if mode == "binaural_beats" and channels != 2:
        raise ValueError("binaural_beats requires stereo output")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_frames = duration_seconds * sample_rate
    generator = random.Random(seed)
    brown_state = 0.0

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frame_index = 0

        while frame_index < total_frames:
            current_chunk = min(chunk_frames, total_frames - frame_index)
            frames = bytearray()

            for offset in range(current_chunk):
                absolute_index = frame_index + offset
                time_position = absolute_index / sample_rate
                gain = _fade_gain(
                    absolute_index,
                    total_frames,
                    sample_rate,
                    fade_in_seconds,
                    fade_out_seconds,
                )

                if mode == "sine":
                    value = amplitude * math.sin(
                        2.0 * math.pi * frequency_hz * time_position
                    )
                    channel_values = [value] * channels

                elif mode == "isochronic_tones":
                    carrier = math.sin(
                        2.0 * math.pi * frequency_hz * time_position
                    )
                    modulation = 0.5 * (
                        1.0
                        + math.sin(
                            2.0
                            * math.pi
                            * pulse_frequency_hz
                            * time_position
                        )
                    )
                    modulated_gain = (
                        (1.0 - modulation_depth)
                        + modulation_depth * modulation
                    )
                    value = amplitude * modulated_gain * carrier
                    channel_values = [value] * channels

                elif mode == "binaural_beats":
                    left = amplitude * math.sin(
                        2.0 * math.pi * left_frequency_hz * time_position
                    )
                    right = amplitude * math.sin(
                        2.0 * math.pi * right_frequency_hz * time_position
                    )
                    channel_values = [left, right]

                elif mode == "white_noise":
                    value = generator.uniform(-amplitude, amplitude)
                    channel_values = [value] * channels

                elif mode == "brown_noise":
                    brown_state += generator.uniform(-0.02, 0.02)
                    brown_state = _clamp(brown_state)
                    value = brown_state * amplitude
                    channel_values = [value] * channels

                else:
                    raise ValueError(f"Unsupported long-form mode: {mode}")

                for channel_value in channel_values:
                    pcm = int(_clamp(channel_value * gain) * 32767)
                    frames.extend(struct.pack("<h", pcm))

            wav_file.writeframesraw(bytes(frames))
            frame_index += current_chunk

            if progress_callback is not None:
                progress_callback(frame_index / total_frames)

        wav_file.writeframes(b"")

    return output_path
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/schemas/audio.py")
content = path.read_text(encoding="utf-8")

needle = "    output_format: OutputFormat = OutputFormat.WAV\n"
replacement = (
    "    output_format: OutputFormat = OutputFormat.WAV\n"
    "    long_form: bool = False\n"
    "    chunk_frames: int = Field(default=65536, ge=1024, le=1048576)\n"
)

if needle not in content:
    raise SystemExit("Expected output_format field was not found.")

path.write_text(content.replace(needle, replacement, 1), encoding="utf-8")
PY

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/services/audio_generator.py")
content = path.read_text(encoding="utf-8")

import_marker = "from app.services.audio_encoding import encode_audio\n"
replacement_import = (
    "from app.services.audio_encoding import encode_audio\n"
    "from app.services.long_form_audio import render_long_form_wav\n"
)

if import_marker not in content:
    raise SystemExit("Expected encoding import was not found.")

content = content.replace(import_marker, replacement_import)

marker = """    output_dir.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"

    if request.mode == AudioMode.BINAURAL_BEATS:
"""

replacement = """    output_dir.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"

    if request.long_form:
        channel_count = 2 if request.channels == ChannelMode.STEREO else 1

        render_long_form_wav(
            output_path=output_path,
            mode=request.mode.value,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            channels=channel_count,
            frequency_hz=request.frequency_hz or 432.0,
            left_frequency_hz=request.left_frequency_hz or 200.0,
            right_frequency_hz=request.right_frequency_hz or 210.0,
            pulse_frequency_hz=request.pulse_frequency_hz or 10.0,
            modulation_depth=request.modulation_depth,
            fade_in_seconds=request.fade_in_seconds,
            fade_out_seconds=request.fade_out_seconds,
            seed=request.seed,
            chunk_frames=request.chunk_frames,
        )

        final_output_path = encode_audio(
            source_wav=output_path,
            output_format=request.output_format.value,
        )

        response_frequency = (
            request.frequency_hz
            if request.mode in {AudioMode.SINE, AudioMode.ISOCHRONIC_TONES}
            else None
        )

        return AudioGenerationResponse(
            id=asset_id,
            title=request.title,
            mode=request.mode.value,
            channels=request.channels.value,
            frequency_hz=response_frequency,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            status="generated",
            output_format=request.output_format.value,
            file_path=str(final_output_path),
        )

    if request.mode == AudioMode.BINAURAL_BEATS:
"""

if marker not in content:
    raise SystemExit("Expected generator setup block was not found.")

path.write_text(content.replace(marker, replacement), encoding="utf-8")
PY

cat > apps/api/tests/test_long_form_audio.py <<'EOF'
import wave
from pathlib import Path

from app.services.long_form_audio import render_long_form_wav


def test_long_form_sine_has_exact_frame_count(tmp_path: Path) -> None:
    output = tmp_path / "long.wav"

    render_long_form_wav(
        output_path=output,
        mode="sine",
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.1,
        channels=1,
        frequency_hz=432,
        chunk_frames=1024,
    )

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 16000


def test_long_form_binaural_is_stereo(tmp_path: Path) -> None:
    output = tmp_path / "binaural.wav"

    render_long_form_wav(
        output_path=output,
        mode="binaural_beats",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        channels=2,
        left_frequency_hz=200,
        right_frequency_hz=210,
        chunk_frames=512,
    )

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getnframes() == 8000


def test_progress_callback_reaches_completion(tmp_path: Path) -> None:
    values: list[float] = []

    render_long_form_wav(
        output_path=tmp_path / "progress.wav",
        mode="white_noise",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        chunk_frames=1000,
        seed=42,
        progress_callback=values.append,
    )

    assert values
    assert values[-1] == 1.0
    assert all(0 < value <= 1.0 for value in values)
EOF

cat > docs/06-factories/audio/long-form-rendering.md <<'EOF'
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
EOF

cat > docs/11-operations/long-form-example.md <<'EOF'
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
EOF

echo "AION Update 014 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
