from app.services.metadata_generator import generate_metadata_package


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
