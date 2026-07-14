#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-012-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

if [[ -f apps/api/app/main.py ]]; then
  mkdir -p "${BACKUP_DIR}/apps/api/app"
  cp apps/api/app/main.py "${BACKUP_DIR}/apps/api/app/main.py"
fi

mkdir -p apps/api/app/web
mkdir -p apps/api/app/api/routes
mkdir -p apps/api/tests
mkdir -p docs/11-operations

cat > apps/api/app/web/index.html <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AION Ambient Audio Factory</title>
  <style>
    :root {
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
      color-scheme: dark;
      background: #0d1117;
      color: #e6edf3;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, #16233a 0, transparent 35%),
        #0d1117;
    }

    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 64px;
    }

    h1 {
      margin-bottom: 8px;
      font-size: clamp(2rem, 5vw, 3.4rem);
    }

    .subtitle {
      color: #9da7b3;
      margin-bottom: 32px;
    }

    .panel {
      background: rgba(22, 27, 34, 0.94);
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 18px 50px rgba(0,0,0,.22);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }

    label {
      display: grid;
      gap: 7px;
      font-size: .9rem;
      color: #c9d1d9;
    }

    input, select, button {
      font: inherit;
    }

    input, select {
      width: 100%;
      box-sizing: border-box;
      padding: 11px 12px;
      border-radius: 9px;
      border: 1px solid #3d444d;
      background: #0d1117;
      color: #e6edf3;
    }

    button {
      border: 0;
      border-radius: 10px;
      padding: 12px 18px;
      cursor: pointer;
      background: #238636;
      color: white;
      font-weight: 700;
    }

    button:disabled {
      opacity: .55;
      cursor: progress;
    }

    .actions {
      margin-top: 20px;
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }

    .status {
      color: #9da7b3;
      min-height: 24px;
    }

    .error {
      color: #ff7b72;
      white-space: pre-wrap;
    }

    .result {
      display: none;
    }

    .result.visible {
      display: block;
    }

    audio {
      width: 100%;
      margin: 16px 0;
    }

    code {
      word-break: break-word;
      color: #79c0ff;
    }

    a.download {
      display: inline-block;
      padding: 10px 14px;
      border-radius: 9px;
      background: #1f6feb;
      color: white;
      text-decoration: none;
      font-weight: 700;
    }

    .hidden {
      display: none;
    }

    .notice {
      padding: 12px;
      border-radius: 10px;
      background: #1b2638;
      color: #b6c2cf;
      margin-top: 18px;
      font-size: .9rem;
    }
  </style>
