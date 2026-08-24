import random
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.audio.concepts import AlbumConcept, get_concept
from app.audio.music_theory import midi_to_hz, parse_note_name
from app.audio.purposes import get_purpose
from app.audio.sample_library import NaturalSoundSample, list_samples, resolve_sample_audio_path
from app.audio.soundfont_synth import soundfont_synth_available
from app.audio.types import AudioMode, ChannelMode, TextureMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio

_NATURAL_SOUND_GAIN_RANGE = (0.90, 0.99)
_MELODY_GAIN_RANGE = (0.50, 0.60)
_TONE_GAIN_RANGE = (0.45, 0.55)
_NOISE_GAIN_RANGE = (0.30, 0.40)
# A modest, mid-register pool -- avoids extremes that would push a melody
# line uncomfortably close to (or far from) the Hz layer regardless of
# which combination gets picked.
_MELODY_ROOT_NOTES = ("C3", "D3", "E3", "G3", "A3", "C4")

# Real EEG frequency-band ranges (distinct from the folklore-adjacent
# Solfeggio Hz values elsewhere in this module) -- delta/gamma
# deliberately excluded, not requested.
BRAINWAVE_BAND_RANGES: dict[str, tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
}
_BRAINWAVE_TECHNIQUES = ("binaural", "isochronic")
# A concept's tone_hz is chosen first, independently of the brainwave
# roll below -- if it lands under this floor, no brainwave layer is
# added for that candidate (real finding: a continuous tone under
# ~150Hz reliably trips the harmony check's low-frequency-buildup
# detector, and a binaural pair splits that same carrier even lower on
# one side, e.g. carrier 174Hz - beta/2 15Hz = 159Hz -- still fine, but
# carrier 111Hz would not be).
_BRAINWAVE_MIN_CARRIER_HZ = 150.0

_PREVIEW_DURATION_SECONDS = 45
_PREVIEW_SAMPLE_RATE = 44100


@dataclass(frozen=True)
class NaturalSoundChoice:
    kind: str  # "sample" (a real CC0 recording) or "texture" (synthesized fallback)
    sample_id: str | None = None
    texture_type: TextureMode | None = None


@dataclass(frozen=True)
class TrackCombination:
    natural_sound: NaturalSoundChoice
    natural_sound_gain: float
    melody_instrument: str | None
    melody_scale: str | None
    melody_root_note: str | None
    melody_gain: float | None
    tone_hz: float
    tone_gain: float
    noise_type: AudioMode
    noise_gain: float
    # None means the plain, single continuous tone_hz layer (the original
    # behavior). "binaural"/"isochronic" replace that layer -- see
    # to_ambient_layers() -- rather than adding a competing extra tone.
    brainwave_band: str | None = None
    brainwave_technique: str | None = None
    brainwave_pulse_hz: float | None = None

    def signature(self) -> str:
        # Identifies the *categorical* choice (not the randomized gains),
        # so a retry after a harmony-check failure can genuinely ask for a
        # different combination rather than re-testing the same one with
        # different gains -- harmony issues are about pitch/spectral
        # relationships, not gain, so re-rolling gains alone would fail
        # identically.
        natural = self.natural_sound.sample_id or self.natural_sound.texture_type
        return (
            f"{natural}|{self.melody_instrument}|{self.tone_hz}|{self.noise_type}|"
            f"{self.brainwave_band}|{self.brainwave_technique}"
        )

    def melody_root_note_hz(self) -> float | None:
        if self.melody_root_note is None:
            return None
        return midi_to_hz(parse_note_name(self.melody_root_note))

    def to_ambient_layers(self) -> list[dict]:
        layers: list[dict] = []

        if self.natural_sound.kind == "sample":
            layers.append(
                {
                    "kind": "sample",
                    "sample_id": self.natural_sound.sample_id,
                    "gain": self.natural_sound_gain,
                }
            )
        else:
            layers.append(
                {
                    "kind": "texture",
                    "texture_type": self.natural_sound.texture_type,
                    "gain": self.natural_sound_gain,
                }
            )

        if self.melody_instrument is not None:
            layers.append(
                {
                    "kind": "synth",
                    "instrument": self.melody_instrument,
                    "root_note": self.melody_root_note,
                    "scale": self.melody_scale,
                    "pattern": "up_down",
                    "gain": self.melody_gain,
                }
            )

        if self.brainwave_technique == "binaural":
            half_beat = self.brainwave_pulse_hz / 2.0
            layers.append(
                {
                    "kind": "binaural_tone",
                    "left_frequency_hz": self.tone_hz - half_beat,
                    "right_frequency_hz": self.tone_hz + half_beat,
                    "gain": self.tone_gain,
                }
            )
        elif self.brainwave_technique == "isochronic":
            layers.append(
                {
                    "kind": "isochronic",
                    "carrier_frequency_hz": self.tone_hz,
                    "pulse_frequency_hz": self.brainwave_pulse_hz,
                    # Real finding: full depth (1.0, the schema default)
                    # pulses all the way down to near-silence and back,
                    # which the harmony check's "sudden loudness jump"
                    # detector (correctly) flags every time over a 45s
                    # window -- that's an inherent property of a deep
                    # isochronic pulse, not a bug in the detector. A more
                    # moderate depth keeps a real, audible pulse without
                    # tripping it.
                    "modulation_depth": 0.6,
                    "gain": self.tone_gain,
                }
            )
        else:
            layers.append({"kind": "tone", "frequency_hz": self.tone_hz, "gain": self.tone_gain})

        layers.append({"kind": "noise", "noise_type": self.noise_type, "gain": self.noise_gain})

        return layers


