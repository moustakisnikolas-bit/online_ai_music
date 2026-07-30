FROM python:3.12-slim

WORKDIR /app

# fluidsynth: native library the Synthesizer mode / mixed_ambient melody
# layer needs for SoundFont-based instrument playback.
# ffmpeg: the album pipeline's video-render stage shells out to the real
# `ffmpeg` binary (see apps/api/app/services/video_renderer.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fluidsynth ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
COPY data /app/data

ENV PYTHONPATH=/app/apps/api:/app/apps/worker

CMD ["python", "/app/apps/worker/app/main.py"]