</head>
<body>
<main>
  <h1>AION Ambient Audio Factory</h1>
  <p class="subtitle">
    Generate original ambient audio assets directly from the browser.
  </p>

  <section class="panel">
    <form id="audio-form">
      <div class="grid">
        <label>
          Title
          <input id="title" value="AION Test Sound" required>
        </label>

        <label>
          Mode
          <select id="mode">
            <option value="sine">Sine tone</option>
            <option value="white_noise">White noise</option>
            <option value="pink_noise">Pink noise</option>
            <option value="brown_noise">Brown noise</option>
            <option value="binaural_beats">Binaural beats</option>
            <option value="isochronic_tones">Isochronic tones</option>
            <option value="preset">Preset</option>
          </select>
        </label>

        <label>
          Channels
          <select id="channels">
            <option value="mono">Mono</option>
            <option value="stereo">Stereo</option>
          </select>
        </label>

        <label>
          Duration (seconds)
          <input id="duration" type="number" value="5" min="1" max="3600">
        </label>

        <label>
          Sample rate
          <select id="sample-rate">
            <option value="8000">8000</option>
            <option value="44100" selected>44100</option>
            <option value="48000">48000</option>
          </select>
        </label>

        <label>
          Amplitude
          <input id="amplitude" type="number" value="0.1" min="0.01" max="1" step="0.01">
        </label>

        <label id="frequency-group">
          Frequency (Hz)
          <input id="frequency" type="number" value="432" min="1" max="20000">
        </label>

        <label id="left-frequency-group" class="hidden">
          Left frequency (Hz)
          <input id="left-frequency" type="number" value="200" min="1" max="20000">
        </label>

        <label id="right-frequency-group" class="hidden">
          Right frequency (Hz)
          <input id="right-frequency" type="number" value="210" min="1" max="20000">
        </label>

        <label id="pulse-frequency-group" class="hidden">
          Pulse frequency (Hz)
          <input id="pulse-frequency" type="number" value="10" min="0.1" max="100" step="0.1">
        </label>

        <label id="preset-group" class="hidden">
          Preset
          <select id="preset">
            <option value="calm-432">Calm 432</option>
            <option value="focus-alpha-bed">Focus Alpha Bed</option>
            <option value="deep-brown">Deep Brown</option>
            <option value="soft-pink">Soft Pink</option>
          </select>
        </label>

        <label>
          Fade in (seconds)
          <input id="fade-in" type="number" value="0.1" min="0" max="60" step="0.1">
        </label>

        <label>
          Fade out (seconds)
          <input id="fade-out" type="number" value="0.1" min="0" max="60" step="0.1">
        </label>

        <label>
          Random seed
          <input id="seed" type="number" value="42">
        </label>
      </div>

      <div class="actions">
        <button id="submit" type="submit">Generate audio</button>
        <span id="status" class="status"></span>
      </div>

      <div class="notice">
        Frequency-based output is provided as ambient and relaxation content.
        It is not medical treatment and does not promise therapeutic outcomes.
      </div>
    </form>
  </section>

  <section id="result" class="panel result">
    <h2>Generated Asset</h2>
    <div id="error" class="error"></div>
    <div id="success">
      <audio id="player" controls></audio>
      <p><strong>Filename:</strong> <code id="filename"></code></p>
      <p><strong>Mode:</strong> <span id="result-mode"></span></p>
      <p><strong>Duration:</strong> <span id="result-duration"></span> seconds</p>
      <p><strong>Sample rate:</strong> <span id="result-rate"></span> Hz</p>
      <a id="download" class="download" href="#">Download WAV</a>
    </div>
  </section>
</main>

<script>
  const form = document.getElementById("audio-form");
  const mode = document.getElementById("mode");
  const channels = document.getElementById("channels");
  const submit = document.getElementById("submit");
  const status = document.getElementById("status");
  const result = document.getElementById("result");
  const error = document.getElementById("error");
  const success = document.getElementById("success");

  function updateConditionalFields() {
    const selected = mode.value;
    const binaural = selected === "binaural_beats";
    const isochronic = selected === "isochronic_tones";
    const preset = selected === "preset";

    document.getElementById("left-frequency-group").classList.toggle("hidden", !binaural);
    document.getElementById("right-frequency-group").classList.toggle("hidden", !binaural);
    document.getElementById("pulse-frequency-group").classList.toggle("hidden", !isochronic);
    document.getElementById("preset-group").classList.toggle("hidden", !preset);
    document.getElementById("frequency-group").classList.toggle(
      "hidden",
      ["white_noise", "pink_noise", "brown_noise", "preset", "binaural_beats"].includes(selected)
    );

    if (binaural) {
      channels.value = "stereo";
      channels.disabled = true;
    } else {
      channels.disabled = false;
    }
  }

  mode.addEventListener("change", updateConditionalFields);
  updateConditionalFields();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    submit.disabled = true;
    status.textContent = "Generating…";
    result.classList.remove("visible");
    error.textContent = "";

    const selectedMode = mode.value;

    const payload = {
      title: document.getElementById("title").value,
      mode: selectedMode,
      channels: channels.value,
      duration_seconds: Number(document.getElementById("duration").value),
      sample_rate: Number(document.getElementById("sample-rate").value),
      amplitude: Number(document.getElementById("amplitude").value),
      fade_in_seconds: Number(document.getElementById("fade-in").value),
      fade_out_seconds: Number(document.getElementById("fade-out").value),
      seed: Number(document.getElementById("seed").value)
    };

    if (!["white_noise", "pink_noise", "brown_noise", "preset", "binaural_beats"].includes(selectedMode)) {
      payload.frequency_hz = Number(document.getElementById("frequency").value);
    }

    if (selectedMode === "binaural_beats") {
      payload.channels = "stereo";
      payload.left_frequency_hz = Number(document.getElementById("left-frequency").value);
      payload.right_frequency_hz = Number(document.getElementById("right-frequency").value);
    }

    if (selectedMode === "isochronic_tones") {
      payload.pulse_frequency_hz = Number(document.getElementById("pulse-frequency").value);
      payload.modulation_depth = 1.0;
    }

    if (selectedMode === "preset") {
      payload.preset_name = document.getElementById("preset").value;
    }

    try {
      const response = await fetch("/api/v1/audio/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });

      const body = await response.json();

      if (!response.ok) {
        throw new Error(JSON.stringify(body, null, 2));
      }

      const filename = body.file_path.split("/").pop();
      const metadataUrl = `/api/v1/audio/assets/${encodeURIComponent(filename)}`;
      const metadataResponse = await fetch(metadataUrl);
      const metadata = await metadataResponse.json();

      if (!metadataResponse.ok) {
        throw new Error(JSON.stringify(metadata, null, 2));
      }

      document.getElementById("filename").textContent = metadata.filename;
      document.getElementById("result-mode").textContent = body.mode;
      document.getElementById("result-duration").textContent = metadata.duration_seconds;
      document.getElementById("result-rate").textContent = metadata.sample_rate;
      document.getElementById("player").src = metadata.download_url;
      document.getElementById("download").href = metadata.download_url;

      success.style.display = "block";
      result.classList.add("visible");
      status.textContent = "Completed";
    } catch (exception) {
      success.style.display = "none";
      error.textContent = exception.message;
      result.classList.add("visible");
      status.textContent = "Failed";
    } finally {
      submit.disabled = false;
    }
  });
