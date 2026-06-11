import os
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

SVD_MODEL_ID = os.getenv("READFLOW_SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt-1-1")


def _run_ffmpeg(args: list[str]) -> None:
    completed = subprocess.run(["ffmpeg", "-y", *args], text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:])


def _check_ai_runtime():
    try:
        import torch
        from diffusers import StableVideoDiffusionPipeline
    except ImportError as exc:
        raise RuntimeError(
            "SVD dependencies are not installed. Run: pip install -r apps/api/requirements-ai.txt"
        ) from exc

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Fix the NVIDIA driver/GPU visibility before running SVD.")

    return torch, StableVideoDiffusionPipeline


def get_ai_video_status() -> dict[str, object]:
    status: dict[str, object] = {
        "engine": "svd",
        "model": SVD_MODEL_ID,
        "endpoint": os.getenv("HF_ENDPOINT"),
        "dependencies": False,
        "cuda": False,
        "device": None,
        "ready": False,
    }
    try:
        import torch
        import diffusers  # noqa: F401
    except ImportError as exc:
        status["reason"] = f"Missing dependency: {exc.name}"
        return status

    status["dependencies"] = True
    status["cuda"] = bool(torch.cuda.is_available())
    if status["cuda"]:
        status["device"] = torch.cuda.get_device_name(0)
    else:
        status["reason"] = "CUDA is not available"
        return status

    status["ready"] = True
    return status


@lru_cache(maxsize=1)
def _load_svd_pipeline():
    torch, pipeline_cls = _check_ai_runtime()
    dtype = torch.float16
    pipe = pipeline_cls.from_pretrained(SVD_MODEL_ID, torch_dtype=dtype, variant="fp16")
    pipe.enable_model_cpu_offload()
    pipe.unet.enable_forward_chunking()
    return pipe


def render_svd_segment(
    keyframe_path: Path,
    output_path: Path,
    duration: float,
    seed: int,
    num_frames: int = 8,
    num_inference_steps: int = 8,
    motion_bucket_id: int = 127,
    noise_aug_strength: float = 0.02,
) -> Path:
    torch, _pipeline_cls = _check_ai_runtime()
    pipe = _load_svd_pipeline()

    image = Image.open(keyframe_path).convert("RGB")
    image = image.resize((576, 1024), Image.Resampling.LANCZOS)
    generator = torch.manual_seed(seed)
    result = pipe(
        image,
        decode_chunk_size=1,
        generator=generator,
        motion_bucket_id=motion_bucket_id,
        noise_aug_strength=noise_aug_strength,
        num_frames=num_frames,
        num_inference_steps=num_inference_steps,
    )

    raw_path = output_path.with_name(output_path.stem + "-raw.mp4")
    from diffusers.utils import export_to_video

    export_to_video(result.frames[0], str(raw_path), fps=7)
    _run_ffmpeg(
        [
            "-stream_loop",
            "-1",
            "-i",
            str(raw_path),
            "-t",
            f"{duration:.2f}",
            "-vf",
            "scale=1080:1920,fps=30,format=yuv420p",
            "-an",
            str(output_path),
        ]
    )
    return output_path
