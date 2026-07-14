FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY apps/worker /app/apps/worker

ENV PYTHONPATH=/app/apps/worker

CMD ["python", "-m", "app.main"]
