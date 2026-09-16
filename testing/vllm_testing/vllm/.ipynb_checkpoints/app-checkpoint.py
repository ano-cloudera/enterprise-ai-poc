import os
import subprocess

MODEL_DIR = os.getenv(
    "MODEL_DIR",
    "/home/cdsw/models/Qwen3.8-27B-AWQ"
)

PORT = os.getenv("CDSW_APP_PORT", "8080")

# Disable FlashInfer sampler karena environment CAI tidak punya nvcc
os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"

cmd = [
    "vllm",
    "serve",
    MODEL_DIR,
    "--host", "0.0.0.0",
    "--port", PORT,
    "--max-model-len", "4096",
    "--gpu-memory-utilization", "0.90",
    "--max-num-seqs", "4",
    "--trust-remote-code",
]

print("Starting vLLM server...")
print(" ".join(cmd))

process = subprocess.Popen(cmd)
process.wait()