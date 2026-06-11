# Readflow Video

Readflow Video turns a prompt into a vertical reading video for short-form platforms.

The first version focuses on a reliable local workflow:

- Generate a 6-scene reading script from a prompt
- Render 1080x1920 animated reading scenes
- Draw a simple speaking character and topic illustration
- Add camera pan/zoom and karaoke-style subtitle highlighting
- Optional Stable Video Diffusion image-to-video engine
- Generate voice-over with Edge TTS when available
- Fall back to silent audio for offline smoke tests
- Export an animated MP4 with FFmpeg
- Provide a small FastAPI backend and React web UI

## Layout

```text
apps/
  api/                 FastAPI app
  web/                 React + Vite UI
packages/
  readflow_video/      Script and rendering core
tests/                 Smoke tests
storage/               Runtime uploads and outputs
```

## System Dependencies

```bash
sudo apt update
sudo apt install -y ffmpeg fonts-noto-cjk
```

## Backend

```bash
cd /data/work/AI/readflow-video
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
uvicorn apps.api.main:app --host 0.0.0.0 --port 8010
```

Open `http://localhost:8010/docs` for API docs.

The web app automatically connects to the API on the same host:

```text
http://<current-browser-host>:8010
```

For example, opening `http://SERVER_IP:5173` will call `http://SERVER_IP:8010`.
Set `VITE_API_URL` only when the API is intentionally hosted somewhere else.

## Optional AI Video Engine

The `svd` engine uses Stable Video Diffusion XT 1.1 as an image-to-video step.
It is optional because the model is large and requires a working CUDA GPU.

```bash
cd /data/work/AI/readflow-video
source .venv/bin/activate
pip install -r apps/api/requirements-ai.txt
python -m readflow_video.cli --ai-engine svd --no-tts "普通人如何提高行动力"
```

Default model:

```text
stabilityai/stable-video-diffusion-img2vid-xt-1-1
```

Override it with:

```bash
export READFLOW_SVD_MODEL=stabilityai/stable-video-diffusion-img2vid-xt-1-1
```

The app defaults to the Hugging Face mirror endpoint:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

If CUDA is unavailable, use the default `template` engine until the NVIDIA driver is fixed.

## Frontend

```bash
cd /data/work/AI/readflow-video/apps/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## CLI Smoke Render

```bash
cd /data/work/AI/readflow-video
source .venv/bin/activate
python -m readflow_video.cli "30岁以后一定要明白的5个人生道理"
```

The MP4 will be written under `storage/outputs`.

Use `--static` if you want the older static-card renderer.
Use `--no-karaoke` to disable subtitle highlighting.
