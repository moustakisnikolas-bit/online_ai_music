#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-019-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "apps/api/app/web/index.html"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

mkdir -p apps/api/tests
mkdir -p docs/11-operations
mkdir -p docs/00-overview

cat > apps/api/app/web/index.html <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AION Ambient Media Factory</title>
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
        radial-gradient(circle at top left, #172743 0, transparent 36%),
        radial-gradient(circle at bottom right, #10243d 0, transparent 30%),
        #0d1117;
    }

    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 72px;
    }

    h1 {
      margin: 0 0 8px;
      font-size: clamp(2rem, 5vw, 3.5rem);
    }

    h2, h3 {
      margin-top: 0;
    }

    .subtitle {
      color: #9da7b3;
      margin-bottom: 28px;
    }

    .panel {
      background: rgba(22, 27, 34, 0.96);
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 22px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, .22);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }

    .workflow-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }

    label {
      display: grid;
      gap: 7px;
      font-size: .9rem;
      color: #c9d1d9;
    }

    input, select, textarea, button {
      font: inherit;
    }

    input, select, textarea {
      width: 100%;
      box-sizing: border-box;
      padding: 11px 12px;
      border-radius: 9px;
      border: 1px solid #3d444d;
      background: #0d1117;
      color: #e6edf3;
    }

    textarea {
      min-height: 110px;
      resize: vertical;
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

    button.secondary {
      background: #1f6feb;
    }

    button.warning {
      background: #9e6a03;
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

    .success {
      color: #7ee787;
    }

    .hidden {
      display: none !important;
    }

    .step {
      border: 1px solid #30363d;
      border-radius: 12px;
      padding: 16px;
      background: #11161d;
    }

    .step.complete {
      border-color: #238636;
    }

    .step.failed {
      border-color: #da3633;
    }

    audio, video, img {
      width: 100%;
      margin-top: 12px;
      border-radius: 10px;
    }

    img {
      max-height: 420px;
      object-fit: contain;
      background: #0d1117;
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
      margin: 6px 6px 0 0;
    }

    .notice {
      padding: 12px;
      border-radius: 10px;
      background: #1b2638;
      color: #b6c2cf;
      margin-top: 18px;
      font-size: .9rem;
    }

    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: .85rem;
      white-space: pre-wrap;
      word-break: break-word;
    }
  </style>
</head>
<body>
<main>
  <h1>AION Ambient Media Factory</h1>
  <p class="subtitle">
    Generate audio, metadata, artwork, video and a complete export package.
  </p>

  <section class="panel">
    <h2>1. Content Configuration</h2>

    <div class="grid">
      <label>
        Title
        <input id="title" value="Night Rain 432">
      </label>

      <label>
        Context
        <select id="context">
          <option value="sleep">Sleep</option>
          <option value="relaxation">Relaxation</option>
          <option value="meditation">Meditation</option>
          <option value="focus">Focus</option>
          <option value="ambient">Ambient</option>
        </select>
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
          <option value="mixed_ambient" selected>Mixed ambient</option>
          <option value="preset">Preset</option>
        </select>
      </label>

      <label>
        Channels
        <select id="channels">
          <option value="mono">Mono</option>
          <option value="stereo" selected>Stereo</option>
        </select>
      </label>

      <label>
        Duration (seconds)
        <input id="duration" type="number" value="10" min="1" max="28800">
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
        Output format
        <select id="output-format">
          <option value="wav" selected>WAV</option>
          <option value="flac">FLAC</option>
          <option value="mp3">MP3</option>
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
          <option value="">Loading presets…</option>
        </select>
      </label>

      <label id="noise-group">
        Noise bed
        <select id="noise-mode">
          <option value="brown_noise" selected>Brown noise</option>
          <option value="pink_noise">Pink noise</option>
          <option value="white_noise">White noise</option>
        </select>
      </label>

      <label id="texture-group">
        Texture
        <select id="texture-mode">
          <option value="rain" selected>Rain</option>
          <option value="wind">Wind</option>
          <option value="none">None</option>
        </select>
      </label>

      <label>
        Fade in
        <input id="fade-in" type="number" value="0.1" min="0" max="60" step="0.1">
      </label>

      <label>
        Fade out
        <input id="fade-out" type="number" value="0.1" min="0" max="60" step="0.1">
      </label>

      <label>
        Seed
        <input id="seed" type="number" value="42">
      </label>

      <label>
        Artwork format
        <select id="artwork-preset">
          <option value="spotify-cover">Spotify cover</option>
          <option value="youtube-thumbnail">YouTube thumbnail</option>
          <option value="square-preview">Square preview</option>
        </select>
      </label>
    </div>

    <div class="actions">
      <button id="run-workflow">Run complete workflow</button>
      <button id="run-audio-only" class="secondary">Generate audio only</button>
      <span id="global-status" class="status"></span>
    </div>

    <div class="notice">
      Publishing remains manual. The export bundle is created for review and later upload.
    </div>
  </section>

  <section class="panel">
    <h2>2. Workflow Status</h2>

    <div class="workflow-grid">
      <div id="step-audio" class="step">
        <h3>Audio</h3>
        <div class="status">Not started</div>
      </div>

      <div id="step-metadata" class="step">
        <h3>Metadata</h3>
        <div class="status">Not started</div>
      </div>

      <div id="step-artwork" class="step">
        <h3>Artwork</h3>
        <div class="status">Not started</div>
      </div>

      <div id="step-video" class="step">
        <h3>Video</h3>
        <div class="status">Not started</div>
      </div>

      <div id="step-export" class="step">
        <h3>Export bundle</h3>
        <div class="status">Not started</div>
      </div>
    </div>

    <div id="workflow-error" class="error"></div>
  </section>

  <section id="results" class="panel hidden">
    <h2>3. Generated Assets</h2>

    <div class="workflow-grid">
      <div>
        <h3>Audio</h3>
        <audio id="audio-player" controls></audio>
        <div id="audio-details" class="mono"></div>
        <a id="audio-download" class="download hidden" href="#">Download audio</a>
      </div>

      <div>
        <h3>Artwork</h3>
        <img id="artwork-preview" alt="Generated artwork">
        <div id="artwork-details" class="mono"></div>
      </div>

      <div>
        <h3>Metadata</h3>
        <textarea id="metadata-preview" readonly></textarea>
      </div>

      <div>
        <h3>Video</h3>
        <video id="video-preview" class="hidden" controls></video>
        <div id="video-details" class="mono"></div>
        <a id="video-download" class="download hidden" href="#">Download video</a>
      </div>
    </div>

    <div class="actions">
      <a id="export-download" class="download hidden" href="#">Download export ZIP</a>
    </div>
  </section>
</main>

<script>
  const state = {
    audio: null,
    metadata: null,
    artwork: null,
    video: null,
    exportBundle: null
  };

  const modeElement = document.getElementById("mode");
  const channelsElement = document.getElementById("channels");
  const statusElement = document.getElementById("global-status");
  const errorElement = document.getElementById("workflow-error");

  function step(name, text, stateName = "") {
    const element = document.getElementById(`step-${name}`);
    element.classList.remove("complete", "failed");

    if (stateName) {
      element.classList.add(stateName);
    }

    element.querySelector(".status").textContent = text;
  }

  function updateConditionalFields() {
    const mode = modeElement.value;
    const binaural = mode === "binaural_beats";
    const isochronic = mode === "isochronic_tones";
    const preset = mode === "preset";
    const mixed = mode === "mixed_ambient";

    document.getElementById("left-frequency-group").classList.toggle("hidden", !binaural);
    document.getElementById("right-frequency-group").classList.toggle("hidden", !binaural);
    document.getElementById("pulse-frequency-group").classList.toggle("hidden", !isochronic);
    document.getElementById("preset-group").classList.toggle("hidden", !preset);
    document.getElementById("noise-group").classList.toggle("hidden", !mixed);
    document.getElementById("texture-group").classList.toggle("hidden", !mixed);

    document.getElementById("frequency-group").classList.toggle(
      "hidden",
      ["white_noise", "pink_noise", "brown_noise", "preset", "binaural_beats"].includes(mode)
    );

    if (binaural) {
      channelsElement.value = "stereo";
      channelsElement.disabled = true;
    } else {
      channelsElement.disabled = false;
    }
  }

  async function jsonRequest(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error(JSON.stringify(body, null, 2));
    }

    return body;
  }

  async function loadPresets() {
    const select = document.getElementById("preset");

    try {
      const presets = await jsonRequest("/api/v1/audio/presets");
      select.innerHTML = "";

      for (const preset of presets) {
        const option = document.createElement("option");
        option.value = preset.name;
        option.textContent = `${preset.label} — ${preset.description}`;
        select.appendChild(option);
      }
    } catch {
      select.innerHTML = '<option value="calm-432">Calm 432</option>';
    }
  }

  function buildAudioPayload() {
    const mode = modeElement.value;

    const payload = {
      title: document.getElementById("title").value,
      mode,
      channels: channelsElement.value,
      duration_seconds: Number(document.getElementById("duration").value),
      sample_rate: Number(document.getElementById("sample-rate").value),
      output_format: document.getElementById("output-format").value,
      amplitude: Number(document.getElementById("amplitude").value),
      fade_in_seconds: Number(document.getElementById("fade-in").value),
      fade_out_seconds: Number(document.getElementById("fade-out").value),
      seed: Number(document.getElementById("seed").value)
    };

    if (!["white_noise", "pink_noise", "brown_noise", "preset", "binaural_beats"].includes(mode)) {
      payload.frequency_hz = Number(document.getElementById("frequency").value);
    }

    if (mode === "binaural_beats") {
      payload.channels = "stereo";
      payload.left_frequency_hz = Number(document.getElementById("left-frequency").value);
      payload.right_frequency_hz = Number(document.getElementById("right-frequency").value);
    }

    if (mode === "isochronic_tones") {
      payload.pulse_frequency_hz = Number(document.getElementById("pulse-frequency").value);
      payload.modulation_depth = 1.0;
    }

    if (mode === "preset") {
      payload.preset_name = document.getElementById("preset").value;
    }

    if (mode === "mixed_ambient") {
      payload.noise_mode = document.getElementById("noise-mode").value;
      payload.texture_mode = document.getElementById("texture-mode").value;
      payload.noise_gain = 0.7;
      payload.texture_gain = 0.2;
      payload.tone_gain = 0.2;
      payload.layers = [
        {
          frequency_hz: Number(document.getElementById("frequency").value),
          amplitude: 0.05
        }
      ];
    }

    return payload;
  }

  async function generateAudio() {
    step("audio", "Generating…");
    const payload = buildAudioPayload();

    state.audio = await jsonRequest(
      "/api/v1/audio/generate",
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    );

    const filename = state.audio.file_path.split("/").pop();
    const downloadUrl = `/api/v1/audio/files/${encodeURIComponent(filename)}`;

    document.getElementById("audio-player").src = downloadUrl;
    document.getElementById("audio-download").href = downloadUrl;
    document.getElementById("audio-download").classList.remove("hidden");
    document.getElementById("audio-details").textContent =
      JSON.stringify(state.audio, null, 2);

    step("audio", "Completed", "complete");
    return filename;
  }

  async function generateMetadata() {
    step("metadata", "Generating…");

    const payload = buildAudioPayload();

    state.metadata = await jsonRequest(
      "/api/v1/catalog/metadata/generate",
      {
        method: "POST",
        body: JSON.stringify({
          source_title: payload.title,
          mode: payload.mode,
          duration_seconds: payload.duration_seconds,
          context: document.getElementById("context").value,
          language: "en",
          frequency_hz: payload.frequency_hz || null,
          texture_mode: payload.texture_mode || null
        })
      }
    );

    document.getElementById("metadata-preview").value =
      JSON.stringify(state.metadata, null, 2);

    step("metadata", "Completed", "complete");
  }

  async function generateArtwork() {
    step("artwork", "Generating…");

    state.artwork = await jsonRequest(
      "/api/v1/visuals/artwork/generate",
      {
        method: "POST",
        body: JSON.stringify({
          title: state.metadata?.title || document.getElementById("title").value,
          subtitle: state.metadata?.subtitle || "Original Ambient Audio",
          preset_name: document.getElementById("artwork-preset").value,
          seed: Number(document.getElementById("seed").value)
        })
      }
    );

    const artworkUrl =
      `/api/v1/visuals/files/${encodeURIComponent(state.artwork.filename)}`;

    document.getElementById("artwork-preview").src = artworkUrl;
    document.getElementById("artwork-details").textContent =
      JSON.stringify(state.artwork, null, 2);

    step("artwork", "Completed", "complete");
  }

  async function generateVideo(audioFilename) {
    step("video", "Rendering…");

    const outputFilename =
      document.getElementById("title").value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") + ".mp4";

    state.video = await jsonRequest(
      "/api/v1/exports/video/render",
      {
        method: "POST",
        body: JSON.stringify({
          audio_filename: audioFilename,
          artwork_filename: state.artwork.filename,
          output_filename: outputFilename,
          width: 1920,
          height: 1080,
          frame_rate: 30
        })
      }
    );

    const videoUrl =
      `/api/v1/exports/files/${encodeURIComponent(state.video.filename)}`;

    document.getElementById("video-preview").src = videoUrl;
    document.getElementById("video-preview").classList.remove("hidden");
    document.getElementById("video-download").href = videoUrl;
    document.getElementById("video-download").classList.remove("hidden");
    document.getElementById("video-details").textContent =
      JSON.stringify(state.video, null, 2);

    step("video", "Completed", "complete");
  }

  async function generateBundle(audioFilename) {
    step("export", "Packaging…");

    state.exportBundle = await jsonRequest(
      "/api/v1/exports/bundle",
      {
        method: "POST",
        body: JSON.stringify({
          title: document.getElementById("title").value,
          audio_filename: audioFilename,
          artwork_filename: state.artwork?.filename || null,
          video_filename: state.video?.filename || null,
          metadata: state.metadata || {}
        })
      }
    );

    const exportUrl =
      `/api/v1/exports/files/${encodeURIComponent(state.exportBundle.zip_filename)}`;

    document.getElementById("export-download").href = exportUrl;
    document.getElementById("export-download").classList.remove("hidden");

    step("export", "Completed", "complete");
  }

  async function runWorkflow(includeVisuals) {
    errorElement.textContent = "";
    statusElement.textContent = "Running workflow…";
    document.getElementById("results").classList.remove("hidden");

    for (const name of ["audio", "metadata", "artwork", "video", "export"]) {
      step(name, "Not started");
    }

    try {
      const audioFilename = await generateAudio();

      if (!includeVisuals) {
        statusElement.textContent = "Audio completed";
        return;
      }

      await generateMetadata();
      await generateArtwork();

      try {
        await generateVideo(audioFilename);
      } catch (error) {
        step("video", "Skipped or failed: FFmpeg may be unavailable", "failed");
        document.getElementById("video-details").textContent = error.message;
      }

      await generateBundle(audioFilename);
      statusElement.textContent = "Workflow completed";
    } catch (error) {
      errorElement.textContent = error.message;
      statusElement.textContent = "Workflow failed";
    }
  }

  document.getElementById("run-workflow").addEventListener(
    "click",
    () => runWorkflow(true)
  );

  document.getElementById("run-audio-only").addEventListener(
    "click",
    () => runWorkflow(false)
  );

  modeElement.addEventListener("change", updateConditionalFields);
  updateConditionalFields();
  loadPresets();
