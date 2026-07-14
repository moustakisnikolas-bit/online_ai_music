import math
import struct
import uuid
import wave
from pathlib import Path

from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse


def generate_sine_wave(
    request: AudioGenerationRequest,
    output_dir: Path,
) -> AudioGenerationResponse:
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_id = str(uuid.uuid4())
    output_path = output_dir / f"{asset_id}.wav"
    frame_count = request.duration_seconds * request.sample_rate

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(request.sample_rate)

        for frame_index in range(frame_count):
            time_position = frame_index / request.sample_rate
            sample_value = request.amplitude * math.sin(
                2.0 * math.pi * request.frequency_hz * time_position
            )
            pcm_value = int(max(-1.0, min(1.0, sample_value)) * 32767)
            wav_file.writeframesraw(struct.pack("<h", pcm_value))

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        frequency_hz=request.frequency_hz,
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        status="generated",
        file_path=str(output_path),
    )
