#!/usr/bin/env bash
set -e

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo ""
echo "Installed versions:"
python - <<'PY'
import sys
print("Python:", sys.version)

for pkg in ["torch", "transformers", "huggingface_hub", "vllm", "openai"]:
    try:
        mod = __import__(pkg)
        print(f"{pkg}: {getattr(mod, '__version__', 'unknown')}")
    except Exception as e:
        print(f"{pkg}: ERROR -> {e}")
PY
