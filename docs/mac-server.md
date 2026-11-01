# Mac Research Server migration

## Intended architecture

Windows Codex → thin MCP bridge → SSH tunnel → loopback API on Mac → durable job queue → document/OCR workers → validated results + cache.

Search/short text reads can complete synchronously. OCR submits a durable job ID; progress, completed pages, partial output and errors remain retrievable after client disconnect. Start with one OCR worker and one loaded VLM because the target Mac has 16 GiB unified memory. SQLite is the proposed initial queue/storage index; no queue implementation is claimed in this bootstrap.

Source-control workflow: change a `codex/` branch, commit, validate, push, then fetch the exact commit on Mac. Record the deployed commit with every job. Deploy from Git rather than copying virtual environments or changing production files manually.

## Service placement

- SearXNG: ARM64-compatible Docker service, regenerated server config and secret, loopback port only.
- Gateway, browser/PDF workers: native Python environments, ARM64 dependencies.
- OCR: native Metal/MLX/Paddle-supported environments, separately pinned per backend. Keep completion reasons, model revision and actual memory measurements.
- Client transport: existing SSH key authentication and loopback forwarding. No app-server port needs public exposure.
- Firecrawl: connected client tool handoff remains explicit; moving code does not transfer the client's plugin credentials.

## Readiness checklist

1. Git checkout on Mac and dependency environments; system Python 3.9 is below the package requirement.
2. Start/configure SearXNG on Mac. Docker Desktop is installed but its daemon was not running during inspection.
3. Fix OCR completion status for timeout/token limits, repetition detection and page/table completeness.
4. Introduce layout/region processing and native OCR backend; validate model outputs on the existing real-document corpus plus held-out pages.
5. Add job submission/status/result/upload API and Windows MCP bridge; verify transfer hash, disconnect/retry, queue limits and per-page resume.
6. Configure launchd and wake behavior. The inspected machine slept after one minute; resolve this for server operation.
7. Test exact end-to-end calls before switching Windows to the Mac server. Keep the existing local prototype available until the server passes these checks.

## Official backend guidance

[PaddleOCR Apple Silicon guide](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html) documents native installation and a separate MLX-VLM recognition service. The recognition endpoint alone is not the complete document parsing pipeline; layout and result assembly must remain in front of it. Runtime speed, accuracy and peak memory on this Mac are not yet measured.

## Current state

Research code/data was first staged as a verified archive on the Mac. That staged release is a migration snapshot. The Git checkout of this repository is the source-control location for subsequent work; production activation is still pending.
