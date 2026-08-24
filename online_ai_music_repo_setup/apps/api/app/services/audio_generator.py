import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, TypeVar

import numpy as np

from app.audio.dsp import (
    apply_breathing_sync,
    apply_energy_envelope,
    apply_fades,
    apply_loop_crossfade,
    compute_duck_envelope,
    generate_airplane_cabin_texture,
    generate_binaural_channels,
    generate_birds_texture,
    generate_blue_noise,
    generate_brown_noise,
    generate_chimes_texture,
    generate_deep_waterfall_texture,
    generate_distant_thunder_texture,
    generate_fire_texture,
    generate_isochronic_samples,
    generate_rain_texture,
    generate_thunder_texture,
    generate_violet_noise,
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
    apply_reverb,
    fold_bass_to_mono as fold_bass_to_mono_channels,
    limit_true_peak,
    measure_lufs,
    true_peak_dbtp,
)
from app.audio.validation import validate_audio
from app.audio.music_theory import generate_pattern
from app.audio.presets import get_preset
from app.audio.sample_library import get_sample, resolve_sample_audio_path
from app.audio.soundfont_synth import GM_INSTRUMENTS, build_cc_values, render_pattern
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
    TextureMode.DEEP_WATERFALL: generate_deep_waterfall_texture,
    TextureMode.DISTANT_THUNDER: generate_distant_thunder_texture,
    TextureMode.AIRPLANE_CABIN: generate_airplane_cabin_texture,
}


# -14 LUFS at amplitude=1.0 (a streaming-loudness-style reference) and
# scaled down in dB terms by amplitude, so "amplitude" keeps its existing
# meaning as a relative level control across every texture type. Steady
# broadband textures (rain/wind/water/waves) already land close to this
# naturally, so in practice this constant mostly only matters for the
# spiky ones being boosted toward it.
_TEXTURE_REFERENCE_LUFS_AT_UNITY = -14.0

# Textures whose whole character is a rare, sharp event (a boom, a pop, a
# chirp) against near-silence -- these trigger sidechain ducking of the
# calmer layers around them. Steady/broadband textures (rain, wind,
# water, waves, deep_waterfall, airplane_cabin) don't have discrete
# events to protect and are never triggers, only duckable targets. See
# compute_duck_envelope() in dsp.py and _apply_sidechain_ducking() below.
_DUCKING_TEXTURE_TYPES = frozenset(
    {
        TextureMode.FIRE,
        TextureMode.THUNDER,
        TextureMode.DISTANT_THUNDER,
        TextureMode.BIRDS,
        TextureMode.CHIMES,
    }
)


def _apply_sidechain_ducking(
    trigger_tracks: list[tuple[np.ndarray, float]],
    sample_rate: int,
) -> np.ndarray | None:
    """Combines the duck envelopes of every trigger track into one, via a
    running minimum (whichever trigger is ducking hardest at a given
    moment wins, rather than multiple triggers compounding into an
    over-ducked mix). Returns None when there are no trigger tracks (the
    common case), so callers can skip the extra multiply entirely.

    Takes only the already-generated trigger tracks -- typically 0-3,
    bounded by how many event-type textures were actually selected, not
    by the schema's full layer-count maximum -- so this stays cheap even
    though a single request can technically ask for many layers.
    """
    combined: np.ndarray | None = None

    for samples, _gain in trigger_tracks:
        envelope = compute_duck_envelope(samples, sample_rate)
        combined = envelope if combined is None else np.minimum(combined, envelope)

    return combined


def _balance_texture_loudness(
    samples: np.ndarray, sample_rate: int, amplitude: float
) -> np.ndarray:
    # Texture generators have very different crest factors: rain/wind/
    # water/waves are steady broadband noise, while fire/thunder/birds/
    # chimes are mostly silence punctuated by sparse transient spikes. At
    # the same requested amplitude, a spiky texture can measure over 10dB
    # quieter in *perceived* loudness (LUFS) than a steady one, even
    # though both hit the same peak -- so when multiple textures are
    # summed, the quieter/spikier one is barely audible under a steadier
    # one. Only ever boosting (never cutting) means a texture that's
    # already loud enough -- every steady one, in practice -- is passed
    # through completely unchanged; the true-peak limit afterward is what
    # actually keeps a boosted texture's rare pops from overpowering the
    # rest of the mix, rather than an arbitrary cap on the boost itself.
    current_lufs = measure_lufs(samples, sample_rate)

    if not np.isfinite(current_lufs):
        return samples.astype(np.float32, copy=False)

    target_lufs = _TEXTURE_REFERENCE_LUFS_AT_UNITY + 20.0 * np.log10(max(amplitude, 1e-4))
    boost_db = max(0.0, target_lufs - current_lufs)

    if boost_db <= 0.0:
        return samples.astype(np.float32, copy=False)

    gain_linear = 10.0 ** (boost_db / 20.0)
    boosted = (samples * gain_linear).astype(np.float32, copy=False)
    return limit_true_peak(boosted, target_dbtp=-3.0)


