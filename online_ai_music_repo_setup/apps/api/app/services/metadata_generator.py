from dataclasses import dataclass


COMPLIANCE_NOTE = (
    "Use as ambient or relaxation content. Do not present this asset "
    "as medical treatment, disease prevention or guaranteed therapy."
)

# Infants are a genuinely vulnerable audience, and real pediatric
# guidance on infant sound machines is specific (safe distance/volume,
# safe-sleep environment) -- worth a dedicated note rather than reusing
# the generic adult-oriented one above.
BABY_COMPLIANCE_NOTE = (
    "Ambient background sound only -- not a medical device and not a "
    "substitute for supervision. Always follow safe sleep guidance (a "
    "firm, flat sleep surface with nothing else in the crib) and keep "
    "any speaker at least 7 feet / 2 meters from the crib, played at a "
    "low volume, per pediatric hearing-safety guidance."
)

_BABY_CONCEPT_IDS = frozenset(
    {"baby_white_noise", "baby_womb", "baby_shush", "baby_lullaby", "baby_rain"}
)


def compliance_note_for(concept_id: str) -> str:
    return BABY_COMPLIANCE_NOTE if concept_id in _BABY_CONCEPT_IDS else COMPLIANCE_NOTE


SAFE_CONTEXT_LABELS = {
    "sleep": "Sleep",
    "relaxation": "Relaxation",
    "meditation": "Meditation",
    "focus": "Focus",
    "healing": "Healing",
    "study": "Study",
    "chakra": "Chakra",
    "deep_focus": "Deep Focus",
    "deep_relaxation": "Deep Relaxation",
    "deep_mind_clearness": "Deep Mind Clearness",
    "deep_sleep": "Deep Sleep",
    "deep_healing": "Deep Healing",
    "deep_study": "Deep Study",
    "deep_chakra": "Deep Chakra",
    "triple_benefit": "Sleep, Study & Focus",
    "baby_white_noise": "Baby White Noise",
    "baby_womb": "Baby Womb Sounds",
    "baby_shush": "Baby Shush Sound",
    "baby_lullaby": "Baby Lullaby",
    "baby_rain": "Baby Rain Sleep",
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


def clean_text(value: str) -> str:
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
    clean_title = clean_text(source_title)
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
        compliance_note=compliance_note_for(context),
    )
