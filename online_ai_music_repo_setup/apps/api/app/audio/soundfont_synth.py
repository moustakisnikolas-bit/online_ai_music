import threading
from functools import lru_cache

import numpy as np

from app.audio.music_theory import NoteEvent
from app.core.config import get_settings

# A curated General MIDI program-number palette suited to ambient/wellness
# content -- not all 128 GM instruments, just piano/keys, mallets/bells,
# strings, choir, winds, and pads/atmosphere. Schema validation only ever
# accepts a name from this dict, never a raw program number.
GM_INSTRUMENTS: dict[str, int] = {
    "acoustic_grand_piano": 0,
    "electric_piano": 4,
    "harpsichord": 6,
    "celesta": 8,
    "glockenspiel": 9,
    "music_box": 10,
    "vibraphone": 11,
    "marimba": 12,
    "tubular_bells": 14,
    "kalimba": 108,
    "tinkle_bell": 112,
    "violin": 40,
    "cello": 42,
    "orchestral_harp": 46,
    "string_ensemble": 48,
    "synth_strings": 50,
    "choir_aahs": 52,
    "voice_oohs": 53,
    "flute": 73,
    "pan_flute": 75,
    "warm_pad": 89,
    "choir_pad": 91,
    "halo_pad": 94,
    "sweep_pad": 95,
    "atmosphere_fx": 99,
}

_CHANNEL = 0
# Standard General MIDI Control Change numbers.
_CC_RESONANCE = 71
_CC_RELEASE = 72
_CC_ATTACK = 73
_CC_CUTOFF = 74
_CC_VOLUME = 7
_NEUTRAL_VOLUME_CC = 100

_MAX_ATTACK_SECONDS = 5.0
_MAX_RELEASE_SECONDS = 10.0

# A single fluidsynth.Synth isn't safe for two requests to render on at the
# exact same instant (shared channel/CC/voice state) -- one render happens
# at a time process-wide. Simple and correct for expected usage; a small
# pool of pre-warmed Synth instances would be the next step if concurrent
# load ever makes this a real bottleneck.
_synth_lock = threading.Lock()
_synth_cache: dict[int, tuple[object, int]] = {}


@lru_cache
def soundfont_synth_available() -> bool:
    """Whether FluidSynth is installed AND the configured soundfont file
    loads -- cached since neither changes during a process's lifetime.
    """
    try:
        import fluidsynth
    except ImportError:
        return False

    try:
        settings = get_settings()
        synth = fluidsynth.Synth(samplerate=44100.0)
        sfid = synth.sfload(settings.soundfont_path)
        synth.delete()
        return sfid is not None and sfid != -1
    except Exception:
        return False


def _get_synth(sample_rate: int) -> tuple[object, int]:
    # FluidSynth's internal sample rate is fixed at construction time and
    # reloading the soundfont file per call would be slow, so the
    # (Synth, soundfont_id) pair is cached per distinct sample rate and
    # reused across requests.
    if sample_rate not in _synth_cache:
        import fluidsynth

        settings = get_settings()
        synth = fluidsynth.Synth(samplerate=float(sample_rate))
        sfid = synth.sfload(settings.soundfont_path)

        if sfid is None or sfid == -1:
            raise ValueError(
                f"Could not load soundfont at {settings.soundfont_path!r}."
            )

        _synth_cache[sample_rate] = (synth, sfid)

    return _synth_cache[sample_rate]


def _seconds_to_time_cc(seconds: float, max_seconds: float) -> int:
    normalized = max(0.0, min(1.0, seconds / max_seconds))
    return int(round(normalized * 127))


def _normalized_to_cc(value: float) -> int:
    return int(round(max(0.0, min(1.0, value)) * 127))


def build_cc_values(
    attack_seconds: float,
    release_seconds: float,
    filter_cutoff: float,
    filter_resonance: float,
) -> dict[int, int]:
    return {
        _CC_ATTACK: _seconds_to_time_cc(attack_seconds, _MAX_ATTACK_SECONDS),
        _CC_RELEASE: _seconds_to_time_cc(release_seconds, _MAX_RELEASE_SECONDS),
        _CC_CUTOFF: _normalized_to_cc(filter_cutoff),
        _CC_RESONANCE: _normalized_to_cc(filter_resonance),
    }


def render_pattern(
    events: list[NoteEvent],
    duration_seconds: int,
    sample_rate: int,
    program_number: int,
    cc_values: dict[int, int],
) -> np.ndarray:
    if not soundfont_synth_available():
        raise ValueError(
            "Synthesizer mode is not available: FluidSynth (or the "
            "configured soundfont file) is not installed/found on this "
            "server. See docs/15-synthesizer for setup instructions."
        )

    target_frames = duration_seconds * sample_rate

    with _synth_lock:
        synth, sfid = _get_synth(sample_rate)
        synth.program_select(_CHANNEL, sfid, 0, program_number)
        synth.cc(_CHANNEL, _CC_VOLUME, _NEUTRAL_VOLUME_CC)

        for controller, value in cc_values.items():
            synth.cc(_CHANNEL, controller, value)

        # Render a little past the nominal duration so a note's release
        # tail isn't cut off, then trim back to exactly target_frames --
        # matching every other generator's fixed-length contract.
        release_seconds = cc_values.get(_CC_RELEASE, 0) / 127.0 * _MAX_RELEASE_SECONDS
        total_frames = target_frames + int(release_seconds * sample_rate)

        # (frame, priority, midi_note, velocity) -- priority 0 (note-off)
        # sorts before priority 1 (note-on) at the same frame, so a note
        # ending exactly when another begins releases first instead of
        # audibly retriggering.
        timeline: list[tuple[int, int, int, int]] = []
        for event in events:
            on_frame = int(event.start_time_seconds * sample_rate)
            off_frame = int(
                (event.start_time_seconds + event.duration_seconds) * sample_rate
            )
            timeline.append((on_frame, 1, event.midi_note, event.velocity))
            timeline.append((off_frame, 0, event.midi_note, 0))

        timeline.sort(key=lambda item: (item[0], item[1]))

        rendered_chunks: list[np.ndarray] = []
        cursor = 0

        for frame, priority, midi_note, velocity in timeline:
            if frame > cursor:
                rendered_chunks.append(synth.get_samples(frame - cursor))
                cursor = frame

            if priority == 1:
                synth.noteon(_CHANNEL, midi_note, velocity)
            else:
                synth.noteoff(_CHANNEL, midi_note)

        if cursor < total_frames:
            rendered_chunks.append(synth.get_samples(total_frames - cursor))

    raw = (
        np.concatenate(rendered_chunks)
        if rendered_chunks
        else np.array([], dtype=np.int16)
    )
    stereo = raw.astype(np.float32).reshape(-1, 2) / 32767.0
    mono = stereo.mean(axis=1).astype(np.float32, copy=False)

    if len(mono) < target_frames:
        mono = np.pad(mono, (0, target_frames - len(mono)))

    return mono[:target_frames]
