import wave
from pathlib import Path

from app.audio.types import AudioMode, ChannelMode, TextureMode
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest
from app.services.audio_generator import generate_audio


def test_generate_mixed_ambient_scene(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Rain and Brown Noise",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        noise_mode=AudioMode.BROWN_NOISE,
        noise_gain=0.7,
        texture_mode=TextureMode.RAIN,
        texture_gain=0.2,
        layers=[
            ToneLayerRequest(
                frequency_hz=432,
                amplitude=0.05,
            )
        ],
        tone_gain=0.2,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "mixed_ambient"

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000
