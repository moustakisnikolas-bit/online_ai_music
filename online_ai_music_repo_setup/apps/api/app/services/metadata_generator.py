from dataclasses import dataclass


SAFE_CONTEXT_LABELS = {
    "sleep": "Sleep",
    "relaxation": "Relaxation",
    "meditation": "Meditation",
    "focus": "Focus",
    "ambient": "Ambient",
}


@dataclass(frozen=True)
class MetadataPackage:
    title: str
    subtitle: str
    description: str
    keywords: list[str]
    category: str
    language: str
    compliance_note: str


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def generate_metadata_package(
    *,
    source_title: str,
    mode: str,
    duration_seconds: int,
    context: str = "ambient",
    language: str = "en",
    frequency_hz: float | None = None,
    texture_mode: str | None = None,
) -> MetadataPackage:
    clean_title = _clean_text(source_title)
    context_label = SAFE_CONTEXT_LABELS.get(context, "Ambient")
    duration_minutes = max(1, round(duration_seconds / 60))

    details: list[str] = []

    if frequency_hz is not None:
        details.append(f"{frequency_hz:g} Hz")

    if texture_mode and texture_mode != "none":
        details.append(texture_mode.replace("_", " ").title())

    details.append(mode.replace("_", " ").title())
    details_text = " · ".join(details)

    title = f"{clean_title} — {context_label} Audio"
    subtitle = f"{details_text} · {duration_minutes} Minutes"

    description = (
        f"{clean_title} is an original {context.lower()} audio soundscape "
        f"created with {mode.replace('_', ' ')} synthesis. "
        f"Duration: approximately {duration_minutes} minutes. "
        "Designed for background listening, relaxation, meditation, sleep "
        "or focus according to personal preference. "
        "This content does not provide medical treatment or guaranteed "
        "therapeutic effects."
    )

    keywords = [
        context.lower(),
        "ambient audio",
        "relaxation",
        "background sound",
        mode.replace("_", " "),
        "original audio",
    ]

    if frequency_hz is not None:
        keywords.append(f"{frequency_hz:g} hz")

    if texture_mode and texture_mode != "none":
        keywords.append(texture_mode.replace("_", " "))

    return MetadataPackage(
        title=title,
        subtitle=subtitle,
        description=description,
        keywords=sorted(set(keywords)),
        category=context_label,
        language=language,
        compliance_note=(
            "Use as ambient or relaxation content. Do not present this asset "
            "as medical treatment, disease prevention or guaranteed therapy."
        ),
    )
