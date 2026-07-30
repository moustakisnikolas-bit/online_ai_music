import wave
from pathlib import Path

import numpy as np
import pytest

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def _dominant_frequency(samples: np.ndarray, sample_rate: int) -> float:
    windowed = samples * np.hanning(len(samples))
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    return float(freqs[np.argmax(spectrum)])


def _read_wav_channels(path: str) -> list[np.ndarray]:
    with wave.open(path, "rb") as wav_file:
        n_channels = wav_file.getnchannels()
        raw = wav_file.readframes(wav_file.getnframes())
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32767.0
    if n_channels == 1:
        return [pcm]
    return [pcm[0::2], pcm[1::2]]


def test_sine_mode_produces_the_requested_frequency(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Freq Check Sine",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=3,
        sample_rate=44100,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    [channel] = _read_wav_channels(result.file_path)

    assert _dominant_frequency(channel, 44100) == pytest.approx(432, 1.0)


def test_binaural_beats_each_ear_carries_its_own_requested_frequency(
    tmp_path: Path,
) -> None:
    request = AudioGenerationRequest(
        title="Freq Check Binaural",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        duration_seconds=3,
        sample_rate=44100,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    left, right = _read_wav_channels(result.file_path)

    left_freq = _dominant_frequency(left, 44100)
    right_freq = _dominant_frequency(right, 44100)

    assert left_freq == pytest.approx(200, 1.0)
    assert right_freq == pytest.approx(210, 1.0)
    # The 10 Hz "beat" is a perceptual effect from the two ears' carriers
    # differing, not a literal 10 Hz component in either channel -- this
    # is the actual thing binaural_beats mode is supposed to produce.
    assert abs(right_freq - left_freq) == pytest.approx(10, 1.0)


def test_isochronic_tones_carrier_and_pulse_rate_are_both_correct(
    tmp_path: Path,
) -> None:
    request = AudioGenerationRequest(
        title="Freq Check Isochronic",
        mode=AudioMode.ISOCHRONIC_TONES,
        channels=ChannelMode.MONO,
        frequency_hz=200,
        pulse_frequency_hz=10,
        duration_seconds=3,
        sample_rate=44100,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    [channel] = _read_wav_channels(result.file_path)

    carrier_freq = _dominant_frequency(channel, 44100)
    assert carrier_freq == pytest.approx(200, 1.0)

    # The pulse rate is periodicity in the amplitude envelope, not in the
    # raw spectrum -- measured via the envelope's own FFT.
    envelope = np.abs(channel)
    pulse_freq = _dominant_frequency(envelope - envelope.mean(), 44100)
    assert pulse_freq == pytest.approx(10, 1.0)


def test_mixed_ambient_tone_layer_produces_the_requested_frequency(
    tmp_path: Path,
) -> None:
    request = AudioGenerationRequest(
        title="Freq Check Mixed Tone",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[{"kind": "tone", "frequency_hz": 432, "gain": 1.0}],
        duration_seconds=3,
        sample_rate=44100,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    [channel] = _read_wav_channels(result.file_path)

    assert _dominant_frequency(channel, 44100) == pytest.approx(432, 1.0)
