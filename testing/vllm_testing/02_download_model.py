import os
from pathlib import Path
from huggingface_hub import snapshot_download

MODEL_ID = os.getenv("MODEL_ID", "nicosuter/Qwen3.8-27B-AWQ")
MODEL_DIR = Path(
    os.getenv("MODEL_DIR", "/home/cdsw/models/Qwen3.8-27B-AWQ")
).expanduser()

HF_TOKEN = os.getenv("HF_TOKEN")

MODEL_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("Downloading Hugging Face model")
print(f"MODEL_ID : {MODEL_ID}")
print(f"MODEL_DIR: {MODEL_DIR}")
print("=" * 80)

path = snapshot_download(
    repo_id=MODEL_ID,
    local_dir=str(MODEL_DIR),
    token=HF_TOKEN,
)

print("")
print("Download complete")
print(f"Local model path: {path}")
