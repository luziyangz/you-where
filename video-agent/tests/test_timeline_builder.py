from app.models.schemas import AudioInfo, SourceInfo
from app.services.timeline_builder import build_timeline


def test_build_timeline_has_stable_schema_version() -> None:
    timeline = build_timeline(
        video_id="video-1",
        source=SourceInfo(
            filename="clip.mp4",
            duration_seconds=1.0,
            width=1920,
            height=1080,
            fps=30.0,
        ),
        audio=AudioInfo(language="zh", segments=[]),
        shots=[],
    )

    assert timeline.schema_version == "1.0"
    assert timeline.video_id == "video-1"
    assert timeline.shots == []
