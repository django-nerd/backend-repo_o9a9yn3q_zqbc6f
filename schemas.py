"""
Database Schemas for AI Video Editor

Each Pydantic model maps to a MongoDB collection using the lowercase class name.
Example: class Project -> collection "project"
"""
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

class User(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: Literal["email", "google"] = "email"
    is_active: bool = True

class AuthSession(BaseModel):
    user_id: str
    token: str
    expires_at: datetime
    device: Optional[str] = None

class MediaAsset(BaseModel):
    project_id: Optional[str] = None
    user_id: str
    kind: Literal["video", "audio", "image"]
    filename: str
    url: str
    duration_ms: Optional[int] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class TrackItem(BaseModel):
    id: str
    type: Literal["clip", "audio", "image", "title", "effect"]
    src: Optional[str] = None
    start_ms: int
    end_ms: int
    transform: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)

class Timeline(BaseModel):
    fps: int = 30
    width: int = 1920
    height: int = 1080
    duration_ms: int = 0
    tracks: Dict[str, List[TrackItem]] = Field(default_factory=lambda: {
        "video": [],
        "audio": [],
        "titles": [],
        "effects": []
    })

class Project(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    timeline: Timeline = Field(default_factory=Timeline)
    cover_url: Optional[str] = None
    template: Optional[str] = None

class RenderJob(BaseModel):
    user_id: str
    project_id: Optional[str] = None
    status: Literal["queued", "processing", "preview", "completed", "failed"] = "queued"
    resolution: Literal["720p", "1080p", "4K"] = "1080p"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    output_url: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)

class SubtitleSegment(BaseModel):
    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None

class SubtitleTrack(BaseModel):
    language: str = "en"
    segments: List[SubtitleSegment]

class AIGenerateRequest(BaseModel):
    prompt: str
    language: Optional[str] = "en"
    voice: Optional[str] = "alloy"
    style: Optional[str] = None
    duration_s: Optional[int] = 30
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"

class AIGenerateResponse(BaseModel):
    job_id: str
    message: str

class TranscribeRequest(BaseModel):
    url: str
    language: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    language: Optional[str] = None

class EnhanceAudioRequest(BaseModel):
    url: str
    strength: Literal["low", "medium", "high"] = "medium"

class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    kind: Literal["video", "audio", "image"]

class Template(BaseModel):
    key: str
    title: str
    description: Optional[str] = None
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    timeline: Timeline = Field(default_factory=Timeline)
