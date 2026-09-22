import os
import sys
import time
import hashlib
import subprocess
from pathlib import Path

import requests


# =========================================================
# Configuration
# =========================================================

def _resolve_base_dir() -> Path:
    """Locate the vllm/ directory this file lives in.

    CAI can execute an Application's script as interpreter/notebook code
    (shown as "Cell In[N]" in the logs), where __file__ is not defined at
    all -- so we can't just trust Path(__file__) like a normal script.

    IMPORTANT: this only ever checks the exact path
    "<project root>/testing/model/vllm" under CDSW_PROJECT_DIR or cwd --
    never a wildcard/glob search. An earlier version used
    `base.glob("*/vllm")` as a fallback, which silently matched ANY
    sibling folder named "vllm" anywhere under the search root
    (including an old, abandoned copy of this app at
    /home/cdsw/tempo_llm_vllm_test/vllm/ that happened to still exist).
    Because glob() order isn't guaranteed, that stale folder sometimes
    won, and the Application spawned uvicorn with --app-dir pointing at
    old, unfixed proxy.py/app.py code -- while every other check (git
    log, file content, root endpoint) still looked correct because they
    were all run against the *intended* checkout, not the one actually
    running.
    """
    script_path = globals().get("__file__")
    if script_path:
        return Path(script_path).resolve().parent

    cwd = Path.cwd().resolve()
    project_dir_env = os.getenv("CDSW_PROJECT_DIR")
    candidates = ([Path(project_dir_env).resolve()] if project_dir_env else []) + [cwd]

    relative_path = Path("testing") / "model" / "vllm"

    for base in candidates:
        for candidate in (base / relative_path, base):
            if (candidate / "app.py").is_file() and (candidate / "proxy.py").is_file():
                return candidate

    raise RuntimeError(
        "Unable to locate the vllm/ application directory at "
        f"<project root>/{relative_path}. Set CDSW_PROJECT_DIR or start "
        "this Application from the project root."
    )


# This file lives at <repo>/testing/model/vllm/app.py; auto-detecting
# BASE_DIR means we never depend on ~/.local (which can be wiped whenever
# CAI rebuilds the container) or on a hardcoded project folder name.
BASE_DIR = _resolve_base_dir()

PROJECT_DIR = BASE_DIR.parent

VENV_DIR = PROJECT_DIR / ".venv-vllm-v2"

PYTHON_BIN = VENV_DIR / "bin" / "python"
VLLM_BIN = VENV_DIR / "bin" / "vllm"

REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
REQUIREMENTS_HASH_FILE = VENV_DIR / ".requirements_hash"


# =========================================================
# Model / ports / vLLM settings
# =========================================================

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
    os.getenv("VLLM_STARTUP_TIMEOUT", "900")
)

VLLM_MAX_MODEL_LEN = os.getenv("VLLM_MAX_MODEL_LEN", "4096")
VLLM_GPU_MEMORY_UTILIZATION = os.getenv("VLLM_GPU_MEMORY_UTILIZATION", "0.90")
VLLM_MAX_NUM_SEQS = os.getenv("VLLM_MAX_NUM_SEQS", "4")

# Qwen3 / Qwen3.5 default to "thinking" mode (long <think>...</think>
# reasoning block prepended to every response). Default this OFF for speed
# and to avoid leaking raw chain-of-thought; override via CAI Application
# env var VLLM_ENABLE_THINKING=true if a caller genuinely needs it.
VLLM_ENABLE_THINKING = os.getenv(
    "VLLM_ENABLE_THINKING", "false"
).strip().lower() in ("1", "true", "yes")


# =========================================================
# Validation
# =========================================================

if not APP_PORT:
    raise RuntimeError(
        "CDSW_READONLY_PORT / CDSW_APP_PORT not found."
    )

if not REQUIREMENTS_FILE.exists():
    raise RuntimeError(
        f"requirements.txt not found: {REQUIREMENTS_FILE}"
    )

