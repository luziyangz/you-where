from datetime import UTC, datetime

from app.models.schemas import AudioInfo, Shot, SourceInfo, Timeline


def build_timeline(
    video_id: str,
    source: SourceInfo,
    audio: AudioInfo,
    shots: list[Shot],
) -> Timeline:
    return Timeline(
        video_id=video_id,
        source=source,
        audio=audio,
        shots=shots,
        created_at=datetime.now(UTC),
    )
