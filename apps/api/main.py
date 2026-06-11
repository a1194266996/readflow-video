import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

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

JOBS: dict[str, dict] = {}
JOBS_LOCK = Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=1)

app = FastAPI(title="Readflow Video API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _output_url(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return f"/outputs/{path.resolve().relative_to(OUTPUTS.resolve()).as_posix()}"
    except ValueError:
        return None


def _set_job(job_id: str, **changes) -> dict:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.update(changes)
        job["updated_at"] = _now()
        return dict(job)


def _get_job(job_id: str) -> dict:
    with JOBS_LOCK:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(JOBS[job_id])


def _run_render_job(job_id: str, project, request: RenderRequest) -> None:
    _set_job(job_id, status="running", message="Job started", progress=1)

    def on_progress(event: dict) -> None:
        scene_count = max(1, len(project.scenes))
        scene_index = int(event.get("scene_index") or 0)
        base = min(90, int((scene_index / scene_count) * 88)) if scene_index else 5
        if event.get("stage") == "done":
            base = 99
        preview_url = _output_url(event.get("preview_path"))
        changes = {
            "message": event.get("message", "Rendering"),
            "progress": base,
        }
        if preview_url:
            changes["preview_url"] = preview_url
        _set_job(job_id, **changes)

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
                progress_callback=on_progress,
            ),
        )
        _set_job(
            job_id,
            status="completed",
            message="Video completed",
            progress=100,
            video_url=f"/outputs/{result.video_path.name}",
            srt_url=f"/outputs/{result.srt_path.name}",
            preview_url=f"/outputs/{result.video_path.name}",
            duration=result.duration,
        )
    except Exception as exc:
        _set_job(job_id, status="failed", message="Render failed", error=str(exc), progress=100)


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


@app.get("/api/system/status")
def system_status():
    cpu_percent = None
    memory = None
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        memory = {
            "percent": mem.percent,
            "used_mb": round(mem.used / 1024 / 1024),
            "total_mb": round(mem.total / 1024 / 1024),
        }
    except Exception:
        pass

    gpu = None
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            capture_output=True,
            timeout=3,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            util, mem_used, mem_total, temp, power = [part.strip() for part in completed.stdout.splitlines()[0].split(",")]
            gpu = {
                "utilization": float(util),
                "memory_used_mb": float(mem_used),
                "memory_total_mb": float(mem_total),
                "memory_percent": round(float(mem_used) / max(1.0, float(mem_total)) * 100, 1),
                "temperature": float(temp),
                "power_w": float(power),
            }
    except Exception:
        pass

    return {"cpu_percent": cpu_percent, "memory": memory, "gpu": gpu, "updated_at": _now()}


@app.get("/api/jobs")
def list_jobs():
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda item: item["created_at"], reverse=True)
        return {"jobs": [dict(job) for job in jobs[:30]]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _get_job(job_id)


@app.post("/api/render")
def render_video(request: RenderRequest):
    project = request.project or generate_script(
        prompt=request.prompt,
        scene_count=request.scene_count,
        style=request.style,
    )
    if request.ai_engine == "svd" and len(project.scenes) > 3:
        project.scenes = project.scenes[:3]
    job_id = uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "message": "Queued",
        "progress": 0,
        "prompt": project.prompt,
        "title": project.title,
        "engine": request.ai_engine,
        "project": project,
        "preview_url": None,
        "video_url": None,
        "srt_url": None,
        "error": None,
        "duration": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    EXECUTOR.submit(_run_render_job, job_id, project, request)
    return {"job": _get_job(job_id)}