def _generate_texture(
    texture_type: TextureMode,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
    tuning_hz: float,
) -> np.ndarray:
    # tuning_hz only matters for chimes (the only texture with named,
    # A440-relative pitches) -- passed as a keyword rather than added to
    # every texture generator's signature, since the other seven ignore
    # it entirely.
    generator = _TEXTURE_GENERATORS[texture_type]

    if texture_type == TextureMode.CHIMES:
        samples = generator(duration_seconds, sample_rate, amplitude, seed, tuning_hz=tuning_hz)
    else:
        samples = generator(duration_seconds, sample_rate, amplitude, seed)

    return _balance_texture_loudness(samples, sample_rate, amplitude)


def _apply_global_textures(base: np.ndarray, request: AudioGenerationRequest) -> np.ndarray:
    # Layers request.textures under any mode's primary signal (not just
    # mixed_ambient's own ambient_layers). Called once per channel; texture
    # generation is deterministic per seed, so calling it for both the left
    # and right binaural channels yields the identical texture bed added to
    # each side, rather than disturbing the binaural L/R phase relationship
    # with independently-random content per ear.
    if not request.textures:
        return base

    # Pass 1: generate only the trigger-type textures (typically 0-3, not
    # the full textures list) and derive one combined duck envelope from
    # them -- see _apply_sidechain_ducking for why this stays bounded
    # regardless of how many textures a request has.
    trigger_tracks: dict[int, tuple[np.ndarray, float]] = {}

    for index, texture in enumerate(request.textures):
        if texture.texture_type in _DUCKING_TEXTURE_TYPES:
            layer_seed = None if request.seed is None else request.seed + 1000 + index
            samples = _generate_texture(
                texture.texture_type,
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                layer_seed,
                request.tuning_hz,
            )
            trigger_tracks[index] = (samples, texture.gain)

    duck_envelope = _apply_sidechain_ducking(list(trigger_tracks.values()), request.sample_rate)

    # Pass 2: the original lazy, one-track-at-a-time generation, feeding
    # mix_tracks exactly as before -- only the base and any non-trigger
    # texture get the combined envelope multiplied in (skipped entirely
    # when there's nothing to duck); already-generated trigger tracks are
    # reused from pass 1 rather than regenerated, and are never ducked
    # themselves -- an event texture doesn't duck itself, only the calmer
    # layers around it.
    def _tracks():
        yield (base * duck_envelope if duck_envelope is not None else base), 1.0

        for index, texture in enumerate(request.textures):
            if index in trigger_tracks:
                samples, gain = trigger_tracks[index]
                yield samples, gain
                continue

            layer_seed = None if request.seed is None else request.seed + 1000 + index
            samples = _generate_texture(
                texture.texture_type,
                request.duration_seconds,
                request.sample_rate,
                request.amplitude,
                layer_seed,
                request.tuning_hz,
            )
            yield (
                samples * duck_envelope if duck_envelope is not None else samples,
                texture.gain,
            )

    return mix_tracks(_tracks())


