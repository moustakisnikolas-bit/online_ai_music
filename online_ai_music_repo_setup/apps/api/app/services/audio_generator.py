import uuid
import wave
from pathlib import Path

import numpy as np

from app.audio.dsp import (
    apply_fades,
    apply_loop_crossfade,
    generate_binaural_channels,
    generate_birds_texture,
    generate_brown_noise,
    generate_chimes_texture,
    generate_fire_texture,
    generate_isochronic_samples,
    generate_rain_texture,
    generate_thunder_texture,
    generate_water_texture,
    generate_waves_texture,
    generate_wind_texture,
    load_sample_layer,
    mix_tracks,
    generate_layered_tones,
    generate_pink_noise,
    generate_sine_samples,
    generate_white_noise,
)
from app.audio.mastering import (
    apply_mastering_eq,
    fold_bass_to_mono as fold_bass_to_mono_channels,
    limit_true_peak,
    measure_lufs,
)
from app.audio.validation import validate_audio
from app.audio.presets import get_preset
from app.audio.sample_library import get_sample, resolve_sample_audio_path
from app.audio.types import AudioMode, ChannelMode, TextureMode
from app.services.audio_encoding import encode_audio
from app.services.long_form_audio import render_long_form_wav
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse

# All texture generators share the same (duration_seconds, sample_rate,
# amplitude, seed) signature, so a lookup table scales better than a
# growing if/elif chain as more texture types get added.
_TEXTURE_GENERATORS = {
    TextureMode.RAIN: generate_rain_texture,
    TextureMode.WIND: generate_wind_texture,
    TextureMode.WAVES: generate_waves_texture,
    TextureMode.BIRDS: generate_birds_texture,
    TextureMode.FIRE: generate_fire_texture,
    TextureMode.WATER: generate_water_texture,
    TextureMode.THUNDER: generate_thunder_texture,
    TextureMode.CHIMES: generate_chimes_texture,
}


def _apply_global_textures(base: np.ndarray, request: AudioGenerationRequest) -> np.ndarray:
    # Layers request.textures under any mode's primary signal (not just
    # mixed_ambient's own ambient_layers). Called once per channel; texture
    # generation is deterministic per seed, so calling it for both the left
    # and right binaural channels yields the identical texture bed added to
    # each side, rather than disturbing the binaural L/R phase relationship
    # with independently-random content per ear.
    if not request.textures:
        return base

    def _tracks():
        yield base, 1.0

        for index, texture in enumerate(request.textures):
            layer_seed = None if request.seed is None else request.seed + 1000 + index
            generator = _TEXTURE_GENERATORS[texture.texture_type]
            samples = generator(
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                layer_seed,
            )
            yield samples, texture.gain

    return mix_tracks(_tracks())


def _mono_samples(request: AudioGenerationRequest) -> np.ndarray:
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

    if request.mode == AudioMode.MIXED_AMBIENT:
        def _ambient_layer_tracks():
            for index, layer in enumerate(request.ambient_layers):
                layer_seed = None if request.seed is None else request.seed + index

                if layer.kind == "noise":
                    if layer.noise_type == AudioMode.WHITE_NOISE:
                        samples = generate_white_noise(
                            request.duration_seconds,
                            request.sample_rate,
                            request.amplitude,
                            layer_seed,
                        )
                    elif layer.noise_type == AudioMode.PINK_NOISE:
                        samples = generate_pink_noise(
                            request.duration_seconds,
                            request.sample_rate,
                            request.amplitude,
                            layer_seed,
                        )
                    else:
                        samples = generate_brown_noise(
                            request.duration_seconds,
                            request.sample_rate,
                            request.amplitude,
                            layer_seed,
                        )
                elif layer.kind == "tone":
                    samples = generate_sine_samples(
                        layer.frequency_hz,
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                    )
                elif layer.kind == "texture":
                    generator = _TEXTURE_GENERATORS[layer.texture_type]
                    samples = generator(
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                        layer_seed,
                    )
                elif layer.kind == "sample":
                    sample = get_sample(layer.sample_id)
                    sample_path = resolve_sample_audio_path(sample)
                    samples = load_sample_layer(
                        sample_path,
                        request.duration_seconds,
                        request.sample_rate,
                    )
                else:
                    raise ValueError(f"Unsupported ambient layer kind: {layer.kind}")

                yield samples, layer.gain

        # Layers are generated lazily and consumed one at a time by
        # mix_tracks, so only one layer's array (plus the running mix) is
        # ever resident, instead of holding every layer in memory at once.
        return mix_tracks(_ambient_layer_tracks())

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
    samples: np.ndarray,
    request: AudioGenerationRequest,
) -> np.ndarray:
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
    channels: list[np.ndarray],
) -> None:
    frame_count = len(channels[0])

    if any(len(channel) != frame_count for channel in channels):
        raise ValueError("All channels must have the same frame count")

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(len(channels))
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        interleaved = np.stack(channels, axis=1)
        pcm = (np.clip(interleaved, -1.0, 1.0) * 32767).astype("<i2")

        wav_file.writeframes(pcm.tobytes())


def _apply_mastering(
    channels: list[np.ndarray],
    request: AudioGenerationRequest,
) -> tuple[list[np.ndarray], float | None, list[str]]:
    # Opt-in post-processing pass over the finished channels, right before
    # writing to disk. Order matters: bass mono-fold and EQ shape the
    # spectrum/stereo image first, then LUFS normalization sets the
    # overall level, then true-peak limiting is applied last so it can't
    # be undone by a later gain change.
    if request.fold_bass_to_mono and len(channels) == 2:
        channels[0], channels[1] = fold_bass_to_mono_channels(
            channels[0], channels[1], request.sample_rate
        )

    if request.apply_mastering_eq:
        channels = [apply_mastering_eq(channel, request.sample_rate) for channel in channels]

    if request.target_lufs is not None:
        # Normalize using a single gain derived from the channel-averaged
        # signal, applied uniformly to every channel, rather than
        # normalizing each channel independently (which would alter the
        # L/R balance).
        combined = np.mean(np.stack(channels), axis=0) if len(channels) > 1 else channels[0]
        current_lufs = measure_lufs(combined, request.sample_rate)

        if np.isfinite(current_lufs):
            gain_linear = 10.0 ** ((request.target_lufs - current_lufs) / 20.0)
            channels = [(channel * gain_linear).astype(np.float32) for channel in channels]

    channels = [limit_true_peak(channel, request.true_peak_dbtp) for channel in channels]

    final_combined = np.mean(np.stack(channels), axis=0) if len(channels) > 1 else channels[0]
    final_lufs = measure_lufs(final_combined, request.sample_rate)
    report = validate_audio(
        final_combined,
        request.sample_rate,
        check_loop_seam=request.seamless_loop,
    )

    return channels, (final_lufs if np.isfinite(final_lufs) else None), report.issues


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
        left = _apply_global_textures(left, request)
        right = _apply_global_textures(right, request)
        channels = [
            _process_channel(left, request),
            _process_channel(right, request),
        ]
    else:
        mono = _apply_global_textures(_mono_samples(request), request)
        mono = _process_channel(mono, request)

        if request.channels == ChannelMode.STEREO:
            channels = [mono.copy(), mono.copy()]
        else:
            channels = [mono]

    channels, loudness_lufs, validation_warnings = _apply_mastering(channels, request)

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
        loudness_lufs=loudness_lufs,
        validation_warnings=validation_warnings,
    )


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    return generate_audio(request=request, output_dir=output_dir)
