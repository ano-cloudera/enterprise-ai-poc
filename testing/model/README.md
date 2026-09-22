# Tempo LLM + vLLM Test Bundle for Cloudera AI

Bundle ini digunakan untuk menjalankan dan melakukan testing model:

`nicosuter/Qwen3.8-27B-AWQ`

menggunakan **vLLM** pada Cloudera AI.

Bundle mendukung dua skenario:

1. Smoke test langsung di Cloudera AI Workbench Session
2. Deploy model sebagai Cloudera AI Application dengan OpenAI-compatible API

---

# Architecture

Untuk testing sederhana:

```text
Client / Python / curl
        ↓
vLLM
        ↓
Qwen3.8-27B-AWQ
        ↓
GPU
```

Untuk Cloudera AI Application:

```text
Client / Frontend / Gradio
        ↓
Cloudera AI Application URL
        ↓
FastAPI Proxy
CDSW_READONLY_PORT
        ↓
vLLM
127.0.0.1:9000
        ↓
Qwen3.8-27B-AWQ
        ↓
GPU
```

FastAPI digunakan sebagai proxy karena port application Cloudera AI dapat digunakan oleh internal application runtime.

vLLM tetap berjalan sebagai internal service pada:

```text
127.0.0.1:9000
```

Sedangkan FastAPI expose endpoint melalui port Cloudera AI Application.

---

# 1. Recommended Environment

Gunakan Cloudera AI Workbench / Cloudera AI Application dengan GPU.

Environment yang sudah berhasil digunakan:

```text
GPU       : NVIDIA L40S
VRAM      : ~46 GB usable
Python    : 3.10
vLLM      : 0.29.0
Model     : Qwen3.8-27B-AWQ
```

Model:

```text
nicosuter/Qwen3.8-27B-AWQ
```

Local model location:

```text
/home/cdsw/models/Qwen3.8-27B-AWQ
```

---

# 2. GPU Requirement

Model 27B AWQ membutuhkan GPU memory yang cukup besar.

Recommended:

```text
NVIDIA L40S 48 GB
A100 40/80 GB
H100 80 GB
```

Untuk GPU 24 GB seperti NVIDIA A10G atau L4:

- model sangat mepet
- berpotensi CUDA OOM
- gunakan hanya untuk smoke test
- turunkan context length
- gunakan single sequence

Contoh konfigurasi konservatif:

```text
MAX_MODEL_LEN=1024
MAX_NUM_SEQS=1
GPU_MEMORY_UTILIZATION=0.95
```

Untuk L40S, konfigurasi yang sudah berhasil:

```text
MAX_MODEL_LEN=4096
MAX_NUM_SEQS=4
GPU_MEMORY_UTILIZATION=0.90
```

---

# 3. Extract Bundle

Upload ZIP ke Cloudera AI Workbench lalu extract:

```bash
unzip tempo_llm_vllm_test.zip
cd tempo_llm_vllm_test
```

Folder awal:

```text
tempo_llm_vllm_test/
├── README.md
├── requirements.txt
├── 01_install.sh
├── 02_download_model.py
├── 03_validate_model.py
├── 04_start_vllm.sh
├── 05_test_health.py
├── 06_test_chat.py
├── qwen_vllm_thinking_test.ipynb
├── vllm/
└── gradio/
```

---

# 4. Check GPU

Run:

```bash
nvidia-smi
```

Pastikan GPU terlihat.

Contoh:

```text
NVIDIA L40S
```

Perlu diperhatikan:

```bash
nvcc --version
```

bisa saja menghasilkan:

```text
nvcc: command not found
```

Ini tidak berarti GPU tidak dapat digunakan.

vLLM tetap dapat menggunakan NVIDIA CUDA runtime selama driver dan PyTorch CUDA tersedia.

---

# 5. Install Dependencies

Run:

```bash
bash 01_install.sh
```

atau:

```bash
pip install -r requirements.txt
```

Contoh dependency:

```text
vllm==0.29.0
huggingface_hub
requests
openai
```

---

# 6. Download Model

Default location:

```text
/home/cdsw/models/Qwen3.8-27B-AWQ
```

Run:

```bash
python 02_download_model.py
```

Custom path:

```bash
MODEL_DIR=/home/cdsw/models/qwen-test \
python 02_download_model.py
```

Jika Hugging Face membutuhkan token:

```bash
export HF_TOKEN="hf_xxxxx"
python 02_download_model.py
```

---

# 7. Validate Model Files

Run:

```bash
python 03_validate_model.py
```

Pastikan model files sudah tersedia sebelum menjalankan vLLM.

