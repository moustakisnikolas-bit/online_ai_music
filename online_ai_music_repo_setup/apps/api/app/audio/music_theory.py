import re
from dataclasses import dataclass

import numpy as np

# Semitone-interval patterns from the root, one octave's worth each.
SCALES: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "natural_minor": (0, 2, 3, 5, 7, 8, 10),
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
}

_NOTE_NAME_PATTERN = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_SEMITONES_FROM_C = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse_note_name(name: str) -> int:
    """Standard scientific pitch notation ("C4", "F#3", "Bb5") to a MIDI note
    number, using the common convention where middle C (C4) is MIDI note 60.
    """
    match = _NOTE_NAME_PATTERN.match(name.strip())

    if not match:
        raise ValueError(
            f"Invalid note name: {name!r} (expected e.g. 'C4', 'F#3', 'Bb5')"
        )

    letter, accidental, octave_str = match.groups()
    semitone = _SEMITONES_FROM_C[letter.upper()]

    if accidental == "#":
        semitone += 1
    elif accidental == "b":
        semitone -= 1

    octave = int(octave_str)
    return (octave + 1) * 12 + semitone


def midi_to_hz(midi_note: int, tuning_hz: float = 440.0) -> float:
    return tuning_hz * 2.0 ** ((midi_note - 69) / 12.0)


@dataclass(frozen=True)
class NoteEvent:
    midi_note: int
    start_time_seconds: float
    duration_seconds: float
    velocity: int


def generate_pattern(
    root_note: str,
    scale_name: str,
    pattern_type: str,
    octave_range: int,
    note_duration_seconds: float,
    duration_seconds: int,
    seed: int | None,
) -> list[NoteEvent]:
    """A deterministic (except for "random") note sequence: the root note's
    scale, spread across octave_range octaves, walked in the given
    pattern_type, filling duration_seconds at note_duration_seconds per
    note. Notes are given a short gap before the next note-on (90% of
    note_duration_seconds) rather than back-to-back, so consecutive notes
    don't ambiguously overlap at the same sample.
    """
    root_midi = parse_note_name(root_note)

    if scale_name not in SCALES:
        raise ValueError(f"Unknown scale: {scale_name!r}")

    if pattern_type not in {"up", "down", "up_down", "random"}:
        raise ValueError(f"Unknown pattern type: {pattern_type!r}")

    if note_duration_seconds <= 0:
        raise ValueError("note_duration_seconds must be positive")

    intervals = SCALES[scale_name]
    pool = [
        root_midi + 12 * octave + interval
        for octave in range(max(1, octave_range))
        for interval in intervals
    ]

    note_count = max(1, int(duration_seconds / note_duration_seconds))

    if pattern_type == "random":
        rng = np.random.default_rng(seed)
        midi_notes = [int(rng.choice(pool)) for _ in range(note_count)]
    else:
        if pattern_type == "up":
            cycle = pool
        elif pattern_type == "down":
            cycle = list(reversed(pool))
        else:  # up_down
            # Ascending then descending, without repeating the top note
            # twice in a row on the turn (pool[-2:0:-1] walks back down
            # from the second-to-last note to the second note).
            cycle = pool if len(pool) <= 1 else pool + pool[-2:0:-1]

        midi_notes = [cycle[i % len(cycle)] for i in range(note_count)]

    return [
        NoteEvent(
            midi_note=midi_notes[i],
            start_time_seconds=i * note_duration_seconds,
            duration_seconds=note_duration_seconds * 0.9,
            velocity=96,
        )
        for i in range(note_count)
    ]
