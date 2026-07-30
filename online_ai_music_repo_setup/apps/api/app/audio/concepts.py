from dataclasses import asdict, dataclass

from app.audio.types import AudioMode, TextureMode

# Album-pipeline concept catalog. Deliberately a separate, thin catalog
# from PURPOSES (app/audio/purposes.py), not a fork of it: concept ids here
# ("focus", "relaxation", "mind_clearness") are album/marketing language
# for this feature specifically, not the same axis as PURPOSES' clinical/
# therapeutic ids ("calm_focus", "stress_relief", "meditation") -- each
# concept just points at the closest existing purpose_id for its loudness/
# energy-arc numbers rather than duplicating them.
#
# Being upfront: there is no objective "top 10" or "best" data source for
# sound combinations behind any of this -- no external ranking API is
# connected. This is curated data (which natural-sound categories, which
# Hz, which instrument/scale) written using the same kind of domain
# reasoning purposes.py already uses for its own categories, not a
# scientific ranking. Solfeggio-style Hz numbers in particular are
# folklore-adjacent, carried forward here with the same disclaimer.


@dataclass(frozen=True)
class AlbumConcept:
    id: str
    label: str
    purpose_id: str
    # app/audio/sample_library.py categories to draw real recordings from.
    natural_sound_categories: tuple[str, ...]
    # Used for any category above with zero real files registered yet.
    texture_fallbacks: tuple[TextureMode, ...]
    hz_pool: tuple[float, ...]
    melody_instruments: tuple[str, ...]
    melody_scales: tuple[str, ...]
    noise_type_preference: tuple[AudioMode, ...]


CONCEPTS: dict[str, AlbumConcept] = {
    "focus": AlbumConcept(
        id="focus",
        label="Focus",
        purpose_id="calm_focus",
        natural_sound_categories=("forest", "chimes", "airplane"),
        texture_fallbacks=(TextureMode.CHIMES, TextureMode.AIRPLANE_CABIN),
        hz_pool=(528.0, 432.0, 40.0),
        melody_instruments=("warm_pad", "halo_pad"),
        melody_scales=("major_pentatonic", "dorian"),
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE),
    ),
    "relaxation": AlbumConcept(
        id="relaxation",
        label="Relaxation",
        purpose_id="stress_relief",
        natural_sound_categories=("ocean", "rain", "wind"),
        texture_fallbacks=(TextureMode.WAVES, TextureMode.RAIN, TextureMode.WIND),
        hz_pool=(396.0, 432.0, 174.0),
        melody_instruments=("choir_pad", "sweep_pad"),
        melody_scales=("natural_minor", "minor_pentatonic"),
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE),
    ),
    "mind_clearness": AlbumConcept(
        id="mind_clearness",
        label="Mind Clearness",
        purpose_id="meditation",
        natural_sound_categories=("wind", "water", "birds", "chimes"),
        texture_fallbacks=(TextureMode.WIND, TextureMode.WATER, TextureMode.BIRDS, TextureMode.CHIMES),
        hz_pool=(528.0, 639.0, 963.0),
        melody_instruments=("atmosphere_fx", "pan_flute"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.BROWN_NOISE),
    ),
}


def list_concepts() -> list[dict]:
    return [asdict(concept) for concept in CONCEPTS.values()]


def get_concept(concept_id: str) -> AlbumConcept:
    try:
        return CONCEPTS[concept_id]
    except KeyError as exc:
        raise ValueError(f"Unknown album concept: {concept_id}") from exc
