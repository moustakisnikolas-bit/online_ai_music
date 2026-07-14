#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

mkdir -p docs/00-overview
mkdir -p docs/12-roadmap
mkdir -p docs/13-ai-implementation

cat > docs/00-overview/current-mvp-summary.md <<'EOF'
# AION Current MVP Summary

## What AION Is

AION is an AI-assisted media production platform whose first production line is an Ambient Audio Factory.

The long-term vision includes automated creation of:

- ambient audio;
- sleep audio;
- meditation audio;
- focus audio;
- frequency-based relaxation content;
- artwork;
- long-form videos;
- metadata;
- publishing packages;
- analytics.

## What Has Already Been Designed

The repository currently contains:

- product and business documentation;
- software requirements;
- architecture notes;
- AI-agent guidance;
- a repository generator CLI;
- a FastAPI backend skeleton;
- PostgreSQL models and Alembic migrations;
- Redis queue design;
- a worker process;
- synchronous and queue-backed audio generation flows;
- WAV generation;
- sine tones;
- layered tones;
- white noise;
- pink noise;
- brown noise;
- preset-based generation;
- fade-in and fade-out;
- automated tests.

## Current MVP Objective

The MVP should allow a user to:

1. create a project;
2. request an ambient audio asset;
3. choose a generation mode;
4. select duration, sample rate, amplitude and fades;
5. submit the job;
6. process the job through a worker;
7. create a valid WAV file;
8. retrieve job status and output metadata.

## Current Supported Audio Modes

- sine;
- layered_tones;
- white_noise;
- pink_noise;
- brown_noise;
- preset.

## Current Presets

- calm-432;
- focus-alpha-bed;
- deep-brown;
- soft-pink.

## Current Limitations

The current implementation is still an engineering MVP.

It does not yet provide:

- a production user interface;
- authentication;
- stereo output;
- binaural beats;
- isochronic tones;
- nature-sound synthesis;
- long-duration streaming rendering;
- FLAC or MP3 export;
- artwork generation;
- video rendering;
- publishing integrations;
- analytics integrations;
- production security hardening;
- production deployment.

## MVP Completion Definition

The current phase is considered complete when:

- all automated tests pass;
- local API execution works;
- one audio file can be generated from an API request;
- one queue-backed job can complete when PostgreSQL and Redis are available;
- the output WAV is valid;
- the implementation prompt accurately describes the next development phase.
EOF

cat > docs/12-roadmap/mvp-completion-plan.md <<'EOF'
# AION MVP Completion Plan

## Phase 1: Stabilize Existing Core

- Keep all current tests green.
- Remove backward-compatibility regressions.
- Validate API schemas.
- Validate database migrations.
- Validate worker job lifecycle.
- Add structured error responses.
- Add deterministic audio tests.

## Phase 2: Complete Audio MVP

- Add stereo rendering.
- Add binaural beats.
- Add isochronic tones.
- Add seamless looping.
- Add chunked generation for long durations.
- Add limiter and clipping protection.
- Add FLAC and MP3 export through FFmpeg.
- Add downloadable asset endpoint.

## Phase 3: Minimal User Interface

- Project list.
- New audio job form.
- Job status view.
- Preset selector.
- Audio preview.
- Download button.

## Phase 4: Media Expansion

- Artwork generation.
- Video rendering.
- Metadata generation.
- Publishing package generation.

## Phase 5: Platform Integrations

- YouTube upload.
- Distributor export package for Spotify, Apple Music and other platforms.
- Analytics import.
- Revenue reporting.

## Phase 6: Stabilization

- Environment doctor.
- macOS setup automation.
- Docker installation verification.
- CI pipeline.
- security checks.
- deployment documentation.
EOF

cat > docs/13-ai-implementation/AI_IMPLEMENTATION_PROMPT.md <<'EOF'
# AION Ambient Media Factory
## AI Implementation Prompt

You are acting as a senior software architect, principal engineer, DevOps engineer, audio DSP engineer and product engineer.

Your task is to inspect, complete and stabilize an existing repository named **AION**, an AI-assisted Ambient Media Factory.

