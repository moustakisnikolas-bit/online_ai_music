from pathlib import Path

import numpy as np

from app.audio.dsp import apply_energy_envelope, generate_chimes_texture
from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_apply_energy_envelope_scales_start_middle_end() -> None:
    samples = np.ones(1000, dtype=np.float32)
    shaped = apply_energy_envelope(samples, energy_start=0.2, energy_middle=1.0, energy_end=0.4)

    assert abs(float(shaped[0]) - 0.2) < 0.01
    assert abs(float(shaped[len(shaped) // 2]) - 1.0) < 0.05
    assert abs(float(shaped[-1]) - 0.4) < 0.01


def test_apply_energy_envelope_flat_is_a_no_op() -> None:
    samples = np.random.default_rng(1).uniform(-0.5, 0.5, 1000).astype(np.float32)
    shaped = apply_energy_envelope(samples, 1.0, 1.0, 1.0)

    assert np.allclose(shaped, samples, atol=1e-6)


def test_apply_energy_envelope_handles_empty_array() -> None:
    samples = np.array([], dtype=np.float32)
    shaped = apply_energy_envelope(samples, 0.5, 0.5, 0.5)

    assert len(shaped) == 0


def test_generate_chimes_texture_tuning_hz_scales_pitches() -> None:
    default_tuning = generate_chimes_texture(10, 8000, 0.5, seed=1, tuning_hz=440.0)
    alternate_tuning = generate_chimes_texture(10, 8000, 0.5, seed=1, tuning_hz=432.0)

    # Same seed means the same chime timing/note choices, but a different
    # tuning reference means different actual frequencies -- the two
    # signals should differ (not be bit-identical) despite matching seeds.
    assert not np.allclose(default_tuning, alternate_tuning)
    assert len(default_tuning) == len(alternate_tuning) == 80000


def test_generate_chimes_texture_defaults_to_440() -> None:
    explicit = generate_chimes_texture(5, 8000, 0.5, seed=3, tuning_hz=440.0)
    implicit = generate_chimes_texture(5, 8000, 0.5, seed=3)

    assert np.array_equal(explicit, implicit)


def test_generate_audio_with_energy_envelope_end_to_end(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Fading Sine",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.3,
        fade_in_seconds=0,
        fade_out_seconds=0,
        energy_start=1.0,
        energy_middle=0.5,
        energy_end=0.1,
    )

    result = generate_audio(request, tmp_path)
    assert result.status == "generated"


def test_generate_audio_with_alternate_tuning_end_to_end(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="A432 Chimes",
        mode=AudioMode.MIXED_AMBIENT,
        ambient_layers=[{"kind": "noise", "noise_type": "brown_noise", "gain": 0.5}],
        textures=[{"texture_type": "chimes", "gain": 0.3}],
        tuning_hz=432.0,
        duration_seconds=10,
        sample_rate=8000,
        amplitude=0.3,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=1,
    )

    result = generate_audio(request, tmp_path)
    assert result.status == "generated"
