# AGENTS.md

This repository is a local-first AI short-video analysis backend named `video-agent`.

## Required Reading Order

Before changing code or documentation, read these files in order:

1. `docs/CONTEXT_BOUNDARY.md`
2. `docs/CONTRACTS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/HARNESS.md`
5. `docs/EXECUTION_PLAN.md`

## Current Scope

Only MVP Milestone 1-5 may be implemented:

1. Project scaffold and harness
2. Upload and storage primitives
3. FFmpeg and ffprobe wrappers
4. Audio transcription boundary
5. Scene and keyframe extraction boundary

Do not implement frontend, login, crawling, AI video generation, Dify integration, vector databases, cloud storage, or unapproved dependencies.

## Engineering Rules

- API behavior must follow `docs/CONTRACTS.md`.
- Uploaded videos must be streamed to disk and must not be loaded fully into memory.
- FFmpeg and ffprobe subprocess calls must use argument lists.
- Never use `shell=True` for FFmpeg or ffprobe.
- Generated runtime files must stay under `storage/`.
- Before finishing any task, run:

```bash
make test
make lint
```