Do not rewrite the project from scratch unless a specific part is irreparably broken. Preserve the existing architecture where reasonable, improve it incrementally and keep all existing working tests passing.

---

# 1. Product Goal

Build a production-capable application that allows one user to generate original ambient audio assets for:

- sleep;
- relaxation;
- meditation;
- focus;
- background listening;
- frequency-based ambient content;
- YouTube;
- music-distribution packages for Spotify, Apple Music, Amazon Music, Deezer and similar platforms.

The system must support legitimate content creation.

It must not automate:

- fake streams;
- artificial engagement;
- royalty manipulation;
- bot listeners;
- deceptive metadata;
- unsupported medical claims;
- copyright infringement.

---

# 2. Current Repository State

Assume the repository already contains:

- a FastAPI backend;
- SQLAlchemy models;
- Alembic migrations;
- PostgreSQL configuration;
- Redis queue design;
- a background worker;
- audio job models;
- audio generation services;
- WAV generation;
- sine tones;
- layered tones;
- white noise;
- pink noise;
- brown noise;
- fade-in and fade-out;
- deterministic random seeds;
- preset-based generation;
- pytest tests;
- Docker Compose configuration;
- project documentation;
- an AION CLI skeleton.

Before changing code:

1. inspect the entire repository;
2. run the existing tests;
3. identify current failures;
4. fix regressions first;
5. document every architectural change;
6. do not invent existing capabilities.

---

# 3. Primary Objective

Complete a stable MVP that supports the full workflow:

1. create a project;
2. submit an audio-generation job;
3. validate the request;
4. persist the job in PostgreSQL;
5. enqueue the job in Redis;
6. process the job in a background worker;
7. generate a valid audio asset;
8. store the asset;
9. update job status;
10. retrieve job metadata;
11. download the generated file;
12. verify the entire flow with automated tests.

---

# 4. Required Functional Capabilities

## 4.1 Project Management

Implement:

- create project;
- list projects;
- retrieve project;
- update project;
- archive project.

Project fields should include:

- id;
- name;
- slug;
- description;
- status;
- brand name;
- default sample rate;
- default output format;
- created_at;
- updated_at.

## 4.2 Audio Job Management

Implement:

- submit job;
- retrieve job;
- list jobs;
- cancel queued job;
- retry failed job;
- retrieve logs;
- download output.

Job statuses must include:

- draft;
- queued;
- processing;
- awaiting_review;
- completed;
- failed;
- cancelled.

## 4.3 Audio Generation Modes

Support:

- sine;
- layered_tones;
- white_noise;
- pink_noise;
- brown_noise;
- binaural_beats;
- isochronic_tones;
- preset;
- mixed_ambient.

## 4.4 Audio Controls

Support:

- duration;
- sample rate;
- bit depth;
- mono or stereo;
- amplitude;
- fade-in;
- fade-out;
- deterministic seed;
- tone frequency;
- tone layers;
- left-channel frequency;
- right-channel frequency;
- beat frequency;
- modulation depth;
- preset name;
- output format.

## 4.5 Output Formats

Support:

- WAV;
- FLAC;
- MP3.

Use FFmpeg for encoded formats.

Do not require FFmpeg for basic WAV unit tests.

## 4.6 Seamless Looping

Implement loop-safe generation.

Requirements:

- optional seamless-loop mode;
- crossfade loop boundaries;
- no audible click at the loop point;
- automated test based on boundary discontinuity.

## 4.7 Long-Form Rendering

Support long-form output without loading the entire audio file into memory.

Use:

- chunked generation;
- streaming writes;
- bounded memory;
- progress reporting;
- resumable jobs where practical.

Target durations:

- 1 minute;
- 10 minutes;
- 30 minutes;
- 1 hour;
- 3 hours;
- 8 hours.

## 4.8 Asset Storage

Initially support:

- local filesystem;
- MinIO-compatible object storage.

Every asset must include:

- asset id;
- project id;
- job id;
- file path or object key;
- format;
- duration;
- sample rate;
- channels;
- bit depth;
- file size;
- checksum;
- creation timestamp;
- provenance metadata.

## 4.9 Preset System

Implement versioned presets.

Initial presets:

- calm-432;
- deep-brown;
- soft-pink;
- focus-alpha-bed;
- sleep-binaural-delta;
- meditation-binaural-theta;
- focus-binaural-alpha;
- soft-isochronic-alpha.

Each preset must specify:

- mode;
- frequencies;
- amplitudes;
- channel configuration;
- fades;
- recommended duration;
- allowed overrides;
- description;
- version.

## 4.10 Review Workflow

Implement:

- generated;
- awaiting_review;
- approved;
- rejected.

Publishing must never occur before explicit approval.

---

# 5. API Requirements

Use versioned REST endpoints under:

`/api/v1`

Required endpoint groups:

- `/projects`
- `/audio/jobs`
- `/audio/assets`
- `/audio/presets`
- `/health`
- `/readiness`

Provide:

- OpenAPI documentation;
- validation errors;
- structured error objects;
- correlation IDs;
- pagination;
- idempotency for job submission.

Example structured error:

```json
{
  "error": {
    "code": "AUDIO_JOB_INVALID",
    "message": "The requested audio job is invalid.",
    "details": {},
    "correlation_id": "uuid"
  }
}
```

---

# 6. Worker Requirements

The worker must:

- consume Redis jobs;
- claim jobs safely;
- avoid duplicate processing;
- update job state;
- report progress;
- persist errors;
- retry transient failures;
- avoid retrying permanent validation failures;
- support graceful shutdown;
- emit structured logs;
- preserve correlation IDs.

Implement:

- retry count;
- maximum retries;
- retry delay;
- dead-letter queue;
- heartbeat;
- stale-job recovery.

---

# 7. Database Requirements

Use PostgreSQL.

Required tables:

- projects;
- audio_jobs;
- audio_assets;
- presets;
- job_events;
- audit_events.

Add:

- indexes;
- foreign keys;
- timestamps;
- status constraints where practical;
- migration tests;
- reversible Alembic migrations.

Do not store large audio binaries in PostgreSQL.

---

# 8. DSP and Audio Quality Requirements

Implement DSP carefully.

Requirements:

- no clipping;
- bounded amplitude;
- limiter or peak normalization;
- fade curves;
- deterministic rendering when a seed is supplied;
- stereo safety;
- channel isolation for binaural beats;
- sample-accurate duration;
- valid WAV headers;
- valid encoded output;
- no NaN or infinite samples.

For binaural beats:

- left and right channels must use different carrier frequencies;
- the beat frequency must be the absolute difference between the channels;
- require stereo output;
- clearly describe this as ambient or meditation audio, not medical treatment.

For isochronic tones:

- use amplitude modulation;
- support configurable pulse frequency;
- support smooth modulation envelopes;
- prevent abrupt clicks.

---

# 9. Testing Requirements

All existing tests must remain green.

Add:

## Unit Tests

- waveform generation;
- noise determinism;
- fades;
- normalization;
- clipping prevention;
- binaural channel frequencies;
- isochronic modulation;
- preset validation;
- seamless loops;
- file metadata;
- job state transitions.

## Integration Tests

- PostgreSQL persistence;
- Alembic migrations;
- Redis queue;
- worker processing;
- local storage;
- MinIO storage.

## API Tests

- project lifecycle;
- job submission;
- job retrieval;
- validation errors;
- cancellation;
- retry;
- download.

## End-to-End Test

Create one project, submit one job, process it, validate the file and retrieve it through the API.

The default test suite must not require paid external services.

---

# 10. User Interface MVP

Build a minimal web interface.

Recommended stack:

- Next.js;
- TypeScript;
- React;
- Tailwind CSS.

Required screens:

- dashboard;
- projects;
- create project;
- audio generator;
- job status;
- audio asset detail;
- presets;
- settings.

The generator form should support:

- mode;
- preset;
- duration;
- sample rate;
- channels;
- output format;
- amplitude;
- fades;
- frequencies;
- seed.

