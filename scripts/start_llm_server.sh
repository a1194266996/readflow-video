#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${READFLOW_LLM_MODEL_PATH:-/data1/home/llw/AI/models/Qwen3-14B-GGUF/Qwen3-14B-128K-Q4_K_M.gguf}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/data1/home/llw/AI/tools/llama.cpp}"
HOST="${READFLOW_LLM_HOST:-127.0.0.1}"
PORT="${READFLOW_LLM_PORT:-8020}"
CTX_SIZE="${READFLOW_LLM_CTX_SIZE:-8192}"
GPU_LAYERS="${READFLOW_LLM_GPU_LAYERS:-99}"

exec "${LLAMA_CPP_DIR}/build/bin/llama-server" \
  -m "${MODEL_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --ctx-size "${CTX_SIZE}" \
  --n-gpu-layers "${GPU_LAYERS}"