Check manual:

```bash
ls -lah /home/cdsw/models/Qwen3.8-27B-AWQ
```

---

# 8. Start vLLM in Workbench Session

Untuk smoke test:

```bash
bash 04_start_vllm.sh
```

Recommended configuration untuk L40S:

```text
Host                   : 127.0.0.1 / 0.0.0.0
Port                   : 9000
Max model length       : 4096
GPU memory utilization : 0.90
Max sequences          : 4
```

Contoh:

```bash
PORT=9000 \
MAX_MODEL_LEN=4096 \
GPU_MEMORY_UTILIZATION=0.90 \
MAX_NUM_SEQS=4 \
bash 04_start_vllm.sh
```

---

# 9. FlashInfer / nvcc Workaround

Pada environment Cloudera AI yang digunakan, NVIDIA driver tersedia tetapi full CUDA Toolkit / `nvcc` tidak tersedia.

FlashInfer JIT dapat menghasilkan error seperti:

```text
RuntimeError:
Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist
```

Gunakan:

```bash
export VLLM_USE_FLASHINFER_SAMPLER=0
```

Sebelum menjalankan vLLM.

Contoh:

```bash
export VLLM_USE_FLASHINFER_SAMPLER=0

vllm serve /home/cdsw/models/Qwen3.8-27B-AWQ \
  --host 127.0.0.1 \
  --port 9000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 4 \
  --trust-remote-code
```

Setting ini tidak mematikan GPU inference.

Setting hanya menonaktifkan FlashInfer sampler yang membutuhkan CUDA JIT compilation pada environment ini.

---

# 10. Test vLLM

Models endpoint:

```bash
curl http://127.0.0.1:9000/v1/models
```

Health:

```bash
curl http://127.0.0.1:9000/health
```

Chat:

```bash
curl http://127.0.0.1:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/home/cdsw/models/Qwen3.8-27B-AWQ",
    "messages": [
      {
        "role": "user",
        "content": "Halo, jelaskan siapa kamu secara singkat."
      }
    ],
    "temperature": 0.2,
    "max_tokens": 256
  }'
```

Atau:

```bash
python 05_test_health.py
```

dan:

```bash
python 06_test_chat.py
```

Custom prompt:

```bash
PROMPT="Jelaskan fungsi semantic layer secara singkat." \
python 06_test_chat.py
```

---

# 11. Deploy as Cloudera AI Application

Setelah smoke test berhasil, model dapat dibungkus sebagai Cloudera AI Application.

Gunakan folder:

```text
tempo_llm_vllm_test/vllm/
```

Struktur:

```text
vllm/
├── app.py
├── proxy.py
└── requirements.txt
```

---

# 12. CAI Application Requirements

File:

```text
vllm/requirements.txt
```

Recommended:

```text
vllm==0.29.0
fastapi
uvicorn
requests>=2.31
huggingface_hub>=0.34
openai>=1.40
```

---

# 13. CAI Application Architecture

CAI Application menjalankan dua process:

```text
app.py
   │
   ├── Start vLLM
   │      ↓
   │   127.0.0.1:9000
   │
   └── Start FastAPI Proxy
          ↓
      CDSW_READONLY_PORT
```

External client hanya mengakses:

```text
Cloudera AI Application URL
```

Client tidak langsung mengakses port internal 9000.

---

# 14. Important Port Configuration

Jangan menggunakan port `8000` sebagai asumsi default untuk CAI Application.

Pada environment Cloudera AI, beberapa port dapat sudah digunakan oleh internal services.

Gunakan:

```python
APP_PORT = (
    os.getenv("CDSW_READONLY_PORT")
    or os.getenv("CDSW_APP_PORT")
)
```

Untuk vLLM gunakan port internal terpisah:

```text
9000
```

Contoh:

```text
External Application
CDSW_READONLY_PORT

Internal vLLM
127.0.0.1:9000
```

---

# 15. app.py Responsibilities

`app.py` bertanggung jawab untuk:

1. set working directory
2. set model location
3. set internal vLLM port
4. disable FlashInfer sampler
5. start vLLM subprocess
6. wait sampai model benar-benar ready
7. start FastAPI proxy
8. monitor kedua process

Environment:

```python
MODEL_DIR = "/home/cdsw/models/Qwen3.8-27B-AWQ"

VLLM_PORT = "9000"

APP_PORT = (
    os.getenv("CDSW_READONLY_PORT")
    or os.getenv("CDSW_APP_PORT")
)

os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
```

vLLM command:

