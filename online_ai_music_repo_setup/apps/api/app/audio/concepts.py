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
    # Real EEG bands (see album_combinations.BRAINWAVE_BAND_RANGES) this
    # concept's random combinations may add a binaural/isochronic layer
    # for. Empty means never -- not every concept needs one.
    brainwave_bands: tuple[str, ...] = ()
    # Chance a candidate combination gets a brainwave layer at all, when
    # brainwave_bands is non-empty (see album_combinations.py). Default
    # matches every existing concept's prior fixed 0.5 -- only the
    # "deep_*" concepts below override it, grounded in a real finding
    # that "binaural" shows up meaningfully more often in their own
    # research than in the base concepts'.
    brainwave_layer_probability: float = 0.5


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
        brainwave_bands=("beta", "alpha"),
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
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE, AudioMode.VIOLET_NOISE),
        brainwave_bands=("theta", "alpha"),
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
        brainwave_bands=("theta", "alpha"),
    ),
    # Added from real YouTube competitive research (see
    # app/services/concept_research.py) -- "sleep", "healing" and "study"
    # were consistently among the top-performing themes in this niche
    # and each maps cleanly onto this engine's existing capabilities.
    "sleep": AlbumConcept(
        id="sleep",
        label="Sleep",
        purpose_id="sleep",
        natural_sound_categories=("night", "rain", "wind"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WIND, TextureMode.WATER),
        hz_pool=(174.0, 111.0, 396.0),
        melody_instruments=("atmosphere_fx", "sweep_pad"),
        melody_scales=("natural_minor", "dorian"),
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE, AudioMode.VIOLET_NOISE),
        # Theta only, not beta/alpha -- theta is the drowsy/pre-sleep band;
        # anything faster works against the concept.
        brainwave_bands=("theta",),
    ),
    "healing": AlbumConcept(
        id="healing",
        label="Healing",
        purpose_id="meditation",
        natural_sound_categories=("forest", "ocean"),
        texture_fallbacks=(TextureMode.WATER, TextureMode.CHIMES),
        hz_pool=(432.0, 528.0, 639.0),
        melody_instruments=("choir_pad", "pan_flute"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.BROWN_NOISE),
        brainwave_bands=("theta", "alpha"),
    ),
    "study": AlbumConcept(
        id="study",
        label="Study",
        purpose_id="calm_focus",
        natural_sound_categories=("forest", "night"),
        texture_fallbacks=(TextureMode.CHIMES, TextureMode.AIRPLANE_CABIN),
        # Not literal 10/14Hz "alpha wave" tones -- this engine renders
        # tone_hz as a single continuous sine, and anything that low is
        # sub-audible and destabilizes the mastering limiter (real finding:
        # failed the harmony check's loudness-jump detector). 741Hz is
        # first (not 40 or 111) because safe_fallback_combination always
        # uses hz_pool[0] with no retry, and a continuous tone under
        # ~150Hz reliably trips the harmony check's low-frequency-buildup
        # detector (measured: 111Hz -> ratio 0.71, 40Hz -> 0.64, vs
        # 741Hz -> 0.001) -- confirmed for real via a direct render, not
        # assumed. 40/111 stay in the pool for regular (retry-protected)
        # random combinations, matching how focus already keeps 40Hz at
        # the end of its own pool for the same reason. The real alpha/beta
        # framing this niche actually wants now lives in brainwave_bands
        # below (a true isochronic/binaural pulse), not in hz_pool.
        hz_pool=(741.0, 111.0, 40.0),
        melody_instruments=("warm_pad", "halo_pad"),
        melody_scales=("major_pentatonic", "dorian"),
        noise_type_preference=(AudioMode.WHITE_NOISE, AudioMode.PINK_NOISE, AudioMode.BLUE_NOISE),
        brainwave_bands=("beta", "alpha"),
    ),
    # 7 real chakra/Solfeggio frequencies, root to crown -- the same
    # folklore-adjacent Hz convention already used elsewhere in this
    # module, not a scientific claim. Skipped in the first pass of this
    # catalog (only one supporting data point in the research at the
    # time); revisited once the user asked for it explicitly.
    "chakra": AlbumConcept(
        id="chakra",
        label="Chakra",
        purpose_id="meditation",
        natural_sound_categories=("night", "ocean"),
        texture_fallbacks=(TextureMode.CHIMES, TextureMode.WATER),
        hz_pool=(396.0, 417.0, 528.0, 639.0, 741.0, 852.0, 963.0),
        melody_instruments=("pan_flute", "atmosphere_fx"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.VIOLET_NOISE),
        brainwave_bands=("theta", "alpha"),
    ),
    # "Deep" variants -- real "ultra" (25-video, duration-bucketed)
    # research per concept (see app/services/concept_research.py,
    # queried under "deep_focus" etc.) found two consistent real
    # patterns versus the base concepts: rain is the dominant real
    # natural-sound signal across almost every "deep X" query
    # regardless of X, and "binaural" shows up in real titles noticeably
    # more often -- reflected here as "rain" leading every
    # natural_sound_categories tuple and a higher
    # brainwave_layer_probability (0.8 vs the 0.5 default).
    #
    # One real finding NOT reflected below: real "deep X" videos skew
    # heavily toward long-form (3-10+ hours -- see each concept's
    # top_duration_buckets in ConceptResearch). This engine still caps
    # every track at TRACK_DURATION_SECONDS (14:55) because the
    # connected YouTube channel isn't verified for longer uploads --
    # deliberately not decided here; see the standing "pursue channel
    # verification?" question flagged to the user.
    "deep_focus": AlbumConcept(
        id="deep_focus",
        label="Deep Focus",
        purpose_id="calm_focus",
        natural_sound_categories=("rain", "forest", "night"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.CHIMES, TextureMode.AIRPLANE_CABIN),
        # Real Hz mentions were sparse (title text leans on "deep"/
        # "long"/"study" wording more than explicit Hz) -- 417 is the
        # one real find; 528/432 carried over from the base Focus
        # concept for a fuller pool, 40 kept last per the existing
        # low-carrier-safety rule.
        hz_pool=(417.0, 528.0, 432.0, 40.0),
        melody_instruments=("warm_pad", "halo_pad"),
        melody_scales=("major_pentatonic", "dorian"),
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE),
        brainwave_bands=("beta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    "deep_relaxation": AlbumConcept(
        id="deep_relaxation",
        label="Deep Relaxation",
        purpose_id="stress_relief",
        natural_sound_categories=("rain", "ocean", "wind"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WAVES, TextureMode.WIND),
        hz_pool=(432.0, 417.0, 396.0, 174.0),
        melody_instruments=("choir_pad", "sweep_pad"),
        melody_scales=("natural_minor", "minor_pentatonic"),
        noise_type_preference=(AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE, AudioMode.VIOLET_NOISE),
        brainwave_bands=("theta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    "deep_mind_clearness": AlbumConcept(
        id="deep_mind_clearness",
        label="Deep Mind Clearness",
        purpose_id="meditation",
        natural_sound_categories=("rain", "wind", "water"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WIND, TextureMode.WATER),
        hz_pool=(432.0, 528.0, 639.0, 963.0),
        melody_instruments=("atmosphere_fx", "pan_flute"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.BROWN_NOISE),
        brainwave_bands=("theta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    "deep_sleep": AlbumConcept(
        id="deep_sleep",
        label="Deep Sleep",
        purpose_id="sleep",
        natural_sound_categories=("rain", "night", "ocean"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WIND, TextureMode.WATER),
        # No real Hz mentions at all in this query's real results
        # (sample_size 25, zero) -- deep sleep content is noise/texture
        # driven, not tone-driven. Kept the base Sleep concept's pool
        # rather than inventing one with no real support.
        hz_pool=(174.0, 111.0, 396.0),
        melody_instruments=("atmosphere_fx", "sweep_pad"),
        melody_scales=("natural_minor", "dorian"),
        # Real finding this one *does* differ from base Sleep on: white
        # noise (4 mentions) outweighed brown noise (1) in real deep
        # sleep titles, where base Sleep's pool led with brown/pink.
        noise_type_preference=(AudioMode.WHITE_NOISE, AudioMode.BROWN_NOISE, AudioMode.PINK_NOISE),
        brainwave_bands=("theta",),
        brainwave_layer_probability=0.8,
    ),
    "deep_healing": AlbumConcept(
        id="deep_healing",
        label="Deep Healing",
        purpose_id="meditation",
        natural_sound_categories=("rain", "forest", "ocean"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WATER, TextureMode.CHIMES),
        # 1111Hz is a real (if thin, 1-mention) find not seen in any
        # other concept's research -- kept last, after the well-
        # supported 528/432/741.
        hz_pool=(432.0, 528.0, 741.0, 1111.0),
        melody_instruments=("choir_pad", "pan_flute"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.BROWN_NOISE),
        brainwave_bands=("theta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    "deep_study": AlbumConcept(
        id="deep_study",
        label="Deep Study",
        purpose_id="calm_focus",
        natural_sound_categories=("rain", "forest", "night"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.CHIMES, TextureMode.AIRPLANE_CABIN),
        # Real research here found only 40Hz explicitly, already covered
        # by the base Study concept's own pool -- reused as-is rather
        # than inventing a second near-duplicate ordering.
        hz_pool=(741.0, 111.0, 40.0),
        melody_instruments=("warm_pad", "halo_pad"),
        melody_scales=("major_pentatonic", "dorian"),
        noise_type_preference=(AudioMode.WHITE_NOISE, AudioMode.PINK_NOISE, AudioMode.BLUE_NOISE),
        # Strongest real "binaural" theme signal of any concept
        # researched (5 of 25 real titles) -- the clearest evidence
        # behind raising brainwave_layer_probability for the whole
        # "deep_*" group.
        brainwave_bands=("beta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    "deep_chakra": AlbumConcept(
        id="deep_chakra",
        label="Deep Chakra",
        purpose_id="meditation",
        natural_sound_categories=("rain", "night", "ocean"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.CHIMES, TextureMode.WATER),
        # 174Hz is a real find here that never appeared in base Chakra's
        # research -- added alongside the strongest-supported values
        # (432/528) from the base concept's own 7-tone pool.
        hz_pool=(432.0, 528.0, 417.0, 639.0, 174.0),
        melody_instruments=("pan_flute", "atmosphere_fx"),
        melody_scales=("dorian", "major_pentatonic"),
        noise_type_preference=(AudioMode.PINK_NOISE, AudioMode.VIOLET_NOISE),
        brainwave_bands=("theta", "alpha"),
        brainwave_layer_probability=0.8,
    ),
    # Modeled on the two actual highest-viewed real videos found across
    # every query researched so far (25-video "ultra" pulls specifically
    # on their own patterns): "White Noise Black Screen | Sleep, Study,
    # Focus | 10 Hours" (369M views, 19/25 white-noise-dominant,
    # multi-benefit title, near-zero Hz content) and "Study Music Alpha
    # Waves: ... Brain Power, Focus Concentration Music" (235M views,
    # real 40Hz/binaural framing). Two real, repeated patterns worth
    # acting on: (1) titling a track for multiple real uses at once
    # outperforms a single-benefit title -- reflected directly in this
    # concept's own multi-part label, which the existing title/hashtag
    # generators already handle with no code changes needed; (2) the
    # single biggest real gap versus the #1 video itself is that it has
    # *no* tonal or brainwave content at all -- pure noise, nothing
    # else. brainwave_layer_probability is raised to 0.9 (the highest
    # in the catalog) specifically to make that the differentiator: real
    # white noise plus what the market leader doesn't offer.
    "triple_benefit": AlbumConcept(
        id="triple_benefit",
        label="Sleep, Study & Focus",
        purpose_id="calm_focus",
        natural_sound_categories=("rain", "night"),
        texture_fallbacks=(TextureMode.RAIN, TextureMode.WIND),
        hz_pool=(432.0, 528.0, 40.0),
        melody_instruments=("atmosphere_fx",),
        melody_scales=("dorian",),
        noise_type_preference=(AudioMode.WHITE_NOISE, AudioMode.PINK_NOISE),
        brainwave_bands=("beta", "alpha"),
        brainwave_layer_probability=0.9,
    ),
}


def list_concepts() -> list[dict]:
    return [asdict(concept) for concept in CONCEPTS.values()]


def get_concept(concept_id: str) -> AlbumConcept:
    try:
        return CONCEPTS[concept_id]
    except KeyError as exc:
        raise ValueError(f"Unknown album concept: {concept_id}") from exc
