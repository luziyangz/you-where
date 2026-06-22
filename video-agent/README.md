# video-agent

`video-agent` is a local-first FastAPI backend for short-video analysis. The MVP prepares a service that can later be called by external workflow tools through HTTP APIs.

## MVP Scope

The first implementation phase will support:

- video upload
- local video storage
- ffprobe metadata extraction
- FFmpeg audio extraction
- faster-whisper transcription
- PySceneDetect shot detection
- FFmpeg keyframe extraction
- stable timeline JSON output

This initialization only creates the project environment, harness files, skeleton modules, and base configuration.

## Requirements

- Python 3.11+
- FFmpeg and ffprobe available on `PATH`

## Setup

```bash
make install
```

## Development

```bash
make dev
```

## Checks

```bash
make test
make lint
make typecheck
```

## Context Boundary

Before contributing, read `docs/CONTEXT_BOUNDARY.md`. Repository content must remain limited to neutral engineering requirements, code, tests, and public reference notes.
