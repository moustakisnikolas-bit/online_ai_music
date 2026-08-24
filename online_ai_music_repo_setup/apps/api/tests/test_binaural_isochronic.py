import wave
from pathlib import Path

import numpy as np
import pytest

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def _read_wav_channels(file_path: str) -> np.ndarray:
    with wave.open(file_path, "rb") as wav_file:
        raw = wav_file.readframes(wav_file.getnframes())
        channel_count = wav_file.getnchannels()

    interleaved = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32767.0
    return interleaved.reshape(-1, channel_count).T


def test_binaural_requires_stereo() -> None:
    with pytest.raises(ValueError):
        AudioGenerationRequest(
            title="Invalid Binaural",
            mode=AudioMode.BINAURAL_BEATS,
            channels=ChannelMode.MONO,
            left_frequency_hz=200,
            right_frequency_hz=210,
            duration_seconds=1,
            sample_rate=8000,
        )


def test_generate_binaural_stereo(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Binaural",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000


def test_generate_isochronic_tone(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Isochronic",
        mode=AudioMode.ISOCHRONIC_TONES,
        channels=ChannelMode.MONO,
        frequency_hz=220,
        pulse_frequency_hz=10,
        modulation_depth=1.0,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz == 220

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 8000


def test_mixed_ambient_binaural_tone_layer_produces_true_stereo_difference(tmp_path: Path) -> None:
    """The real point of a binaural_tone layer: left and right must
    actually carry different frequencies, not the same mono signal
    duplicated to two channels like every other mixed_ambient layer.
    """
    request = AudioGenerationRequest(
        title="Binaural Layer",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        ambient_layers=[
            {
                "kind": "binaural_tone",
                "left_frequency_hz": 200.0,
                "right_frequency_hz": 210.0,
                "gain": 1.0,
            }
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.3,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    channels = _read_wav_channels(result.file_path)

    assert channels.shape[0] == 2
    assert not np.allclose(channels[0], channels[1], atol=1e-3)


def test_mixed_ambient_binaural_tone_layer_degrades_gracefully_in_mono(tmp_path: Path) -> None:
    # The harmony-check preview renders mono -- a binaural_tone layer
    # must not crash there, and should still produce real, non-silent
    # audio (a monaural mix of both frequencies) rather than an error.
    request = AudioGenerationRequest(
        title="Binaural Layer Mono",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {
                "kind": "binaural_tone",
                "left_frequency_hz": 200.0,
                "right_frequency_hz": 210.0,
                "gain": 1.0,
            }
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.3,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    channels = _read_wav_channels(result.file_path)

    assert channels.shape[0] == 1
    assert float(np.abs(channels[0]).max()) > 0.01


def test_mixed_ambient_isochronic_layer_produces_real_amplitude_modulation(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Isochronic Layer",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {
                "kind": "isochronic",
                "carrier_frequency_hz": 300.0,
                "pulse_frequency_hz": 10.0,
                "modulation_depth": 1.0,
                "gain": 1.0,
            }
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.3,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)
    channels = _read_wav_channels(result.file_path)
    samples = channels[0]

    # A continuous (unmodulated) tone's rectified envelope stays roughly
    # constant; a fully-depth-modulated isochronic pulse should swing
    # from near its peak down to near-silence and back, several times a
    # second -- window the envelope and check it actually dips low.
    window = 80  # 10ms at 8kHz
    envelope = np.array(
        [np.abs(samples[i : i + window]).mean() for i in range(0, len(samples) - window, window)]
    )
    assert envelope.min() < 0.3 * envelope.max()
