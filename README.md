# Readflow Video

Readflow Video turns a prompt into a vertical short video for Douyin, Xiaohongshu, Bilibili, and similar platforms.

The first version focuses on a reliable local workflow:

- Generate a reading script from a prompt
- Render 1080x1920 animated reading scenes
- Draw a simple speaking character and topic illustration
- Add camera pan/zoom and karaoke-style subtitle highlighting
- Generate prompt-to-video clips with Wan2.2
- Keep Stable Video Diffusion as an image-to-video fallback
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

The default `wan` engine uses `Wan-AI/Wan2.2-TI2V-5B-Diffusers` for prompt-to-video
generation. It is a better fit for 24GB GPUs such as RTX 4090/4090D than the older
SVD image-to-video fallback.

The `svd` engine uses Stable Video Diffusion XT 1.1 as an image-to-video step.
Both AI engines are optional because the models are large and require a working CUDA GPU.

```bash
cd /data/work/AI/readflow-video
source .venv/bin/activate
pip install -r apps/api/requirements-ai.txt
python -m readflow_video.cli --ai-engine wan --no-tts "a cat and a mouse fighting in a cartoon living room"
python -m readflow_video.cli --ai-engine svd --no-tts "how to improve daily focus"
```

Default models:

```text
Wan-AI/Wan2.2-TI2V-5B-Diffusers
stabilityai/stable-video-diffusion-img2vid-xt-1-1
```

Override them with:

```bash
export READFLOW_WAN_MODEL=Wan-AI/Wan2.2-TI2V-5B-Diffusers
export READFLOW_SVD_MODEL=stabilityai/stable-video-diffusion-img2vid-xt-1-1
```

The app defaults to the Hugging Face mirror endpoint:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

If CUDA is unavailable, use the `template` engine until the NVIDIA driver is fixed.

## Optional LLM Director

The web UI can call an OpenAI-compatible chat model from the FastAPI backend. Use
this for prompt rewriting, shot planning, and Wan2.2 prompt optimization. Never put
LLM API keys in the frontend.

Recommended local model for RTX 4090/4090D 24GB:

```text
Qwen3-14B-128K-Q4_K_M.gguf
```

Practical 24GB guidance:

```text
7B/8B Q4/Q5: very easy, fast, plenty of VRAM left
14B Q4_K_M/Q5_K_M: recommended balance for this app
32B Q4_K_M: possible, but tight when Wan2.2 is also running
70B Q4: not recommended on a single 24GB GPU
```

Example local llama.cpp server:

```bash
cd /data1/home/llw/AI/tools/llama.cpp
./build/bin/llama-server \
  -m /data1/home/llw/AI/models/Qwen3-14B-GGUF/Qwen3-14B-128K-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8020 \
  --ctx-size 8192 \
  --n-gpu-layers 99
```

Backend environment:

```bash
export READFLOW_LLM_BASE_URL=http://127.0.0.1:8020/v1
export READFLOW_LLM_MODEL=qwen3-14b-q4
export READFLOW_LLM_API_KEY=not-needed
```

For hosted providers such as DeepSeek or DashScope/Qwen, point
`READFLOW_LLM_BASE_URL`, `READFLOW_LLM_MODEL`, and `READFLOW_LLM_API_KEY` at their
OpenAI-compatible endpoint instead.

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
python -m readflow_video.cli "five life lessons after age 30"
```

The MP4 will be written under `storage/outputs`.

Use `--static` if you want the older static-card renderer.
Use `--no-karaoke` to disable subtitle highlighting.
