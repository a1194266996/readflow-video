from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from readflow_video.ai_video import get_ai_video_status
from readflow_video.renderer import RenderOptions, render_project
from readflow_video.schemas import RenderRequest, ScriptRequest
from readflow_video.script import generate_script

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "storage"
OUTPUTS = STORAGE / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Readflow Video API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/script")
def create_script(request: ScriptRequest):
    return generate_script(
        prompt=request.prompt,
        scene_count=request.scene_count,
        style=request.style,
    )


@app.get("/api/ai/status")
def ai_status():
    return get_ai_video_status()


@app.post("/api/render")
def render_video(request: RenderRequest):
    project = request.project or generate_script(
        prompt=request.prompt,
        scene_count=request.scene_count,
        style=request.style,
    )
    if request.ai_engine == "svd" and len(project.scenes) > 3:
        project.scenes = project.scenes[:3]
    try:
        result = render_project(
            project,
            RenderOptions(
                output_dir=OUTPUTS,
                voice=request.voice,
                with_tts=request.with_tts,
                animated=request.animated,
                ai_engine=request.ai_engine,
                visual_style=request.visual_style,
                character=request.character,
                karaoke=request.karaoke,
            ),
        )
    except RuntimeError as exc:
        if request.ai_engine == "svd":
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise
    return {
        "project": project,
        "video_url": f"/outputs/{result.video_path.name}",
        "srt_url": f"/outputs/{result.srt_path.name}",
        "duration": result.duration,
    }
