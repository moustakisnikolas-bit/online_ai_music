from app.schemas.audio import AudioGenerationRequest


def test_one_second_clip_accepts_default_fades() -> None:
    request = AudioGenerationRequest(
        title="One Second Tone",
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    assert request.fade_in_seconds == 0.1
    assert request.fade_out_seconds == 0.1