def _mono_samples(request: AudioGenerationRequest, channel: str | None = None) -> np.ndarray:
    # channel is only meaningful for a MIXED_AMBIENT request containing a
    # binaural_tone layer: "left"/"right" render that layer's true stereo-
    # differentiated frequency; None (mono/preview) mixes both of the
    # binaural pair's frequencies together instead, which is a real,
    # different-but-related technique (a monaural beat) rather than a
    # silent no-op or a crash.
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
        def _generate_ambient_layer_samples(layer, layer_seed) -> np.ndarray:
            if layer.kind == "noise":
                if layer.noise_type == AudioMode.WHITE_NOISE:
                    return generate_white_noise(
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                        layer_seed,
                    )
                if layer.noise_type == AudioMode.PINK_NOISE:
                    return generate_pink_noise(
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                        layer_seed,
                    )
                if layer.noise_type == AudioMode.BLUE_NOISE:
                    return generate_blue_noise(
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                        layer_seed,
                    )
                if layer.noise_type == AudioMode.VIOLET_NOISE:
                    return generate_violet_noise(
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                        layer_seed,
                    )
                return generate_brown_noise(
                    request.duration_seconds,
                    request.sample_rate,
                    request.amplitude,
                    layer_seed,
                )

            if layer.kind == "tone":
                return generate_sine_samples(
                    layer.frequency_hz,
                    request.duration_seconds,
                    request.sample_rate,
                    request.amplitude,
                )

            if layer.kind == "binaural_tone":
                if channel == "left":
                    return generate_sine_samples(
                        layer.left_frequency_hz,
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                    )
                if channel == "right":
                    return generate_sine_samples(
                        layer.right_frequency_hz,
                        request.duration_seconds,
                        request.sample_rate,
                        request.amplitude,
                    )
                return generate_layered_tones(
                    [
                        (layer.left_frequency_hz, request.amplitude),
                        (layer.right_frequency_hz, request.amplitude),
                    ],
                    request.duration_seconds,
                    request.sample_rate,
                )

            if layer.kind == "isochronic":
                return generate_isochronic_samples(
                    carrier_frequency_hz=layer.carrier_frequency_hz,
                    pulse_frequency_hz=layer.pulse_frequency_hz,
                    duration_seconds=request.duration_seconds,
                    sample_rate=request.sample_rate,
                    amplitude=request.amplitude,
                    modulation_depth=layer.modulation_depth,
                )

            if layer.kind == "texture":
                return _generate_texture(
                    layer.texture_type,
                    request.duration_seconds,
                    request.sample_rate,
                    request.amplitude,
                    layer_seed,
                    request.tuning_hz,
                )

            if layer.kind == "sample":
                sample = get_sample(layer.sample_id)
                sample_path = resolve_sample_audio_path(sample)
                return load_sample_layer(
                    sample_path,
                    request.duration_seconds,
                    request.sample_rate,
                )

            if layer.kind == "synth":
                events = generate_pattern(
                    layer.root_note,
                    layer.scale,
                    layer.pattern,
                    layer.octave_range,
                    layer.note_duration_seconds,
                    request.duration_seconds,
                    layer_seed,
                )
                cc_values = build_cc_values(
                    layer.attack_seconds,
                    layer.release_seconds,
                    layer.filter_cutoff,
                    layer.filter_resonance,
                )
                return render_pattern(
                    events,
                    request.duration_seconds,
                    request.sample_rate,
                    GM_INSTRUMENTS[layer.instrument],
                    cc_values,
                )

            raise ValueError(f"Unsupported ambient layer kind: {layer.kind}")

        # Pass 1: generate only the trigger-type layers (a "texture" kind
        # layer whose texture_type is an event-driven one -- noise/tone/
        # sample layers are never triggers, only duckable targets) and
        # derive one combined duck envelope, same bounded-memory approach
        # as _apply_global_textures above.
        trigger_tracks: dict[int, tuple[np.ndarray, float]] = {}

        for index, layer in enumerate(request.ambient_layers):
            if layer.kind == "texture" and layer.texture_type in _DUCKING_TEXTURE_TYPES:
                layer_seed = None if request.seed is None else request.seed + index
                samples = _generate_ambient_layer_samples(layer, layer_seed)
                trigger_tracks[index] = (samples, layer.gain)

        duck_envelope = _apply_sidechain_ducking(
            list(trigger_tracks.values()), request.sample_rate
        )

        def _ambient_layer_tracks():
            for index, layer in enumerate(request.ambient_layers):
                if index in trigger_tracks:
                    samples, gain = trigger_tracks[index]
                    yield samples, gain
                    continue

                layer_seed = None if request.seed is None else request.seed + index
                samples = _generate_ambient_layer_samples(layer, layer_seed)
                yield (
                    samples * duck_envelope if duck_envelope is not None else samples,
                    layer.gain,
                )

        # Non-trigger layers are still generated lazily and consumed one
        # at a time by mix_tracks, so only one layer's array (plus the
        # running mix, plus the small set of already-generated trigger
        # tracks) is ever resident, instead of holding every layer in
        # memory at once.
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

    if request.mode == AudioMode.SYNTHESIZER:
        events = generate_pattern(
            request.synth_root_note or "",
            request.synth_scale or "",
            request.synth_pattern or "",
            request.synth_octave_range,
            request.synth_note_duration_seconds,
            request.duration_seconds,
            request.seed,
        )
        cc_values = build_cc_values(
            request.synth_attack_seconds,
            request.synth_release_seconds,
            request.synth_filter_cutoff,
            request.synth_filter_resonance,
        )
        return render_pattern(
            events,
            request.duration_seconds,
            request.sample_rate,
            GM_INSTRUMENTS[request.synth_instrument or ""],
            cc_values,
        )

    raise ValueError(f"Unsupported mono audio mode: {request.mode}")


