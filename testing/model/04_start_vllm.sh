#!/usr/bin/env bash
set -e

MODEL_DIR="${MODEL_DIR:-/home/cdsw/models/Qwen3.8-27B-AWQ}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-4}"

echo "Starting vLLM"
echo "MODEL_DIR               = ${MODEL_DIR}"
echo "HOST                    = ${HOST}"
echo "PORT                    = ${PORT}"
echo "MAX_MODEL_LEN           = ${MAX_MODEL_LEN}"
echo "GPU_MEMORY_UTILIZATION  = ${GPU_MEMORY_UTILIZATION}"
echo "MAX_NUM_SEQS            = ${MAX_NUM_SEQS}"
echo ""

python -m vllm.entrypoints.openai.api_server \
  --model "${MODEL_DIR}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --max-num-seqs "${MAX_NUM_SEQS}" \
  --trust-remote-code
