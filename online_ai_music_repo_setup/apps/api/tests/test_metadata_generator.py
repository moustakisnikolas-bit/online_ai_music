from app.services.metadata_generator import (
    BABY_COMPLIANCE_NOTE,
    COMPLIANCE_NOTE,
    compliance_note_for,
    generate_metadata_package,
)


def test_metadata_package_uses_safe_language() -> None:
    package = generate_metadata_package(
        source_title="Night Rain",
        mode="mixed_ambient",
        duration_seconds=3600,
        context="sleep",
        frequency_hz=432,
        texture_mode="rain",
    )

    assert "Night Rain" in package.title
    assert "432 hz" in package.keywords
    assert "rain" in package.keywords
    assert "medical treatment" in package.description
    assert "guaranteed" in package.compliance_note


def test_metadata_package_has_unique_keywords() -> None:
    package = generate_metadata_package(
        source_title="Brown Noise",
        mode="brown_noise",
        duration_seconds=600,
        context="ambient",
    )

    assert len(package.keywords) == len(set(package.keywords))


def test_compliance_note_for_baby_concepts_is_the_baby_specific_one() -> None:
    for concept_id in ["baby_white_noise", "baby_womb", "baby_shush", "baby_lullaby", "baby_rain"]:
        note = compliance_note_for(concept_id)
        assert note == BABY_COMPLIANCE_NOTE
        # Real, specific pediatric safety content -- not just a relabeled
        # copy of the generic adult note.
        assert "crib" in note
        assert "distance" in note or "feet" in note or "meters" in note


def test_compliance_note_for_non_baby_concepts_is_the_standard_one() -> None:
    for concept_id in ["focus", "relaxation", "sleep", "chakra", "deep_focus", "triple_benefit"]:
        assert compliance_note_for(concept_id) == COMPLIANCE_NOTE


def test_metadata_package_uses_baby_compliance_note_for_baby_context() -> None:
    package = generate_metadata_package(
        source_title="Womb Whoosh",
        mode="mixed_ambient",
        duration_seconds=895,
        context="baby_womb",
    )

    assert package.compliance_note == BABY_COMPLIANCE_NOTE
