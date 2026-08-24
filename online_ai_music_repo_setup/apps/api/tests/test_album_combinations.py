from pathlib import Path

import pytest

from app.audio.concepts import CONCEPTS, get_concept
from app.audio.validation import check_combination_harmony
from app.schemas.audio import AudioGenerationRequest
from app.services import album_combinations
from app.services.album_combinations import (
    BRAINWAVE_BAND_RANGES,
    _BRAINWAVE_MIN_CARRIER_HZ,
    _NATURAL_SOUND_GAIN_RANGE,
    _NOISE_GAIN_RANGE,
    _TONE_GAIN_RANGE,
    TrackCombination,
    generate_candidate_combinations,
    render_harmony_preview,
    safe_fallback_combination,
)


# Parametrized over every real registered concept (not a hardcoded list) so
# a newly added concept is automatically covered here -- catches a concept
# whose natural_sound_categories/texture_fallbacks resolve to an empty pool
# before it ever reaches production.
@pytest.mark.parametrize("concept_id", list(CONCEPTS.keys()))
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


@pytest.mark.parametrize(
    "concept_id",
    [
        "sleep", "healing", "study", "chakra",
        "deep_focus", "deep_relaxation", "deep_mind_clearness", "deep_sleep",
        "deep_healing", "deep_study", "deep_chakra", "triple_benefit",
    ],
)
def test_render_harmony_preview_real_end_to_end_for_each_new_concept(
    tmp_path: Path, concept_id: str
) -> None:
    # Each new concept points at its own purpose_id (sleep/meditation/
    # calm_focus) with its own loudness targets -- a real render per
    # concept catches a purpose lookup typo or an out-of-range gain
    # combination that a purely data-level assertion would miss.
    concept = get_concept(concept_id)
    combination = safe_fallback_combination(concept_id)

    samples, sample_rate = render_harmony_preview(combination, concept, tmp_path)

    assert samples.size > 0

    report = check_combination_harmony(
        samples,
        sample_rate,
        tone_frequency_hz=combination.tone_hz,
        melody_root_note_hz=combination.melody_root_note_hz(),
    )

    assert report.passed, report.issues


def test_safe_fallback_combination_never_includes_a_brainwave_layer() -> None:
    # The zero-retry last resort stays maximally conservative -- brainwave
    # layers are new and only proven safe above _BRAINWAVE_MIN_CARRIER_HZ,
    # so they're kept out of the one path that can't afford to fail.
    for concept_id in CONCEPTS:
        fallback = safe_fallback_combination(concept_id)
        assert fallback.brainwave_technique is None
        assert fallback.brainwave_band is None


def test_generate_candidate_combinations_only_uses_the_concepts_own_bands() -> None:
    combinations = generate_candidate_combinations("mind_clearness", count=30, seed=3)

    for combination in combinations:
        if combination.brainwave_band is not None:
            assert combination.brainwave_band in get_concept("mind_clearness").brainwave_bands


def test_generate_candidate_combinations_never_gives_a_low_tone_a_brainwave_layer() -> None:
    # Real finding: a continuous tone under ~150Hz destabilizes the
    # mastering limiter, and a binaural pair splits that carrier even
    # lower on one side -- low tone_hz picks must never get paired with
    # a brainwave layer regardless of how the random roll lands.
    combinations = generate_candidate_combinations("study", count=60, seed=11)

    low_tone_combinations = [c for c in combinations if c.tone_hz < _BRAINWAVE_MIN_CARRIER_HZ]
    assert any(low_tone_combinations)  # sanity: study's pool does include low values
    assert all(c.brainwave_technique is None for c in low_tone_combinations)


def test_generate_candidate_combinations_produces_both_brainwave_techniques_over_many_seeds() -> None:
    # Not a statistical guarantee, but with 60 candidates across a
    # concept whose pool is always >= _BRAINWAVE_MIN_CARRIER_HZ (chakra's
    # lowest Hz is 396), both techniques should show up for real.
    combinations = generate_candidate_combinations("chakra", count=60, seed=5)
    techniques = {c.brainwave_technique for c in combinations if c.brainwave_technique is not None}

    assert techniques == {"binaural", "isochronic"}