</script>
</body>
</html>
EOF

cat > apps/api/app/api/routes/web.py <<'EOF'
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


@router.get("/", include_in_schema=False)
def web_home() -> FileResponse:
    return FileResponse(
        WEB_ROOT / "index.html",
        media_type="text/html",
    )


@router.get("/app", include_in_schema=False)
def web_app() -> FileResponse:
    return FileResponse(
        WEB_ROOT / "index.html",
        media_type="text/html",
    )
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.web import router as web_router\n"

if import_line not in content:
    marker = "from app.api.routes.projects import router as projects_router\n"

    if marker not in content:
        raise SystemExit("Expected projects router import was not found.")

    content = content.replace(marker, marker + import_line)

route_line = "app.include_router(web_router)\n"

if route_line not in content:
    content += "\n" + route_line

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_web_ui.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_web_home_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AION Ambient Audio Factory" in response.text
    assert "Generate audio" in response.text


def test_web_app_alias_is_available() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
EOF

cat > docs/11-operations/web-ui-guide.md <<'EOF'
# AION Web UI Guide

## Start the API

```bash
make api
```

## Open the Interface

```text
http://127.0.0.1:8000/
```

or:

```text
http://127.0.0.1:8000/app
```

## Current Capabilities

The first interface supports:

- sine tones;
- white noise;
- pink noise;
- brown noise;
- binaural beats;
- isochronic tones;
- presets;
- mono and stereo output;
- duration;
- sample rate;
- amplitude;
- fades;
- deterministic seed;
- audio preview;
- WAV download.

## Current Limitation

Generation is synchronous in this first web interface.

Queue-backed job creation remains available through the API and worker architecture.

A later version should connect the UI to asynchronous jobs with progress reporting.
EOF

cat > docs/00-overview/mvp-status-after-update-012.md <<'EOF'
# MVP Status After Update 012

## Completed

- Repository architecture
- Product documentation
- FastAPI backend
- Audio generation API
- Sine tones
- Layered tones
- White noise
- Pink noise
- Brown noise
- Binaural beats
- Isochronic tones
- Mono and stereo WAV
- Fades
- Loop crossfade
- Presets
- Asset metadata
- Secure WAV download
- First usable browser interface
- Automated tests

## Remaining Before Production

- Authentication
- asynchronous UI jobs
- production database verification
- Docker environment stabilization
- object storage
- long-form chunked rendering
- MP3 and FLAC output
- artwork generation
- video rendering
- publishing integration
- analytics
- deployment hardening

## Practical Meaning

The repository now contains a real local audio-generation MVP rather than only documentation or code skeletons.
EOF

echo "AION Update 012 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
echo "  make api"
echo
echo "Then open:"
echo "  http://127.0.0.1:8000/"
