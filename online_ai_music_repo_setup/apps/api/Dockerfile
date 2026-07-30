FROM python:3.12-slim

WORKDIR /app

# fluidsynth: native library for Synthesizer mode (SoundFont-based
# instrument playback) -- the pyfluidsynth pip package is only a thin
# wrapper around this.
# ffmpeg: video_renderer.py shells out to the real `ffmpeg` binary (no
# Python wrapper bundles one) to render the static-image videos used by
# both the manual "Publish to YouTube" flow and the album pipeline.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fluidsynth ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/api /app/apps/api
COPY data /app/data

ENV PYTHONPATH=/app/apps/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
