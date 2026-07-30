import pytest

from app.audio.music_theory import SCALES, generate_pattern, midi_to_hz, parse_note_name


def test_parse_note_name_middle_c() -> None:
    assert parse_note_name("C4") == 60


def test_parse_note_name_sharp() -> None:
    assert parse_note_name("F#3") == 54


def test_parse_note_name_flat() -> None:
    assert parse_note_name("Bb5") == 82


def test_parse_note_name_lowercase_letter() -> None:
    assert parse_note_name("c4") == 60


def test_parse_note_name_rejects_invalid_letter() -> None:
    with pytest.raises(ValueError, match="Invalid note name"):
        parse_note_name("H4")


def test_parse_note_name_rejects_malformed_string() -> None:
    with pytest.raises(ValueError, match="Invalid note name"):
        parse_note_name("not-a-note")


def test_midi_to_hz_a4_is_440() -> None:
    assert midi_to_hz(parse_note_name("A4")) == pytest.approx(440.0)


def test_scales_intervals_start_at_zero_and_stay_within_an_octave() -> None:
    for name, intervals in SCALES.items():
        assert intervals[0] == 0, name
        assert all(0 <= interval < 12 for interval in intervals), name
        assert list(intervals) == sorted(intervals), name


def test_generate_pattern_up_is_deterministic_and_ascends() -> None:
    events = generate_pattern("C4", "major", "up", 1, 0.5, 3, seed=None)
    notes = [e.midi_note for e in events]

    assert notes == [60, 62, 64, 65, 67, 69]


def test_generate_pattern_down_descends() -> None:
    events = generate_pattern("C4", "major_pentatonic", "down", 1, 0.5, 2, seed=None)
    notes = [e.midi_note for e in events]

    assert notes == [69, 67, 64, 62]


def test_generate_pattern_up_down_does_not_repeat_the_peak() -> None:
    events = generate_pattern("C4", "major_pentatonic", "up_down", 1, 0.5, 4, seed=None)
    notes = [e.midi_note for e in events]

    # pool = [60, 62, 64, 67, 69]; up_down walks up then back down without
    # repeating the peak (69) twice in a row.
    assert notes == [60, 62, 64, 67, 69, 67, 64, 62]
    assert notes.count(69) == 1


def test_generate_pattern_random_is_seed_reproducible() -> None:
    first = generate_pattern("C4", "major", "random", 1, 0.5, 3, seed=42)
    second = generate_pattern("C4", "major", "random", 1, 0.5, 3, seed=42)

    assert [e.midi_note for e in first] == [e.midi_note for e in second]


def test_generate_pattern_random_differs_across_seeds() -> None:
    first = generate_pattern("C4", "major", "random", 2, 0.25, 10, seed=1)
    second = generate_pattern("C4", "major", "random", 2, 0.25, 10, seed=2)

    assert [e.midi_note for e in first] != [e.midi_note for e in second]


def test_generate_pattern_note_count_matches_duration() -> None:
    events = generate_pattern("C4", "major", "up", 1, 0.5, 5, seed=None)

    assert len(events) == 10  # 5 seconds / 0.5s per note


def test_generate_pattern_note_timing_is_back_to_back_with_a_small_gap() -> None:
    events = generate_pattern("C4", "major", "up", 1, 0.5, 2, seed=None)

    assert events[0].start_time_seconds == 0.0
    assert events[0].duration_seconds == pytest.approx(0.45)
    assert events[1].start_time_seconds == pytest.approx(0.5)


def test_generate_pattern_octave_range_expands_the_pool() -> None:
    one_octave = generate_pattern("C4", "major", "up", 1, 1.0, 7, seed=None)
    two_octaves = generate_pattern("C4", "major", "up", 2, 1.0, 14, seed=None)

    assert max(e.midi_note for e in one_octave) < max(e.midi_note for e in two_octaves)


def test_generate_pattern_rejects_unknown_scale() -> None:
    with pytest.raises(ValueError, match="Unknown scale"):
        generate_pattern("C4", "not_a_scale", "up", 1, 0.5, 1, seed=None)


def test_generate_pattern_rejects_unknown_pattern_type() -> None:
    with pytest.raises(ValueError, match="Unknown pattern type"):
        generate_pattern("C4", "major", "sideways", 1, 0.5, 1, seed=None)


def test_generate_pattern_rejects_bad_root_note() -> None:
    with pytest.raises(ValueError, match="Invalid note name"):
        generate_pattern("not-a-note", "major", "up", 1, 0.5, 1, seed=None)