def _process_channel(
    samples: np.ndarray,
    request: AudioGenerationRequest,
) -> np.ndarray:
    samples = apply_energy_envelope(
        samples,
        request.energy_start,
        request.energy_middle,
        request.energy_end,
    )

    if request.breathing_sync_enabled:
        samples = apply_breathing_sync(
            samples,
            request.sample_rate,
            request.breathing_inhale_seconds,
            request.breathing_exhale_seconds,
            request.breathing_sync_depth,
        )

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


_T = TypeVar("_T")
_R = TypeVar("_R")


def _parallel_map(func: Callable[[_T], _R], items: list[_T]) -> list[_R]:
    # Mastering steps like limit_true_peak and apply_mastering_eq process
    # each channel independently (no shared state), and their cost is
    # dominated by scipy C routines (resample_poly, lfilter) that release
    # the GIL during the heavy computation -- confirmed empirically
    # (2-channel true_peak_dbtp: ~2x wall-clock speedup, bit-identical
    # results). Real threads, not multiprocessing, since there's no need to
    # duplicate the arrays across process boundaries. Skips the pool
    # entirely for <=1 item (mono), where it would only add overhead.
    if len(items) <= 1:
        return [func(item) for item in items]

    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        return list(pool.map(func, items))


def _apply_mastering(
    channels: list[np.ndarray],
    request: AudioGenerationRequest,
) -> tuple[list[np.ndarray], float | None, list[str]]:
    # Opt-in post-processing pass over the finished channels, right before
    # writing to disk. Order matters: bass mono-fold, EQ, and reverb shape
    # the spectrum/stereo image first, then LUFS normalization sets the
    # overall level, then true-peak limiting is applied last so it can't
    # be undone by a later gain change.
    if request.fold_bass_to_mono and len(channels) == 2:
        channels[0], channels[1] = fold_bass_to_mono_channels(
            channels[0], channels[1], request.sample_rate
        )

    if request.apply_mastering_eq:
        channels = _parallel_map(
            lambda channel: apply_mastering_eq(channel, request.sample_rate), channels
        )

    if request.apply_reverb:
        # A different seed per channel so stereo reverb tails are
        # decorrelated rather than identical -- an identical L/R tail
        # would collapse the reverb to a mono-sounding wash.
        base_seed = request.seed if request.seed is not None else 42
        channels = _parallel_map(
            lambda indexed_channel: apply_reverb(
                indexed_channel[1],
                request.sample_rate,
                decay_seconds=request.reverb_decay_seconds,
                wet_level=request.reverb_wet_level,
                seed=base_seed + indexed_channel[0],
            ),
            list(enumerate(channels)),
        )

    if request.target_lufs is not None:
        # Normalize using a single gain derived from the channel-averaged
        # signal, applied uniformly to every channel, rather than
        # normalizing each channel independently (which would alter the
        # L/R balance).
        combined = np.mean(np.stack(channels), axis=0) if len(channels) > 1 else channels[0]
        current_lufs = measure_lufs(combined, request.sample_rate)

        if np.isfinite(current_lufs):
            loudness_gain_db = request.target_lufs - current_lufs

            # A signal with a high crest factor (loud peaks, quiet
            # integrated average -- exactly what a strong energy envelope
            # produces) can ask for a loudness gain that would push the
            # true peak well past true_peak_dbtp. Cap the gain here so
            # peak safety wins over hitting the exact LUFS target, rather
            # than applying the full gain and letting limit_true_peak claw
            # it back afterward -- that sequence silently fights itself:
            # the correction after the fact drags the loudness back down
            # by whatever the peak overshoot was, defeating the
            # normalization instead of coordinating with it. The
            # response's loudness_lufs will honestly reflect a target that
            # couldn't be fully reached, rather than silently missing it.
            current_peak_dbtp = true_peak_dbtp(combined)
            if np.isfinite(current_peak_dbtp):
                max_gain_db = request.true_peak_dbtp - current_peak_dbtp
                loudness_gain_db = min(loudness_gain_db, max_gain_db)

            gain_linear = 10.0 ** (loudness_gain_db / 20.0)
            channels = [(channel * gain_linear).astype(np.float32) for channel in channels]

    channels = _parallel_map(
        lambda channel: limit_true_peak(channel, request.true_peak_dbtp), channels
    )

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

    mixed_ambient_binaural = request.mode == AudioMode.MIXED_AMBIENT and any(
        layer.kind == "binaural_tone" for layer in request.ambient_layers
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
    elif mixed_ambient_binaural and request.channels == ChannelMode.STEREO:
        # A binaural_tone layer only has a real effect in true stereo --
        # the natural-sound/noise/melody layers are rendered identically
        # on both sides (same seed), only the tone layer's frequency
        # actually differs left vs right.
        left = _apply_global_textures(_mono_samples(request, channel="left"), request)
        right = _apply_global_textures(_mono_samples(request, channel="right"), request)
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
