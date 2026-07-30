from pathlib import Path

import pytest

from app.audio.validation import check_combination_harmony
from app.schemas.audio import AudioGenerationRequest
from app.services import album_combinations
from app.services.album_combinations import (
    _NATURAL_SOUND_GAIN_RANGE,
    _NOISE_GAIN_RANGE,
    _TONE_GAIN_RANGE,
    generate_candidate_combinations,
    render_harmony_preview,
    safe_fallback_combination,
)


@pytest.mark.parametrize("concept_id", ["focus", "relaxation", "mind_clearness"])
def test_generate_candidate_combinations_returns_ten_unique_per_concept(concept_id: str) -> None:
    combinations = generate_candidate_combinations(concept_id, count=10, seed=1)

    assert len(combinations) == 10
    signatures = {c.signature() for c in combinations}
    assert len(signatures) == 10


def test_generate_candidate_combinations_is_reproducible_for_a_given_seed() -> None:
    first = generate_candidate_combinations("focus", count=10, seed=42)
    second = generate_candidate_combinations("focus", count=10, seed=42)

    assert [c.signature() for c in first] == [c.signature() for c in second]


def test_generate_candidate_combinations_gains_are_within_the_specified_ranges() -> None:
    combinations = generate_candidate_combinations("relaxation", count=10, seed=5)

    for combination in combinations:
        assert _NATURAL_SOUND_GAIN_RANGE[0] <= combination.natural_sound_gain <= _NATURAL_SOUND_GAIN_RANGE[1]
        assert _TONE_GAIN_RANGE[0] <= combination.tone_gain <= _TONE_GAIN_RANGE[1]
        assert _NOISE_GAIN_RANGE[0] <= combination.noise_gain <= _NOISE_GAIN_RANGE[1]

        if combination.melody_gain is not None:
            from app.services.album_combinations import _MELODY_GAIN_RANGE

            assert _MELODY_GAIN_RANGE[0] <= combination.melody_gain <= _MELODY_GAIN_RANGE[1]


def test_generate_candidate_combinations_respects_exclude_signatures() -> None:
    first_batch = generate_candidate_combinations("focus", count=10, seed=9)
    excluded = frozenset(c.signature() for c in first_batch)

    second_batch = generate_candidate_combinations(
        "focus", count=5, seed=9, exclude_signatures=excluded
    )

    assert excluded.isdisjoint({c.signature() for c in second_batch})


def test_generate_candidate_combinations_rejects_unknown_concept() -> None:
    with pytest.raises(ValueError, match="Unknown album concept"):
        generate_candidate_combinations("not_a_real_concept")


def test_generate_candidate_combinations_omits_melody_when_soundfont_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(album_combinations, "soundfont_synth_available", lambda: False)

    combinations = generate_candidate_combinations("focus", count=5, seed=2)

    assert all(c.melody_instrument is None for c in combinations)
    assert all(c.melody_gain is None for c in combinations)


def test_generate_candidate_combinations_includes_melody_when_soundfont_available(monkeypatch) -> None:
    monkeypatch.setattr(album_combinations, "soundfont_synth_available", lambda: True)

    combinations = generate_candidate_combinations("focus", count=5, seed=2)

    assert any(c.melody_instrument is not None for c in combinations)


def test_to_ambient_layers_produces_a_valid_request() -> None:
    combination = generate_candidate_combinations("relaxation", count=1, seed=11)[0]

    request = AudioGenerationRequest(
        title="Combination Smoke Test",
        mode="mixed_ambient",
        ambient_layers=combination.to_ambient_layers(),
        duration_seconds=5,
        sample_rate=8000,
    )

    assert len(request.ambient_layers) >= 3  # natural sound + tone + noise, plus melody if available


def test_safe_fallback_combination_has_no_melody() -> None:
    fallback = safe_fallback_combination("focus")

    assert fallback.melody_instrument is None
    assert fallback.melody_gain is None
    assert fallback.melody_root_note_hz() is None


def test_safe_fallback_combination_produces_a_valid_request() -> None:
    fallback = safe_fallback_combination("mind_clearness")

    request = AudioGenerationRequest(
        title="Fallback Smoke Test",
        mode="mixed_ambient",
        ambient_layers=fallback.to_ambient_layers(),
        duration_seconds=5,
        sample_rate=8000,
    )

    assert len(request.ambient_layers) == 3


def test_render_harmony_preview_and_check_combination_harmony_real_end_to_end(
    tmp_path: Path,
) -> None:
    # Real generation, real harmony check -- no melody is included on this
    # test machine (FluidSynth unavailable), so this exercises the full
    # real path without needing a soundfont.
    from app.audio.concepts import get_concept

    concept = get_concept("relaxation")
    combination = safe_fallback_combination("relaxation")

    samples, sample_rate = render_harmony_preview(combination, concept, tmp_path)

    assert samples.size > 0

    report = check_combination_harmony(
        samples,
        sample_rate,
        tone_frequency_hz=combination.tone_hz,
        melody_root_note_hz=combination.melody_root_note_hz(),
    )

    assert report.passed, report.issues