def test_deep_concepts_have_a_higher_brainwave_layer_probability_than_base_concepts() -> None:
    for concept_id in ["focus", "relaxation", "mind_clearness", "sleep", "healing", "study", "chakra"]:
        assert get_concept(concept_id).brainwave_layer_probability == 0.5

    for concept_id in [
        "deep_focus", "deep_relaxation", "deep_mind_clearness", "deep_sleep",
        "deep_healing", "deep_study", "deep_chakra",
    ]:
        assert get_concept(concept_id).brainwave_layer_probability == 0.8


def test_deep_concept_actually_produces_more_brainwave_layers_than_its_base_concept() -> None:
    # Proves brainwave_layer_probability is really wired through to
    # generation, not just set as inert data -- same seed, same
    # attempt-count ceiling, only the concept (and its probability)
    # differs.
    base_combinations = generate_candidate_combinations("chakra", count=60, seed=21)
    deep_combinations = generate_candidate_combinations("deep_chakra", count=60, seed=21)

    base_rate = sum(1 for c in base_combinations if c.brainwave_technique is not None) / len(base_combinations)
    deep_rate = sum(1 for c in deep_combinations if c.brainwave_technique is not None) / len(deep_combinations)

    assert deep_rate > base_rate


def test_track_combination_signature_distinguishes_brainwave_variants() -> None:
    base = safe_fallback_combination("chakra")
    binaural = TrackCombination(
        **{**base.__dict__, "brainwave_band": "theta", "brainwave_technique": "binaural", "brainwave_pulse_hz": 6.0}
    )
    isochronic = TrackCombination(
        **{**base.__dict__, "brainwave_band": "theta", "brainwave_technique": "isochronic", "brainwave_pulse_hz": 6.0}
    )

    assert len({base.signature(), binaural.signature(), isochronic.signature()}) == 3


def test_to_ambient_layers_emits_binaural_tone_instead_of_plain_tone() -> None:
    base = safe_fallback_combination("chakra")
    combination = TrackCombination(
        **{
            **base.__dict__,
            "brainwave_band": "alpha",
            "brainwave_technique": "binaural",
            "brainwave_pulse_hz": 10.0,
        }
    )

    layers = combination.to_ambient_layers()
    kinds = [layer["kind"] for layer in layers]

    assert "binaural_tone" in kinds
    assert "tone" not in kinds
    binaural_layer = next(layer for layer in layers if layer["kind"] == "binaural_tone")
    assert binaural_layer["left_frequency_hz"] == combination.tone_hz - 5.0
    assert binaural_layer["right_frequency_hz"] == combination.tone_hz + 5.0


def test_to_ambient_layers_emits_isochronic_instead_of_plain_tone() -> None:
    base = safe_fallback_combination("chakra")
    combination = TrackCombination(
        **{
            **base.__dict__,
            "brainwave_band": "alpha",
            "brainwave_technique": "isochronic",
            "brainwave_pulse_hz": 10.0,
        }
    )

    layers = combination.to_ambient_layers()
    kinds = [layer["kind"] for layer in layers]

    assert "isochronic" in kinds
    assert "tone" not in kinds
    isochronic_layer = next(layer for layer in layers if layer["kind"] == "isochronic")
    assert isochronic_layer["carrier_frequency_hz"] == combination.tone_hz
    assert isochronic_layer["pulse_frequency_hz"] == 10.0


@pytest.mark.parametrize("technique", ["binaural", "isochronic"])
def test_render_harmony_preview_passes_with_a_real_brainwave_layer(
    tmp_path: Path, technique: str
) -> None:
    # Proves _BRAINWAVE_MIN_CARRIER_HZ is actually a safe floor, the same
    # way the study concept's hz_pool ordering bug was caught earlier --
    # a real render, not an assumption.
    concept = get_concept("chakra")
    base = safe_fallback_combination("chakra")
    band_low, band_high = BRAINWAVE_BAND_RANGES["alpha"]
    combination = TrackCombination(
        **{
            **base.__dict__,
            "brainwave_band": "alpha",
            "brainwave_technique": technique,
            "brainwave_pulse_hz": (band_low + band_high) / 2.0,
        }
    )

    samples, sample_rate = render_harmony_preview(combination, concept, tmp_path)

    report = check_combination_harmony(
        samples,
        sample_rate,
        tone_frequency_hz=combination.tone_hz,
        melody_root_note_hz=combination.melody_root_note_hz(),
    )

    assert report.passed, report.issues