</script>
</body>
</html>
EOF

cat > apps/api/app/api/routes/visual_files.py <<'EOF'
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter(prefix="/visuals/files", tags=["visual-files"])

ARTWORK_DIR = Path("data/generated/artwork")


@router.get("/{filename}")
def download_visual_file(filename: str) -> FileResponse:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported visual file type.",
        )

    base = ARTWORK_DIR.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visual file not found.",
        )

    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }[path.suffix.lower()]

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=path.name,
    )
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.visual_files import router as visual_files_router\n"

if import_line not in content:
    marker = "from app.api.routes.visuals import router as visuals_router\n"

    if marker not in content:
        raise SystemExit("Expected visuals import was not found.")

    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(visual_files_router, prefix="/api/v1")\n'

if route_line not in content:
    marker = 'app.include_router(visuals_router, prefix="/api/v1")\n'

    if marker not in content:
        raise SystemExit("Expected visuals route registration was not found.")

    content = content.replace(marker, marker + route_line)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_visual_files_api.py <<'EOF'
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def test_visual_file_endpoint() -> None:
    output_dir = Path("data/generated/artwork")
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / "ui-test-image.png"
    Image.new("RGB", (10, 10)).save(path)

    try:
        response = client.get(
            "/api/v1/visuals/files/ui-test-image.png"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    finally:
        path.unlink(missing_ok=True)
EOF

cat > apps/api/tests/test_complete_ui_workflow.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_complete_ui_contains_all_workflow_steps() -> None:
    response = client.get("/")

    assert response.status_code == 200

    expected_text = [
        "Run complete workflow",
        "Audio",
        "Metadata",
        "Artwork",
        "Video",
        "Export bundle",
        "Download export ZIP",
    ]

    for text in expected_text:
        assert text in response.text
EOF

cat > docs/11-operations/complete-local-workflow.md <<'EOF'
# Complete Local Workflow

## Start the Application

```bash
make api
```

Open:

```text
http://127.0.0.1:8000/
```

## Workflow

The complete browser workflow performs:

1. audio generation;
2. metadata generation;
3. artwork generation;
4. optional MP4 rendering;
5. export ZIP creation.

## Generated Outputs

### Audio

Stored under:

```text
data/generated/audio
```

### Artwork

Stored under:

```text
data/generated/artwork
```

### Video

Stored under:

```text
data/generated/video
```

### Export Bundle

Stored under:

```text
data/generated/exports
```

## FFmpeg Behavior

When FFmpeg is unavailable:

- WAV generation still works;
- metadata generation still works;
- artwork generation still works;
- MP4 generation is skipped or returns an explicit error;
- the export bundle can still be created without video.

## Publishing

The ZIP is a preparation package.

It is not uploaded automatically and should be reviewed before distribution.
EOF

cat > docs/00-overview/mvp-user-flow.md <<'EOF'
# AION MVP User Flow

## Input

The user chooses:

- content title;
- purpose;
- audio mode;
- frequency;
- duration;
- channels;
- output format;
- artwork preset.

## Processing

AION creates:

- original audio;
- metadata;
- artwork;
- optional video;
- catalog manifest;
- export ZIP.

## Output

The user can preview and download the generated assets.

## Current Boundary

The MVP ends at export-package creation.

Uploading to YouTube or music distributors remains a manual, reviewed action.
EOF

echo "AION Update 019 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Remaining planned updates after this one: 1"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
echo "  make api"