def _real_available_sample_ids(category: str) -> list[str]:
    matches = []

    for entry in list_samples():
        if entry["category"].lower() != category.lower():
            continue

        sample = NaturalSoundSample(**entry)

        try:
            resolve_sample_audio_path(sample)
        except (FileNotFoundError, ValueError):
            continue

        matches.append(sample.id)

    return matches


def _natural_sound_pool(concept: AlbumConcept) -> list[NaturalSoundChoice]:
    pool: list[NaturalSoundChoice] = []

    for category in concept.natural_sound_categories:
        pool.extend(
            NaturalSoundChoice(kind="sample", sample_id=sample_id)
            for sample_id in _real_available_sample_ids(category)
        )

    if not pool:
        pool = [
            NaturalSoundChoice(kind="texture", texture_type=texture_type)
            for texture_type in concept.texture_fallbacks
        ]

    return pool


def generate_candidate_combinations(
    concept_id: str,
    *,
    count: int = 10,
    seed: int | None = None,
    exclude_signatures: frozenset[str] = frozenset(),
) -> list[TrackCombination]:
    concept = get_concept(concept_id)
    natural_pool = _natural_sound_pool(concept)

    if not natural_pool:
        raise ValueError(
            f"No natural sounds or fallback textures available for concept {concept_id!r}"
        )

    melody_available = soundfont_synth_available()
    rng = random.Random(seed)
    seen_signatures = set(exclude_signatures)
    candidates: list[TrackCombination] = []

    # Generous ceiling so a small pool (few real samples registered, or a
    # narrow Hz/noise pool) can't spin forever trying to find `count`
    # unique signatures -- returns fewer than `count` rather than hanging.
    max_attempts = count * 20

    for _ in range(max_attempts):
        if len(candidates) >= count:
            break

        natural = rng.choice(natural_pool)
        tone_hz = rng.choice(concept.hz_pool)
        noise_type = rng.choice(concept.noise_type_preference)

        if melody_available:
            melody_instrument = rng.choice(concept.melody_instruments)
            melody_scale = rng.choice(concept.melody_scales)
            melody_root_note = rng.choice(_MELODY_ROOT_NOTES)
        else:
            melody_instrument = melody_scale = melody_root_note = None

        brainwave_band = brainwave_technique = None
        brainwave_pulse_hz = None
        if (
            concept.brainwave_bands
            and tone_hz >= _BRAINWAVE_MIN_CARRIER_HZ
            and rng.random() < concept.brainwave_layer_probability
        ):
            brainwave_band = rng.choice(concept.brainwave_bands)
            brainwave_technique = rng.choice(_BRAINWAVE_TECHNIQUES)
            band_low, band_high = BRAINWAVE_BAND_RANGES[brainwave_band]
            brainwave_pulse_hz = rng.uniform(band_low, band_high)

        combination = TrackCombination(
            natural_sound=natural,
            natural_sound_gain=rng.uniform(*_NATURAL_SOUND_GAIN_RANGE),
            melody_instrument=melody_instrument,
            melody_scale=melody_scale,
            melody_root_note=melody_root_note,
            melody_gain=rng.uniform(*_MELODY_GAIN_RANGE) if melody_instrument else None,
            tone_hz=tone_hz,
            tone_gain=rng.uniform(*_TONE_GAIN_RANGE),
            noise_type=noise_type,
            noise_gain=rng.uniform(*_NOISE_GAIN_RANGE),
            brainwave_band=brainwave_band,
            brainwave_technique=brainwave_technique,
            brainwave_pulse_hz=brainwave_pulse_hz,
        )

        signature = combination.signature()
        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        candidates.append(combination)

    return candidates


def safe_fallback_combination(concept_id: str) -> TrackCombination:
    # Deliberately no melody layer -- guarantees no tone/melody beating is
    # even possible -- and centered, safely-inside-range gains. The last
    # resort after MAX_HARMONY_ATTEMPTS real candidates all fail their
    # harmony check.
    concept = get_concept(concept_id)
    natural_pool = _natural_sound_pool(concept)
    natural = natural_pool[0] if natural_pool else NaturalSoundChoice(
        kind="texture", texture_type=TextureMode.RAIN
    )

    return TrackCombination(
        natural_sound=natural,
        natural_sound_gain=0.95,
        melody_instrument=None,
        melody_scale=None,
        melody_root_note=None,
        melody_gain=None,
        tone_hz=concept.hz_pool[0],
        tone_gain=0.5,
        noise_type=concept.noise_type_preference[0],
        noise_gain=0.35,
    )


def render_harmony_preview(
    combination: TrackCombination,
    concept: AlbumConcept,
    output_dir: Path,
) -> tuple[np.ndarray, int]:
    # A short (45s) preview render, with the concept's real mastering
    # settings applied so the check validates what will actually ship --
    # never the full 1-hour render. Mono, since the harmony check cares
    # about spectral/pitch content, not stereo imaging.
    purpose = get_purpose(concept.purpose_id)

    request = AudioGenerationRequest(
        title="Harmony Check Preview",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=combination.to_ambient_layers(),
        duration_seconds=_PREVIEW_DURATION_SECONDS,
        sample_rate=_PREVIEW_SAMPLE_RATE,
        fade_in_seconds=0,
        fade_out_seconds=0,
        target_lufs=purpose.target_lufs,
        true_peak_dbtp=purpose.true_peak_dbtp,
        apply_mastering_eq=True,
    )
    result = generate_audio(request, output_dir)

    with wave.open(result.file_path, "rb") as wav_file:
        raw = wav_file.readframes(wav_file.getnframes())

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32767.0

    return samples, _PREVIEW_SAMPLE_RATE