Include:

- progress display;
- audio preview;
- download;
- retry;
- approve or reject.

---

# 11. Security Requirements

Implement:

- environment-based secrets;
- input validation;
- path traversal prevention;
- safe filenames;
- authorization boundaries;
- audit logs;
- rate limiting;
- file size limits;
- duration limits;
- safe subprocess execution for FFmpeg;
- no shell interpolation of user input.

Do not commit credentials.

---

# 12. Compliance Requirements

The product must:

- create original or properly licensed content;
- preserve provenance;
- avoid protected recordings;
- avoid imitation of recognizable artists;
- avoid fake engagement;
- avoid unsupported medical claims;
- require human approval before publishing.

Use language such as:

- relaxation;
- meditation;
- sleep;
- focus;
- ambient;
- mindfulness.

Do not claim:

- disease treatment;
- DNA repair;
- toxin removal;
- guaranteed neurological effects;
- replacement of medical care.

---

# 13. Architecture Requirements

Prefer a modular monolith for the MVP.

Use clear domain boundaries:

- projects;
- jobs;
- audio;
- presets;
- storage;
- review;
- publishing;
- analytics;
- audit.

Use background workers for expensive media generation.

Do not introduce Kubernetes or dozens of microservices for the MVP.

The code must remain extractable into services later.

---

# 14. Developer Experience

Provide:

- `make setup`;
- `make test`;
- `make lint`;
- `make api`;
- `make worker`;
- `make infra-up`;
- `make infra-down`;
- `make smoke`;
- `make doctor`.

Support macOS and Linux.

Document required versions:

- Python 3.12+;
- PostgreSQL 16+;
- Redis 7+;
- FFmpeg;
- Docker where available.

Provide a non-Docker development path.

---

# 15. Deliverables

Produce:

1. working backend;
2. working worker;
3. database migrations;
4. audio engine;
5. storage abstraction;
6. minimal web UI;
7. automated tests;
8. Docker Compose;
9. setup scripts;
10. API documentation;
11. architecture documentation;
12. security notes;
13. operations guide;
14. sample presets;
15. sample generated asset.

---

# 16. Implementation Rules

- Inspect before modifying.
- Keep commits small and coherent.
- Do not delete working functionality without justification.
- Preserve backward compatibility where practical.
- Add tests before or with each feature.
- Do not mark work complete when tests fail.
- Do not hide warnings that indicate real incompatibility.
- Document incomplete areas honestly.
- Prefer clear code over premature optimization.
- Avoid unnecessary dependencies.
- Do not use external paid APIs for core audio generation.

---

# 17. Required Execution Order

Implement in this order:

1. repository inspection;
2. current test stabilization;
3. database and migration stabilization;
4. job lifecycle;
5. audio engine completion;
6. storage abstraction;
7. download endpoint;
8. end-to-end test;
9. minimal UI;
10. documentation;
11. environment doctor;
12. final full test run.

---

# 18. Completion Criteria

The implementation is complete only when:

- all automated tests pass;
- local setup is documented;
- one project can be created;
- one audio job can be queued;
- one worker can process it;
- one WAV file can be downloaded;
- one FLAC or MP3 file can be generated when FFmpeg exists;
- binaural and isochronic modes are tested;
- long-form generation uses bounded memory;
- review status is enforced;
- no publishing occurs automatically;
- security and compliance notes are present;
- no unsupported claims are included.

---

# 19. Final AI Response Format

At the end, provide:

1. implementation summary;
2. files changed;
3. architecture decisions;
4. commands to run;
5. test results;
6. known limitations;
7. next recommended milestone.

Do not claim success unless the test suite has actually passed.
EOF

echo "AION Update 009 applied successfully."
echo
echo "Created:"
echo "  docs/00-overview/current-mvp-summary.md"
echo "  docs/12-roadmap/mvp-completion-plan.md"
echo "  docs/13-ai-implementation/AI_IMPLEMENTATION_PROMPT.md"
echo
echo "Repository:"
echo "  ${TARGET}"
