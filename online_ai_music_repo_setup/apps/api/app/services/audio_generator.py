import struct
import uuid
import wave
from pathlib import Path

from app.audio.dsp import (
    apply_fades,
    generate_brown_noise,
    generate_layered_tones,
    generate_pink_noise,
    generate_sine_samples,
    generate_white_noise,
)
from app.audio.presets import get_preset
from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def _samples_for_request(request: AudioGenerationRequest) -> list[float]:
    if request.mode == AudioMode.SINE:
        return generate_sine_samples(
            frequency_hz=request.frequency_hz or 432.0,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
        )

    if request.mode == AudioMode.LAYERED_TONES:
        return generate_layered_tones(
            layers=[
                (layer.frequency_hz, layer.amplitude)
                for layer in request.layers
            ],
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
        )

    if request.mode == AudioMode.WHITE_NOISE:
        return generate_white_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.PINK_NOISE:
        return generate_pink_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.BROWN_NOISE:
        return generate_brown_noise(
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            seed=request.seed,
        )

    if request.mode == AudioMode.PRESET:
        preset = get_preset(request.preset_name or "")

        if preset.mode == "layered_tones":
            return generate_layered_tones(
                layers=[
                    (layer.frequency_hz, layer.amplitude)
                    for layer in preset.layers
                ],
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
            )

        if preset.mode == "pink_noise":
            return generate_pink_noise(
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
                amplitude=preset.noise_amplitude,
                seed=request.seed,
            )

        if preset.mode == "brown_noise":
            return generate_brown_noise(
                duration_seconds=request.duration_seconds,
                sample_rate=request.sample_rate,
                amplitude=preset.noise_amplitude,
                seed=request.seed,
            )

        raise ValueError(f"Unsupported preset mode: {preset.mode}")

    raise ValueError(f"Unsupported audio mode: {request.mode}")


def generate_audio(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"

    samples = _samples_for_request(request)
    samples = apply_fades(
        samples=samples,
        sample_rate=request.sample_rate,
        fade_in_seconds=request.fade_in_seconds,
        fade_out_seconds=request.fade_out_seconds,
    )

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(request.sample_rate)

        frames = bytearray()
        for sample in samples:
            pcm_value = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(struct.pack("<h", pcm_value))

        wav_file.writeframes(bytes(frames))

    response_frequency = (
        request.frequency_hz
        if request.mode == AudioMode.SINE
        else None
    )

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        mode=request.mode.value,
        frequency_hz=response_frequency,
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        status="generated",
        file_path=str(output_path),
    )


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    return generate_audio(request=request, output_dir=output_dir)
