import struct
import uuid
import wave
from pathlib import Path

from app.audio.dsp import (
    apply_fades,
    apply_loop_crossfade,
    generate_binaural_channels,
    generate_brown_noise,
    generate_isochronic_samples,
    generate_layered_tones,
    generate_pink_noise,
    generate_sine_samples,
    generate_white_noise,
)
from app.audio.presets import get_preset
from app.audio.types import AudioMode, ChannelMode
from app.services.audio_encoding import encode_audio
from app.services.long_form_audio import render_long_form_wav
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def _mono_samples(request: AudioGenerationRequest) -> list[float]:
    if request.mode == AudioMode.SINE:
        return generate_sine_samples(
            request.frequency_hz or 432.0,
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
        )

    if request.mode == AudioMode.LAYERED_TONES:
        return generate_layered_tones(
            [(layer.frequency_hz, layer.amplitude) for layer in request.layers],
            request.duration_seconds,
            request.sample_rate,
        )

    if request.mode == AudioMode.WHITE_NOISE:
        return generate_white_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.PINK_NOISE:
        return generate_pink_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.BROWN_NOISE:
        return generate_brown_noise(
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
            request.seed,
        )

    if request.mode == AudioMode.ISOCHRONIC_TONES:
        return generate_isochronic_samples(
            carrier_frequency_hz=request.frequency_hz or 220.0,
            pulse_frequency_hz=request.pulse_frequency_hz or 10.0,
            duration_seconds=request.duration_seconds,
            sample_rate=request.sample_rate,
            amplitude=request.amplitude,
            modulation_depth=request.modulation_depth,
        )

    if request.mode == AudioMode.PRESET:
        preset = get_preset(request.preset_name or "")

        if preset.mode == "layered_tones":
            return generate_layered_tones(
                [(layer.frequency_hz, layer.amplitude) for layer in preset.layers],
                request.duration_seconds,
                request.sample_rate,
            )

        if preset.mode == "pink_noise":
            return generate_pink_noise(
                request.duration_seconds,
                request.sample_rate,
                preset.noise_amplitude,
                request.seed,
            )

        if preset.mode == "brown_noise":
            return generate_brown_noise(
                request.duration_seconds,
                request.sample_rate,
                preset.noise_amplitude,
                request.seed,
            )

    raise ValueError(f"Unsupported mono audio mode: {request.mode}")


def _process_channel(
    samples: list[float],
    request: AudioGenerationRequest,
) -> list[float]:
    samples = apply_fades(
        samples,
        request.sample_rate,
        request.fade_in_seconds,
        request.fade_out_seconds,
    )

    if request.seamless_loop:
        samples = apply_loop_crossfade(
            samples,
            request.sample_rate,
            request.loop_crossfade_seconds,
        )

    return samples


def _write_wav(
    output_path: Path,
    sample_rate: int,
    channels: list[list[float]],
) -> None:
    frame_count = len(channels[0])

    if any(len(channel) != frame_count for channel in channels):
        raise ValueError("All channels must have the same frame count")

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(len(channels))
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()

        for frame_index in range(frame_count):
            for channel in channels:
                sample = max(-1.0, min(1.0, channel[frame_index]))
                frames.extend(struct.pack("<h", int(sample * 32767)))

        wav_file.writeframes(bytes(frames))


def generate_audio(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)
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
        left, right = generate_binaural_channels(
            request.left_frequency_hz or 200.0,
            request.right_frequency_hz or 210.0,
            request.duration_seconds,
            request.sample_rate,
            request.amplitude,
        )
        channels = [
            _process_channel(left, request),
            _process_channel(right, request),
        ]
    else:
        mono = _process_channel(_mono_samples(request), request)

        if request.channels == ChannelMode.STEREO:
            channels = [mono[:], mono[:]]
        else:
            channels = [mono]

    _write_wav(output_path, request.sample_rate, channels)

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


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    return generate_audio(request=request, output_dir=output_dir)
