import os
from pathlib import Path

MODEL_DIR = Path(
    os.getenv("MODEL_DIR", "/home/cdsw/models/Qwen3.8-27B-AWQ")
).expanduser()

required_candidates = [
    "config.json",
    "tokenizer_config.json",
]

print(f"Checking: {MODEL_DIR}")

if not MODEL_DIR.exists():
    raise SystemExit(f"ERROR: model directory not found: {MODEL_DIR}")

missing = [name for name in required_candidates if not (MODEL_DIR / name).exists()]

safetensors = list(MODEL_DIR.glob("*.safetensors"))
index_files = list(MODEL_DIR.glob("*.safetensors.index.json"))

print(f"Files            : {sum(1 for _ in MODEL_DIR.rglob('*') if _.is_file())}")
print(f"Safetensors      : {len(safetensors)}")
print(f"Safetensor index : {len(index_files)}")

if missing:
    print("Missing expected files:", missing)
    raise SystemExit(1)

if not safetensors and not index_files:
    print("ERROR: no safetensors weights found")
    raise SystemExit(1)

print("Validation OK.")
