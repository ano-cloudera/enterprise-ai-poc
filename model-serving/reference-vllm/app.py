import os
import sys
import time
import subprocess
import requests

BASE_DIR = "/home/cdsw/tempo_llm_vllm_test/vllm"
MODEL_DIR = os.getenv("MODEL_DIR", "/home/cdsw/models/Qwen3.8-27B-AWQ")
APP_PORT = os.getenv("CDSW_READONLY_PORT") or os.getenv("CDSW_APP_PORT")
VLLM_PORT = os.getenv("VLLM_INTERNAL_PORT", "9000")
MAX_WAIT_SECONDS = int(os.getenv("VLLM_STARTUP_TIMEOUT", "900"))

if not APP_PORT:
    raise RuntimeError("CDSW_READONLY_PORT / CDSW_APP_PORT not found.")

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)
os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"

vllm_cmd = [
    "vllm", "serve", MODEL_DIR,
    "--host", "127.0.0.1",
    "--port", str(VLLM_PORT),
    "--max-model-len", "4096",
    "--gpu-memory-utilization", "0.90",
    "--max-num-seqs", "4",
    "--trust-remote-code",
]

print("Starting vLLM...")
print(" ".join(vllm_cmd))
vllm_process = subprocess.Popen(vllm_cmd, env=os.environ.copy())

models_url = f"http://127.0.0.1:{VLLM_PORT}/v1/models"
start_time = time.time()

while True:
    elapsed = int(time.time() - start_time)

    if vllm_process.poll() is not None:
        raise RuntimeError(f"vLLM exited during startup with code {vllm_process.returncode}")

    try:
        r = requests.get(models_url, timeout=10)
        print(f"[{elapsed}s] /v1/models -> HTTP {r.status_code}")
        if r.status_code == 200:
            print("vLLM READY")
            break
    except requests.RequestException:
        print(f"[{elapsed}s] vLLM still starting...")

    if elapsed >= MAX_WAIT_SECONDS:
        raise RuntimeError(f"vLLM did not become ready within {MAX_WAIT_SECONDS}s")

    time.sleep(5)

proxy_cmd = [
    sys.executable, "-m", "uvicorn", "proxy:app",
    "--host", "127.0.0.1",
    "--port", str(APP_PORT),
    "--app-dir", BASE_DIR,
    "--log-level", "info",
]

print("Starting proxy...")
proxy_process = subprocess.Popen(proxy_cmd, env=os.environ.copy())

try:
    while True:
        if proxy_process.poll() is not None:
            raise RuntimeError(f"Proxy exited with code {proxy_process.returncode}")
        if vllm_process.poll() is not None:
            raise RuntimeError(f"vLLM exited with code {vllm_process.returncode}")
        time.sleep(5)
finally:
    if proxy_process.poll() is None:
        proxy_process.terminate()
    if vllm_process.poll() is None:
        vllm_process.terminate()
