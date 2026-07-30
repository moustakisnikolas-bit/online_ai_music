from pathlib import Path


def _format_timestamp(seconds: float) -> str:
    # HH:MM:SS,mmm per the SRT spec.
    total_ms = max(0, round(seconds * 1000))
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_to_srt(
    audio_path: Path,
    output_dir: Path,
    *,
    model_size: str = "base",
) -> Path:
    # Dormant feature: nothing in this codebase produces speech yet (every
    # AudioMode is instrumental), so nothing calls this today. It exists
    # ready for a future narrated-content feature, mirroring the
    # "hibernating, no key configured by default" pattern used for
    # openrouter_api_key in core/config.py -- here at the import-cost
    # level rather than the configured-key level, since local Whisper
    # inference needs no API key to gate. Imported lazily so the rest of
    # the app never pays faster-whisper's import cost for a call path
    # nothing exercises yet.
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio_path))

    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / f"{audio_path.stem}.srt"

    with srt_path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, start=1):
            handle.write(f"{index}\n")
            handle.write(
                f"{_format_timestamp(segment.start)} --> {_format_timestamp(segment.end)}\n"
            )
            handle.write(f"{segment.text.strip()}\n\n")

    return srt_path