```bash
vllm serve /home/cdsw/models/Qwen3.8-27B-AWQ \
  --host 127.0.0.1 \
  --port 9000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 4 \
  --trust-remote-code
```

---

# 16. Application Startup / Readiness

Model 27B membutuhkan waktu untuk:

```text
load weights
initialize CUDA
allocate KV cache
warmup
initialize API server
```

Jangan hanya menggunakan:

```python
time.sleep(5)
```

Gunakan readiness check ke:

```text
http://127.0.0.1:9000/v1/models
```

Recommended timeout:

```text
900 seconds
```

Contoh logic:

```python
while True:
    try:
        response = requests.get(
            "http://127.0.0.1:9000/v1/models",
            timeout=10
        )

        if response.status_code == 200:
            break

    except requests.RequestException:
        pass

    time.sleep(5)
```

Jika log vLLM menunjukkan:

```text
Application startup complete
```

berarti API server sudah hampir / sudah siap.

---

# 17. FastAPI Proxy

`proxy.py` menyediakan endpoint:

```text
GET  /
GET  /health
GET  /v1/models
POST /v1/chat/completions
POST /v1/completions
```

Root:

```text
/
```

Expected response:

```json
{
  "service": "Tempo Scan LLM",
  "status": "running",
  "backend": "vLLM"
}
```

---

# 18. Create Cloudera AI Application

Di Cloudera AI Workbench:

1. Buka project yang berisi source code.
2. Pilih **Applications**.
3. Create new Application.
4. Gunakan runtime Python 3.10 yang compatible.
5. Attach GPU.
6. Recommended GPU untuk model ini:

```text
NVIDIA L40S
```

7. Application script:

```text
vllm/app.py
```

8. Pastikan dependency pada:

```text
vllm/requirements.txt
```

sudah terinstall pada runtime/application environment.

9. Start / deploy Application.

---

# 19. Application Startup

Saat Application start, flow-nya:

```text
CAI Application
      ↓
app.py
      ↓
Start vLLM
      ↓
Load Qwen
      ↓
Wait /v1/models
      ↓
Start FastAPI
      ↓
Application Ready
```

Loading pertama model dapat membutuhkan beberapa menit.

Monitor application logs sampai muncul:

```text
vLLM READY
```

dan kemudian:

```text
Uvicorn running
```

---

# 20. Test CAI Application

Setelah Application running, buka application URL.

Root:

```text
https://<application-url>/
```

Expected:

```json
{
  "service": "Tempo Scan LLM",
  "status": "running",
  "backend": "vLLM"
}
```

---

# 21. FastAPI Documentation

Buka:

```text
https://<application-url>/docs
```

FastAPI Swagger UI harus terlihat.

---

# 22. Test Models Endpoint

```bash
curl https://<application-url>/v1/models
```

Expected response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "/home/cdsw/models/Qwen3.8-27B-AWQ"
    }
  ]
}
```

---

# 23. Test Chat Completion

```bash
curl https://<application-url>/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/home/cdsw/models/Qwen3.8-27B-AWQ",
    "messages": [
      {
        "role": "user",
        "content": "Jelaskan fungsi semantic layer secara singkat."
      }
    ],
    "temperature": 0.3,
    "max_tokens": 512
  }'
```

---

# 24. Test Using OpenAI Client

Karena API vLLM OpenAI-compatible:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<application-url>/v1",
    api_key="dummy"
)

response = client.chat.completions.create(
    model="/home/cdsw/models/Qwen3.8-27B-AWQ",
    messages=[
        {
            "role": "user",
            "content": "Apa fungsi semantic layer?"
        }
    ],
    temperature=0.3,
    max_tokens=512
)

print(response.choices[0].message.content)
```

---

# 25. Thinking / Reasoning Mode

Qwen dapat menggunakan thinking/reasoning mode.

Contoh payload:

```json
{
  "model": "/home/cdsw/models/Qwen3.8-27B-AWQ",
  "messages": [
    {
      "role": "user",
      "content": "Analisa penyebab sales turun."
    }
  ],
  "temperature": 0.3,
  "max_tokens": 2048,
  "chat_template_kwargs": {
    "enable_thinking": true,
    "preserve_thinking": false
  }
}
```

Untuk aplikasi management / production demo, recommended default:

```text
enable_thinking = false
```

Aktifkan reasoning hanya untuk analysis yang membutuhkan reasoning lebih kompleks.

Internal chain-of-thought tidak boleh ditampilkan ke end user.

---

# 26. Application Authentication

Untuk testing internal PoC, Application dapat dibuat accessible sesuai policy environment Cloudera.

