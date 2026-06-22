from fastapi.testclient import TestClient

from app.main import app


def test_analyze_rejects_non_video_upload() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/videos/analyze",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_analyze_accepts_video_upload_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/videos/analyze",
        files={"file": ("clip.mp4", b"not-a-real-video-yet", "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["task_id"]
