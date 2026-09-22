import os
import sys
import time
import subprocess
import requests


# =========================================================
# Configuration
# =========================================================

BASE_DIR = "/home/cdsw/tempo_llm_vllm_test/vllm"

MODEL_DIR = os.getenv(
    "MODEL_DIR",
    "/home/cdsw/models/Qwen3.8-27B-AWQ"
)

APP_PORT = (
    os.getenv("CDSW_READONLY_PORT")
    or os.getenv("CDSW_APP_PORT")
)

VLLM_PORT = os.getenv(
    "VLLM_INTERNAL_PORT",
    "9000"
)

MAX_WAIT_SECONDS = int(
    os.getenv("VLLM_STARTUP_TIMEOUT", "300")
)


if not APP_PORT:
    raise RuntimeError(
        "CDSW_READONLY_PORT / CDSW_APP_PORT not found."
    )


os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


# Disable FlashInfer sampler because CAI runtime
# does not provide nvcc / full CUDA Toolkit
os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"


print("=" * 60)
print("Tempo Scan LLM Application")
print("=" * 60)
print("Working directory :", os.getcwd())
print("Model directory   :", MODEL_DIR)
print("Application port  :", APP_PORT)
print("vLLM internal port:", VLLM_PORT)
print("=" * 60)
print()


# =========================================================
# Start vLLM
# =========================================================

vllm_cmd = [
    "vllm",
    "serve",
    MODEL_DIR,

    "--host",
    "127.0.0.1",

    "--port",
    str(VLLM_PORT),

    "--max-model-len",
    "4096",

    "--gpu-memory-utilization",
    "0.90",

    "--max-num-seqs",
    "4",

    "--trust-remote-code",
]


print("Starting vLLM...")
print(" ".join(vllm_cmd))
print()


vllm_process = subprocess.Popen(
    vllm_cmd,
    env=os.environ.copy()
)


print("vLLM PID:", vllm_process.pid)
print()


# =========================================================
# Wait until vLLM OpenAI API is ready
# =========================================================

MODELS_URL = f"http://127.0.0.1:{VLLM_PORT}/v1/models"

MAX_WAIT_SECONDS = int(
    os.getenv("VLLM_STARTUP_TIMEOUT", "900")
)

POLL_INTERVAL = 5

print("=" * 60)
print("Waiting for vLLM OpenAI API")
print("=" * 60)
print("URL     :", MODELS_URL)
print("Timeout :", MAX_WAIT_SECONDS, "seconds")
print()


start_time = time.time()
vllm_ready = False


while True:

    elapsed = int(time.time() - start_time)


    # -----------------------------------------------------
    # Check whether vLLM process crashed
    # -----------------------------------------------------

    return_code = vllm_process.poll()

    if return_code is not None:

        raise RuntimeError(
            f"vLLM exited during startup "
            f"with code {return_code}"
        )


    # -----------------------------------------------------
    # Try OpenAI-compatible endpoint
    # -----------------------------------------------------

    try:

        response = requests.get(
            MODELS_URL,
            timeout=10
        )

        print(
            f"[{elapsed}s] "
            f"/v1/models -> HTTP {response.status_code}"
        )


        if response.status_code == 200:

            print()
            print("=" * 60)
            print("vLLM READY")
            print("=" * 60)

            print(
                response.text[:2000]
            )

            print()

            vllm_ready = True
            break


    except requests.RequestException as e:

        print(
            f"[{elapsed}s] "
            f"vLLM still starting..."
        )


    # -----------------------------------------------------
    # Timeout check AFTER request attempt
    # -----------------------------------------------------

    if elapsed >= MAX_WAIT_SECONDS:

        raise RuntimeError(
            f"vLLM OpenAI API did not become ready "
            f"within {MAX_WAIT_SECONDS} seconds."
        )


    time.sleep(POLL_INTERVAL)


if not vllm_ready:

    raise RuntimeError(
        "vLLM readiness validation failed."
    )


# =========================================================
# Start FastAPI proxy
# =========================================================

proxy_cmd = [
    sys.executable,
    "-m",
    "uvicorn",

    "proxy:app",

    "--host",
    "127.0.0.1",

    "--port",
    str(APP_PORT),

    "--app-dir",
    BASE_DIR,

    "--log-level",
    "info"
]


print("Starting CAI API proxy...")
print(" ".join(proxy_cmd))
print()


proxy_process = subprocess.Popen(
    proxy_cmd,
    env=os.environ.copy()
)


print("Proxy PID:", proxy_process.pid)
print()


# =========================================================
# Keep Application Alive
# =========================================================

try:

    while True:

        # Proxy died
        proxy_return = proxy_process.poll()

        if proxy_return is not None:

            raise RuntimeError(
                f"Proxy exited with code "
                f"{proxy_return}"
            )


        # vLLM died
        vllm_return = vllm_process.poll()

        if vllm_return is not None:

            raise RuntimeError(
                f"vLLM exited with code "
                f"{vllm_return}"
            )


        time.sleep(5)


except KeyboardInterrupt:

    print("Application interrupted.")


finally:

    print()
    print("Stopping application processes...")


    if proxy_process.poll() is None:

        print("Stopping proxy...")

        proxy_process.terminate()

        try:

            proxy_process.wait(
                timeout=10
            )

        except subprocess.TimeoutExpired:

            proxy_process.kill()


    if vllm_process.poll() is None:

        print("Stopping vLLM...")

        vllm_process.terminate()

        try:

            vllm_process.wait(
                timeout=20
            )

        except subprocess.TimeoutExpired:

            vllm_process.kill()


    print("Application stopped.")