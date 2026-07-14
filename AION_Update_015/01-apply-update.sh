#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-015-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "apps/api/app/audio/types.py" \
  "apps/api/app/audio/dsp.py" \
  "apps/api/app/audio/presets.py" \
  "apps/api/app/schemas/audio.py" \
  "apps/api/app/schemas/audio_job.py" \
  "apps/api/app/models/audio_job.py" \
  "apps/api/app/repositories/audio_jobs.py" \
  "apps/api/app/services/audio_generator.py" \
  "apps/worker/app/main.py"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

cat > apps/api/app/audio/types.py <<'EOF'
from enum import StrEnum


class AudioMode(StrEnum):
    SINE = "sine"
    LAYERED_TONES = "layered_tones"
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BROWN_NOISE = "brown_noise"
    BINAURAL_BEATS = "binaural_beats"
    ISOCHRONIC_TONES = "isochronic_tones"
    MIXED_AMBIENT = "mixed_ambient"
    PRESET = "preset"


class ChannelMode(StrEnum):
    MONO = "mono"
    STEREO = "stereo"


class OutputFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"


class TextureMode(StrEnum):
    NONE = "none"
    RAIN = "rain"
    WIND = "wind"
EOF

cat >> apps/api/app/audio/dsp.py <<'EOF'


def generate_rain_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    samples = [0.0] * frame_count

    for index in range(frame_count):
        base = generator.uniform(-1.0, 1.0) * 0.35
        drop = 0.0

        if generator.random() < 0.004:
            drop = generator.uniform(0.4, 1.0)

        samples[index] = (base + drop) * amplitude

    return normalize(samples, peak=min(amplitude, 0.95))


def generate_wind_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    samples: list[float] = []
    smooth = 0.0

    for index in range(frame_count):
        white = generator.uniform(-1.0, 1.0)
        smooth = 0.995 * smooth + 0.005 * white
        swell = 0.55 + 0.45 * math.sin(
            2.0 * math.pi * 0.08 * (index / sample_rate)
        )
        samples.append(smooth * swell * amplitude)

    return normalize(samples, peak=min(amplitude, 0.95))


def mix_tracks(
    tracks: list[tuple[list[float], float]],
    peak: float = 0.95,
) -> list[float]:
    if not tracks:
        return []

    frame_count = len(tracks[0][0])

    if any(len(samples) != frame_count for samples, _ in tracks):
        raise ValueError("All mixed tracks must have equal frame counts")

    mixed = [0.0] * frame_count

    for samples, gain in tracks:
        for index, sample in enumerate(samples):
            mixed[index] += sample * gain

    return normalize(mixed, peak=peak)
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/schemas/audio.py")
content = path.read_text(encoding="utf-8")
content = content.replace(
    "from app.audio.types import AudioMode, ChannelMode, OutputFormat",
    "from app.audio.types import AudioMode, ChannelMode, OutputFormat, TextureMode",
)
needle = "    output_format: OutputFormat = OutputFormat.WAV\n"
replacement = (
    "    output_format: OutputFormat = OutputFormat.WAV\n"
    "    noise_mode: AudioMode | None = None\n"
    "    noise_gain: float = Field(default=0.65, ge=0, le=1.0)\n"
    "    tone_gain: float = Field(default=0.35, ge=0, le=1.0)\n"
    "    texture_mode: TextureMode = TextureMode.NONE\n"
    "    texture_gain: float = Field(default=0.25, ge=0, le=1.0)\n"
)
if needle not in content:
    raise SystemExit("Expected output_format field not found.")
content = content.replace(needle, replacement, 1)

validation_needle = """        if self.mode == AudioMode.ISOCHRONIC_TONES:
            if self.frequency_hz is None or self.pulse_frequency_hz is None:
                raise ValueError(
                    "frequency_hz and pulse_frequency_hz are required "
                    "for isochronic_tones"
                )
"""
validation_replacement = validation_needle + """
        if self.mode == AudioMode.MIXED_AMBIENT:
            if self.noise_mode not in {
                AudioMode.WHITE_NOISE,
                AudioMode.PINK_NOISE,
                AudioMode.BROWN_NOISE,
            }:
                raise ValueError(
                    "mixed_ambient requires noise_mode to be white_noise, "
                    "pink_noise or brown_noise"
                )
"""
if validation_needle not in content:
    raise SystemExit("Expected validation block not found.")
content = content.replace(validation_needle, validation_replacement)

path.write_text(content, encoding="utf-8")
PY

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/services/audio_generator.py")
content = path.read_text(encoding="utf-8")

content = content.replace(
    "    generate_isochronic_samples,\n",
    "    generate_isochronic_samples,\n"
    "    generate_rain_texture,\n"
    "    generate_wind_texture,\n"
    "    mix_tracks,\n",
)

marker = """    if request.mode == AudioMode.PRESET:
        preset = get_preset(request.preset_name or "")
"""
mixed_block = """    if request.mode == AudioMode.MIXED_AMBIENT:
        tracks: list[tuple[list[float], float]] = []

        if request.noise_mode == AudioMode.WHITE_NOISE:
            noise = generate_white_noise(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                request.seed,
            )
        elif request.noise_mode == AudioMode.PINK_NOISE:
            noise = generate_pink_noise(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                request.seed,
            )
        elif request.noise_mode == AudioMode.BROWN_NOISE:
            noise = generate_brown_noise(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                request.seed,
            )
        else:
            raise ValueError("Unsupported mixed ambient noise mode")

        tracks.append((noise, request.noise_gain))

        if request.layers:
            tones = generate_layered_tones(
                [(layer.frequency_hz, layer.amplitude) for layer in request.layers],
                request.duration_seconds,
                request.sample_rate,
            )
            tracks.append((tones, request.tone_gain))

        if request.texture_mode.value == "rain":
            texture = generate_rain_texture(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                request.seed,
            )
            tracks.append((texture, request.texture_gain))
        elif request.texture_mode.value == "wind":
            texture = generate_wind_texture(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                request.seed,
            )
            tracks.append((texture, request.texture_gain))

        return mix_tracks(tracks)

"""
if marker not in content:
    raise SystemExit("Expected preset marker not found.")
content = content.replace(marker, mixed_block + marker)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_mixed_ambient.py <<'EOF'
import wave
from pathlib import Path

from app.audio.types import AudioMode, ChannelMode, TextureMode
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest
from app.services.audio_generator import generate_audio


def test_generate_mixed_ambient_scene(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Rain and Brown Noise",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        noise_mode=AudioMode.BROWN_NOISE,
        noise_gain=0.7,
        texture_mode=TextureMode.RAIN,
        texture_gain=0.2,
        layers=[
            ToneLayerRequest(
                frequency_hz=432,
                amplitude=0.05,
            )
        ],
        tone_gain=0.2,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "mixed_ambient"

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000
EOF

cat > docs/06-factories/audio/mixed-ambient-scenes.md <<'EOF'
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
EOF

echo "AION Update 015 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
