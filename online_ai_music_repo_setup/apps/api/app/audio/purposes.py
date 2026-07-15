from dataclasses import asdict, dataclass

# Recommended parameter bundles for the therapeutic-music spec's track
# categories (section 7), mapped onto the loudness targets from the same
# spec's loudness table (section 6) -- Deep Sleep -> Sleep,
# Stress Release/Anxiety-Calming/Pain-Comfort -> Relaxation,
# Meditation -> Meditation, Calm Focus -> Calm Focus. target_lufs is the
# midpoint of each range so there's headroom to move either direction.
#
# This intentionally does NOT claim to deliver the spec's instrumentation
# (piano, strings, flute) -- that needs Milestone 11 (composition). These
# are engine parameters (duration, loudness, energy arc, suggested mode)
# the current DSP-only engine can actually honor.


@dataclass(frozen=True)
class PurposeProfile:
    id: str
    label: str
    description: str
    recommended_duration_seconds: int
    target_lufs: float
    true_peak_dbtp: float
    energy_start: float
    energy_middle: float
    energy_end: float
    suggested_mode: str
    notes: str


PURPOSES: dict[str, PurposeProfile] = {
    "sleep": PurposeProfile(
        id="sleep",
        label="Deep Sleep",
        description="Long, beatless, minimal-event-density ambience for sleep.",
        recommended_duration_seconds=2700,
        target_lufs=-18.5,
        true_peak_dbtp=-2.0,
        energy_start=0.3,
        energy_middle=0.15,
        energy_end=0.05,
        suggested_mode="mixed_ambient",
        notes=(
            "Continuously fades toward near-silence rather than a "
            "noticeable ending, per the spec's resolution guidance for "
            "sleep tracks."
        ),
    ),
    "stress_relief": PurposeProfile(
        id="stress_relief",
        label="Stress Release",
        description="Warm, gradually calming ambience for stress reduction.",
        recommended_duration_seconds=1200,
        target_lufs=-15.5,
        true_peak_dbtp=-1.0,
        energy_start=0.4,
        energy_middle=0.25,
        energy_end=0.15,
        suggested_mode="mixed_ambient",
        notes="Gradual emotional release rather than a sharp resolution.",
    ),
    "meditation": PurposeProfile(
        id="meditation",
        label="Meditation",
        description="Sparse, stable ambience for meditation practice.",
        recommended_duration_seconds=1800,
        target_lufs=-16.5,
        true_peak_dbtp=-1.0,
        energy_start=0.35,
        energy_middle=0.3,
        energy_end=0.2,
        suggested_mode="mixed_ambient",
        notes="Stable throughout -- avoid dramatic energy swings.",
    ),
    "calm_focus": PurposeProfile(
        id="calm_focus",
        label="Calm Focus",
        description="Slightly more rhythmic continuity for sustained attention.",
        recommended_duration_seconds=2700,
        target_lufs=-15.0,
        true_peak_dbtp=-1.0,
        energy_start=0.4,
        energy_middle=0.4,
        energy_end=0.35,
        suggested_mode="mixed_ambient",
        notes=(
            "Flatter energy arc than the others -- focus content "
            "shouldn't dip toward sleep-like near-silence."
        ),
    ),
    "anxiety_calming": PurposeProfile(
        id="anxiety_calming",
        label="Anxiety-Calming Support",
        description="Predictable, stable-pulse ambience.",
        recommended_duration_seconds=900,
        target_lufs=-15.5,
        true_peak_dbtp=-1.0,
        energy_start=0.35,
        energy_middle=0.25,
        energy_end=0.2,
        suggested_mode="mixed_ambient",
        notes=(
            "Supplements, not replaces, appropriate healthcare -- not a "
            "clinical claim."
        ),
    ),
    "pain_comfort": PurposeProfile(
        id="pain_comfort",
        label="Pain-Comfort Support",
        description="Warm, emotionally supportive ambience.",
        recommended_duration_seconds=1800,
        target_lufs=-15.5,
        true_peak_dbtp=-1.0,
        energy_start=0.35,
        energy_middle=0.25,
        energy_end=0.2,
        suggested_mode="mixed_ambient",
        notes="Does not claim to treat the cause of pain.",
    ),
}


def list_purposes() -> list[dict]:
    return [asdict(profile) for profile in PURPOSES.values()]


def get_purpose(purpose_id: str) -> PurposeProfile:
    try:
        return PURPOSES[purpose_id]
    except KeyError as exc:
        raise ValueError(f"Unknown purpose: {purpose_id}") from exc
