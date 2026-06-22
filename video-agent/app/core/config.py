from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "video-agent"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    storage_root: str = "./storage"
    upload_max_mb: int = 500
    video_max_seconds: int = 600

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    ffmpeg_timeout_seconds: int = 300

    whisper_model: str = "small"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "int8_float16"
    whisper_language: str = "zh"

    scene_detect_threshold: float = 27.0
    keyframes_per_shot: int = 3

    ocr_enabled: bool = False
    vision_enabled: bool = False
    vision_provider: str = "mock"

    api_auth_enabled: bool = False
    api_key: str = Field(default="change-me", repr=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
