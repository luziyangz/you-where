from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str


class AnalyzeAcceptedResponse(BaseModel):
    task_id: str
    status: Literal["accepted"]
    message: str


class SourceInfo(BaseModel):
    filename: str
    duration_seconds: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    fps: float = Field(ge=0)


class TranscriptSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str


class AudioInfo(BaseModel):
    language: str
    segments: list[TranscriptSegment]


class Shot(BaseModel):
    shot_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    keyframes: list[str]


class Timeline(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    video_id: str
    source: SourceInfo
    audio: AudioInfo
    shots: list[Shot]
    created_at: datetime