Jika frontend / backend lain perlu melakukan server-to-server call ke Qwen Application, pastikan authentication mode sesuai.

Pada PoC ini, Qwen Application pernah dibuat tanpa authentication tambahan agar Gradio backend dapat mengakses endpoint secara langsung.

Untuk production, authentication dan authorization harus ditambahkan sesuai security policy customer.

---

# 27. Gradio Integration

Gradio Application dapat menggunakan Qwen CAI Application sebagai endpoint:

```text
Gradio
   ↓
https://<qwen-application-url>
   ↓
/v1/chat/completions
```

Test:

```text
GET /v1/models
```

Jika berhasil, UI dapat menampilkan:

```text
Connected
```

---

# 28. Troubleshooting

## CUDA Out of Memory

Untuk L40S:

```bash
MAX_MODEL_LEN=2048 \
GPU_MEMORY_UTILIZATION=0.85 \
MAX_NUM_SEQS=2 \
bash 04_start_vllm.sh
```

Untuk GPU 24 GB:

```text
MAX_MODEL_LEN=1024
MAX_NUM_SEQS=1
GPU_MEMORY_UTILIZATION=0.90-0.95
```

Jika masih OOM, model terlalu besar untuk GPU tersebut.

---

## FlashInfer / nvcc Error

Error:

```text
Could not find nvcc
```

Set:

```bash
export VLLM_USE_FLASHINFER_SAMPLER=0
```

---

## Port Already Used

Jika port session digunakan:

```bash
PORT=9000 bash 04_start_vllm.sh
```

Untuk CAI Application jangan hardcode external application port.

Gunakan:

```python
os.getenv("CDSW_READONLY_PORT")
```

---

## Port Returns Cloudera HTML

Jika request seperti:

```bash
curl localhost:8000
```

menghasilkan HTML Cloudera AI Terminal, berarti port tersebut digunakan oleh internal Cloudera service.

Jangan gunakan port tersebut.

Gunakan port internal lain untuk vLLM, contoh:

```text
9000
```

---

## /v1/models Internal Server Error

Check terlebih dahulu internal vLLM:

```bash
curl http://127.0.0.1:9000/v1/models
```

Jika internal endpoint berhasil tetapi public endpoint gagal, problem kemungkinan berada pada FastAPI proxy.

---

## Application Timeout

Model 27B membutuhkan startup cukup lama.

Gunakan readiness timeout:

```text
900 seconds
```

Jangan menganggap model gagal hanya karena startup lebih dari 1–2 menit.

---

## Model tidak ditemukan

Check:

```bash
ls -lah /home/cdsw/models/Qwen3.8-27B-AWQ
```

Pastikan Application mempunyai access ke path model tersebut.

---

# 29. Folder Structure

Final structure:

```text
tempo_llm_vllm_test/
│
├── README.md
├── requirements.txt
│
├── 01_install.sh
├── 02_download_model.py
├── 03_validate_model.py
├── 04_start_vllm.sh
├── 05_test_health.py
├── 06_test_chat.py
│
├── qwen_vllm_thinking_test.ipynb
│
├── vllm/
│   ├── app.py
│   ├── proxy.py
│   └── requirements.txt
│
└── gradio/
    ├── app.py
    └── requirements.txt
```

---

# 30. Recommended Workflow

Recommended flow untuk deployment:

```text
1. Start GPU Workbench Session
        ↓
2. Check nvidia-smi
        ↓
3. Install dependencies
        ↓
4. Download model
        ↓
5. Validate model
        ↓
6. Run vLLM smoke test
        ↓
7. Test /v1/models
        ↓
8. Test /v1/chat/completions
        ↓
9. Create CAI Application
        ↓
10. Start vLLM internal service
        ↓
11. Start FastAPI proxy
        ↓
12. Test public API
        ↓
13. Connect Gradio / Backend / LangGraph
```

---

# Current Status

Current implementation has successfully validated:

- NVIDIA L40S GPU
- Qwen3.8-27B-AWQ model download
- vLLM 0.29.0
- GPU inference
- OpenAI-compatible API
- FastAPI proxy
- Cloudera AI Application
- public model endpoint
- Bahasa Indonesia / English
- reasoning mode
- Gradio integration

This bundle can now be used as the model-serving foundation for the Tempo Scan Commercial Intelligence PoC.

Next application layer:

```text
Frontend
   ↓
FastAPI Backend
   ↓
LangGraph
   ↓
Semantic Layer
   ↓
Impala/CDW
   ↓
Qwen vLLM Endpoint
```