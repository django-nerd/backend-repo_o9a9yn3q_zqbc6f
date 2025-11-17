import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import WebSocket, WebSocketDisconnect

from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import (
    User, Project, MediaAsset, RenderJob, Timeline, TrackItem,
    AIGenerateRequest, AIGenerateResponse,
    TranscribeRequest, TTSRequest, EnhanceAudioRequest, UploadUrlRequest,
    SubtitleTrack, Template
)

app = FastAPI(title="AI Video Editor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In a real system we would integrate cloud storage signed URLs.
# For this environment, we will simulate upload by accepting files and placing them in a local 'uploads' folder.
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Simple in-memory WebSocket hub for preview events
class PreviewHub:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(project_id, []).append(websocket)

    def disconnect(self, project_id: str, websocket: WebSocket):
        if project_id in self.connections and websocket in self.connections[project_id]:
            self.connections[project_id].remove(websocket)

    async def broadcast(self, project_id: str, event: Dict[str, Any]):
        for ws in list(self.connections.get(project_id, [])):
            try:
                await ws.send_json(event)
            except WebSocketDisconnect:
                self.disconnect(project_id, ws)
            except Exception:
                self.disconnect(project_id, ws)

hub = PreviewHub()

@app.get("/")
def root():
    return {"status": "ok", "service": "AI Video Editor API"}

@app.get("/schema")
def get_schema_summary():
    return {
        "collections": ["user", "project", "mediaasset", "renderjob", "template"],
    }

# Auth endpoints (simplified demo)
class LoginRequest(BaseModel):
    email: str
    name: str | None = None
    provider: str = "email"

@app.post("/auth/login")
def login(req: LoginRequest):
    existing = db["user"].find_one({"email": req.email}) if db else None
    if existing:
        user_id = str(existing.get("_id"))
    else:
        user = User(email=req.email, name=req.name, provider=req.provider)
        user_id = create_document("user", user)
    token = str(uuid.uuid4())
    return {"token": token, "user_id": user_id}

# Project endpoints
@app.post("/projects")
def create_project(title: str = Form(...), aspect_ratio: str = Form("16:9"), user_id: str = Form(...)):
    project = Project(user_id=user_id, title=title, aspect_ratio=aspect_ratio)  # type: ignore
    project_id = create_document("project", project)
    return {"project_id": project_id}

@app.get("/projects")
def list_projects(user_id: str):
    docs = get_documents("project", {"user_id": user_id}, limit=50)
    for d in docs:
        d["_id"] = str(d.get("_id"))
    return {"items": docs}

# Uploads
@app.post("/upload")
async def upload_file(user_id: str = Form(...), kind: str = Form(...), file: UploadFile = File(...)):
    dest = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    with open(dest, "wb") as f:
        f.write(await file.read())
    url = f"/uploads/{os.path.basename(dest)}"
    asset = MediaAsset(user_id=user_id, kind=kind, filename=file.filename, url=url)
    asset_id = create_document("mediaasset", asset)
    return {"asset_id": asset_id, "url": url}

@app.get("/uploads/{name}")
def get_upload(name: str):
    path = os.path.join(UPLOAD_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    def iterfile():
        with open(path, "rb") as f:
            yield from f
    return StreamingResponse(iterfile(), media_type="application/octet-stream")

# AI generation stubs (simulate jobs)
@app.post("/ai/generate", response_model=AIGenerateResponse)
def ai_generate(req: AIGenerateRequest):
    job = RenderJob(user_id="system", status="queued", params={"prompt": req.prompt, "mode": "text2video"})
    job_id = create_document("renderjob", job)
    return AIGenerateResponse(job_id=job_id, message="Job queued")

@app.post("/ai/transcribe")
def ai_transcribe(req: TranscribeRequest):
    # Simulate transcript
    segments = [
        {"start_ms": 0, "end_ms": 1500, "text": "Hello everyone"},
        {"start_ms": 1600, "end_ms": 3200, "text": "welcome to the AI editor"},
    ]
    return {"language": req.language or "en", "segments": segments}

@app.post("/ai/tts")
def ai_tts(req: TTSRequest):
    # Simulate generated audio URL
    fake_url = f"/tts/{uuid.uuid4()}.wav"
    return {"url": fake_url}

@app.post("/ai/enhance-audio")
def enhance_audio(req: EnhanceAudioRequest):
    return {"status": "ok", "strength": req.strength}

# Render queue stubs
@app.post("/render/queue")
def queue_render(project_id: str, user_id: str, resolution: str = "1080p", aspect_ratio: str = "16:9"):
    job = RenderJob(user_id=user_id, project_id=project_id, status="queued", resolution=resolution, aspect_ratio=aspect_ratio)
    job_id = create_document("renderjob", job)
    return {"job_id": job_id}

@app.get("/render/jobs")
def list_jobs(user_id: str):
    docs = get_documents("renderjob", {"user_id": user_id}, limit=50)
    for d in docs:
        d["_id"] = str(d.get("_id"))
    return {"items": docs}

# WebSocket for live preview events
@app.websocket("/ws/preview/{project_id}")
async def preview_ws(websocket: WebSocket, project_id: str):
    await hub.connect(project_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await hub.broadcast(project_id, {"type": "event", "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        hub.disconnect(project_id, websocket)
    except Exception:
        hub.disconnect(project_id, websocket)

# Simple templates
@app.get("/templates")
def get_templates():
    templates = [
        {"key": "tiktok_fast", "title": "TikTok Fast Cut", "aspect_ratio": "9:16"},
        {"key": "yt_talking_head", "title": "YouTube Talking Head", "aspect_ratio": "16:9"},
        {"key": "promo_glitch", "title": "Promo Glitch", "aspect_ratio": "1:1"},
    ]
    return {"items": templates}

# Health
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
