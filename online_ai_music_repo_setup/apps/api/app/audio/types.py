from enum import StrEnum


class AudioMode(StrEnum):
    SINE = "sine"
    LAYERED_TONES = "layered_tones"
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BROWN_NOISE = "brown_noise"
    BINAURAL_BEATS = "binaural_beats"
    ISOCHRONIC_TONES = "isochronic_tones"
    MIXED_AMBIENT = "mixed_ambient"
    PRESET = "preset"


class ChannelMode(StrEnum):
    MONO = "mono"
    STEREO = "stereo"


class OutputFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"


class TextureMode(StrEnum):
    NONE = "none"
    RAIN = "rain"
    WIND = "wind"
    WAVES = "waves"
    BIRDS = "birds"