if not Path(MODEL_DIR).exists():
    raise RuntimeError(
        f"Model directory not found: {MODEL_DIR}"
    )


os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))


# Disable FlashInfer sampler because CAI runtime
# does not provide nvcc / full CUDA Toolkit
os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"


print("=" * 60)
print("Tempo Scan LLM Application")
print("=" * 60)
print("Project directory  :", PROJECT_DIR)
print("Working directory  :", BASE_DIR)
print("Model directory    :", MODEL_DIR)
print("Virtual environment:", VENV_DIR)
print("Application port   :", APP_PORT)
print("vLLM internal port :", VLLM_PORT)
print("Thinking mode      :", VLLM_ENABLE_THINKING)
print("=" * 60)
print()


# =========================================================
# Ensure venv + dependencies
# =========================================================
# Everything vLLM needs (including the `vllm` CLI itself) is installed
# into a project-local venv instead of relying on the global/`~/.local`
# site-packages, which is not guaranteed to survive a CAI container
# rebuild -- that's what caused "ModuleNotFoundError: No module named
# 'vllm'" the first time this Application was recreated from scratch.

def calculate_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def venv_is_usable() -> bool:
    """PYTHON_BIN.exists() isn't enough: a venv can be left as a folder
    with no bin/python inside if a previous run was interrupted mid
    `python -m venv` (e.g. the container got killed/rebuilt while the
    Application was starting). Actually invoke the interpreter so a
    half-built venv gets rebuilt instead of failing every request.
    """
    if not PYTHON_BIN.exists():
        return False
    try:
        subprocess.check_call(
            [str(PYTHON_BIN), "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


if not venv_is_usable():

    if VENV_DIR.exists():

        print("=" * 60)
        print("REMOVING CORRUPT VIRTUAL ENVIRONMENT")
        print("=" * 60)
        print(VENV_DIR)

        import shutil
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    print("=" * 60)
    print("CREATING VIRTUAL ENVIRONMENT")
    print("=" * 60)

    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    print("Virtual environment created:", VENV_DIR)

else:

    print("Using existing virtual environment:", VENV_DIR)

print()


pip_env = os.environ.copy()
pip_env.pop("PIP_USER", None)
pip_env.pop("PYTHONUSERBASE", None)
pip_env["PIP_CONFIG_FILE"] = os.devnull
pip_env["PYTHONNOUSERSITE"] = "1"
pip_env["VIRTUAL_ENV"] = str(VENV_DIR)
pip_env["PATH"] = f"{VENV_DIR / 'bin'}:{pip_env.get('PATH', '')}"


print("=" * 60)
print("PREPARING PIP")
print("=" * 60)

subprocess.check_call(
    [str(PYTHON_BIN), "-m", "pip", "--isolated", "install",
     "--upgrade", "pip", "setuptools", "wheel"],
    env=pip_env
)


current_hash = calculate_file_hash(REQUIREMENTS_FILE)
installed_hash = (
    REQUIREMENTS_HASH_FILE.read_text().strip()
    if REQUIREMENTS_HASH_FILE.exists()
    else None
)

if current_hash != installed_hash:

    print()
    print("=" * 60)
    print("INSTALLING DEPENDENCIES")
    print("=" * 60)

    subprocess.check_call(
        [str(PYTHON_BIN), "-m", "pip", "--isolated", "install",
         "--no-cache-dir", "-r", str(REQUIREMENTS_FILE)],
        env=pip_env
    )

    REQUIREMENTS_HASH_FILE.write_text(current_hash)

else:

    print()
    print("Requirements unchanged, skipping dependency installation.")


if not VLLM_BIN.exists():
    raise RuntimeError(f"vLLM binary not found after install: {VLLM_BIN}")


# =========================================================
# Runtime env for vLLM / proxy subprocesses
# =========================================================

run_env = os.environ.copy()
run_env.pop("PIP_USER", None)
run_env.pop("PYTHONUSERBASE", None)
run_env["PYTHONNOUSERSITE"] = "1"
run_env["VIRTUAL_ENV"] = str(VENV_DIR)
run_env["PATH"] = f"{VENV_DIR / 'bin'}:{run_env.get('PATH', '')}"
run_env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"


# =========================================================
# Start vLLM
# =========================================================

vllm_cmd = [
    str(VLLM_BIN),
    "serve",
    MODEL_DIR,

    "--host",
    "127.0.0.1",

    "--port",
    str(VLLM_PORT),

    "--max-model-len",
    str(VLLM_MAX_MODEL_LEN),

    "--gpu-memory-utilization",
    str(VLLM_GPU_MEMORY_UTILIZATION),

    "--max-num-seqs",
    str(VLLM_MAX_NUM_SEQS),

    "--trust-remote-code",

    # Qwen3 / Qwen3.5 use the "qwen3" reasoning parser to split reasoning
    # out of message.content into a separate reasoning/reasoning_content
    # field. --default-chat-template-kwargs sets the server-wide default;
    # request-level chat_template_kwargs still take priority over this
    # default per vLLM's merge behavior.
    "--reasoning-parser",
    "qwen3",

    "--default-chat-template-kwargs",
    (
        '{"enable_thinking": true}'
        if VLLM_ENABLE_THINKING
        else '{"enable_thinking": false}'
    ),
]


print()
print("=" * 60)
print("STARTING vLLM")
print("=" * 60)
print(" ".join(vllm_cmd))
print()


vllm_process = subprocess.Popen(
    vllm_cmd,
    cwd=str(BASE_DIR),
    env=run_env
)


print("vLLM PID:", vllm_process.pid)
print()


# =========================================================
# Wait until vLLM OpenAI API is ready
# =========================================================

MODELS_URL = f"http://127.0.0.1:{VLLM_PORT}/v1/models"

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

    return_code = vllm_process.poll()

    if return_code is not None:
        raise RuntimeError(
            f"vLLM exited during startup with code {return_code}"
        )

    try:

        response = requests.get(MODELS_URL, timeout=10)

        print(f"[{elapsed}s] /v1/models -> HTTP {response.status_code}")

        if response.status_code == 200:

            print()
            print("=" * 60)
            print("vLLM READY")
            print("=" * 60)
            print(response.text[:2000])
            print()

            vllm_ready = True
            break

    except requests.RequestException:

        print(f"[{elapsed}s] vLLM still starting...")

    if elapsed >= MAX_WAIT_SECONDS:
        raise RuntimeError(
            f"vLLM OpenAI API did not become ready within {MAX_WAIT_SECONDS} seconds."
        )

    time.sleep(POLL_INTERVAL)


if not vllm_ready:
    raise RuntimeError("vLLM readiness validation failed.")


# =========================================================
# Start FastAPI proxy
# =========================================================

proxy_cmd = [
    str(PYTHON_BIN),
    "-m",
    "uvicorn",

    "proxy:app",

    "--host",
    "127.0.0.1",

    "--port",
    str(APP_PORT),

    "--app-dir",
    str(BASE_DIR),

    "--log-level",
    "info"
]


print("=" * 60)
print("STARTING CAI API PROXY")
print("=" * 60)
print(" ".join(proxy_cmd))
print()


proxy_process = subprocess.Popen(
    proxy_cmd,
    cwd=str(BASE_DIR),
    env=run_env
)


print("Proxy PID:", proxy_process.pid)
print()


# =========================================================
# Keep Application alive
# =========================================================

try:

    while True:

        proxy_return = proxy_process.poll()

        if proxy_return is not None:
            raise RuntimeError(f"Proxy exited with code {proxy_return}")

        vllm_return = vllm_process.poll()

        if vllm_return is not None:
            raise RuntimeError(f"vLLM exited with code {vllm_return}")

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
            proxy_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proxy_process.kill()

    if vllm_process.poll() is None:

        print("Stopping vLLM...")
        vllm_process.terminate()

        try:
            vllm_process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            vllm_process.kill()

    print("Application stopped.")
