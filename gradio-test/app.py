import os
import re
import time
import gradio as gr
import requests

APP_PORT = os.getenv("CDSW_READONLY_PORT") or os.getenv("CDSW_APP_PORT")
if not APP_PORT:
    raise RuntimeError("CDSW_READONLY_PORT / CDSW_APP_PORT not found.")

DEFAULT_VLLM_URL = os.getenv(
    "VLLM_BASE_URL",
    "https://qwen-model.ml-6e4750a0-e43.ano03-cd.a465-9q4k.cloudera.site",
)
DEFAULT_MODEL = os.getenv("MODEL_NAME", "/home/cdsw/models/Qwen3.8-27B-AWQ")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

DEFAULT_SYSTEM_PROMPT = """You are Tempo Scan Commercial Intelligence Assistant.
Your primary users are management and business leaders.
Answer in the same language as the user.
Prioritize management-level insights.
Be concise, clear, and actionable.
Do not invent unavailable facts or numbers.
For business analysis use: Executive Summary, Key Drivers, Recommended Actions.
Do not expose internal chain-of-thought."""

def normalize_endpoint(endpoint):
    endpoint = endpoint.strip().rstrip("/")
    return endpoint[:-3] if endpoint.endswith("/v1") else endpoint

def build_headers():
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"
    return headers

def clean_model_output(content):
    if not content:
        return ""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    if "</think>" in content.lower():
        pos = content.lower().rfind("</think>")
        content = content[pos + len("</think>"):]
    return content.strip()

def check_endpoint(endpoint):
    try:
        start = time.time()
        r = requests.get(f"{normalize_endpoint(endpoint)}/v1/models", headers=build_headers(), timeout=30)
        if r.status_code != 200:
            return f"HTTP {r.status_code}", r.text[:500]
        models = r.json().get("data", [])
        model = models[0].get("id", "Unknown") if models else "Unknown"
        return f"Connected · {time.time()-start:.2f}s", model
    except Exception as e:
        return "Connection Failed", str(e)[:500]

def send_message(message, history, endpoint, system_prompt, thinking, temperature, max_tokens):
    history = history or []
    if not message or not message.strip():
        return history, "", "Ready"

    messages = [{"role": "system", "content": system_prompt.strip()}]
    for item in history:
        if isinstance(item, dict) and item.get("role") in ["user", "assistant"] and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "chat_template_kwargs": {
            "enable_thinking": bool(thinking),
            "preserve_thinking": False,
        },
    }

    new_history = history + [{"role": "user", "content": message}]
    start = time.time()

    try:
        r = requests.post(
            f"{normalize_endpoint(endpoint)}/v1/chat/completions",
            headers=build_headers(), json=payload, timeout=300
        )
        latency = time.time() - start
        if r.status_code != 200:
            answer = f"⚠️ vLLM HTTP {r.status_code}\n\n```text\n{r.text[:2000]}\n```"
            new_history.append({"role": "assistant", "content": answer})
            return new_history, "", f"HTTP {r.status_code} · {latency:.2f}s"

        data = r.json()
        raw_answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        answer = clean_model_output(raw_answer) or "Model returned an empty response."
        new_history.append({"role": "assistant", "content": answer})
        usage = data.get("usage", {}) or {}
        mode = "Reasoning" if thinking else "Direct"
        status = f"Ready · {latency:.2f}s · {mode} · Input {usage.get('prompt_tokens','?')} · Output {usage.get('completion_tokens','?')}"
        return new_history, "", status
    except Exception as e:
        new_history.append({"role": "assistant", "content": f"Connection error:\n\n{str(e)}"})
        return new_history, "", "Connection Error"

def clear_chat():
    return [], "", "Ready"

CSS = """
:root { color-scheme: light !important; }
html, body, .gradio-container { background:#f5f7fa !important; color:#111827 !important; }
.gradio-container { width:100% !important; max-width:none !important; margin:0 !important; padding:18px 22px !important; }
#tempo-header { background:#fff; border:1px solid #e4e7ec; border-radius:14px; padding:18px 24px; margin-bottom:16px; }
.tempo-title { font-size:24px; font-weight:800; color:#11285a !important; }
.tempo-mark { color:#ed1b2f !important; margin-right:10px; }
.tempo-subtitle { color:#667085 !important; margin-top:4px; font-size:14px; }
#workspace-row { display:flex !important; flex-direction:row !important; flex-wrap:nowrap !important; width:100% !important; gap:16px !important; }
#left-panel { flex:0 0 320px !important; width:320px !important; min-width:320px !important; max-width:320px !important; background:#fff !important; border:1px solid #e4e7ec !important; border-radius:14px !important; padding:18px !important; }
#chat-panel { flex:1 1 auto !important; min-width:0 !important; background:#fff !important; border:1px solid #e4e7ec !important; border-radius:14px !important; padding:20px !important; }
#left-panel h1,#left-panel h2,#left-panel h3,#chat-panel h1,#chat-panel h2,#chat-panel h3,.gradio-container .prose h1,.gradio-container .prose h2,.gradio-container .prose h3,.gradio-container .prose h4 { color:#111827 !important; opacity:1 !important; }
#chat-panel .prose p { color:#475467 !important; }
#main-chat { width:100% !important; background:#0f172a !important; border:1px solid #1e293b !important; border-radius:12px !important; }
#main-chat,#main-chat * { color:#fff !important; -webkit-text-fill-color:#fff !important; opacity:1 !important; }
#thinking-box { background:#1e293b !important; border-radius:8px !important; padding:10px 12px !important; }
#thinking-box label,#thinking-box label span,#thinking-box span,#thinking-box p { color:#fff !important; -webkit-text-fill-color:#fff !important; opacity:1 !important; }
#thinking-box input[type='checkbox'] { cursor:pointer !important; pointer-events:auto !important; accent-color:#ed1b2f !important; }
textarea,input,select { background:#fff !important; color:#111827 !important; border-color:#d0d5dd !important; }
#message-row { display:flex !important; flex-wrap:nowrap !important; gap:10px !important; }
#message-input { flex:1 !important; min-width:0 !important; }
#send-button { flex:0 0 100px !important; background:#ed1b2f !important; color:#fff !important; border:none !important; font-weight:700 !important; }
.quick-button { background:#fff !important; color:#11285a !important; border:1px solid #d0d5dd !important; font-weight:600 !important; }
#runtime-status,#runtime-status * { color:#667085 !important; font-size:12px !important; }
footer { display:none !important; }
@media (max-width:780px) { #workspace-row { flex-direction:column !important; } #left-panel { width:100% !important; min-width:0 !important; max-width:none !important; flex:1 1 auto !important; } }
"""

theme = gr.themes.Soft(primary_hue="red", secondary_hue="slate", neutral_hue="slate")

with gr.Blocks(theme=theme, css=CSS, title="Tempo Scan Commercial Intelligence", fill_width=True) as demo:
    gr.HTML("""<div id='tempo-header'><div class='tempo-title'><span class='tempo-mark'>TT</span>TEMPO SCAN</div><div class='tempo-subtitle'>Commercial Intelligence Assistant · Powered by Cloudera AI</div></div>""")

    with gr.Row(elem_id="workspace-row"):
        with gr.Column(elem_id="left-panel"):
            gr.Markdown("### Settings")
            endpoint = gr.Textbox(label="Model Endpoint", value=DEFAULT_VLLM_URL, lines=2)
            test_connection = gr.Button("Test Connection")
            connection_status = gr.Textbox(label="Connection", value="Not checked", interactive=False)
            model_info = gr.Textbox(label="Model", value=DEFAULT_MODEL, interactive=False, lines=2)
            with gr.Group(elem_id="thinking-box"):
                thinking = gr.Checkbox(label="Thinking / Reasoning", value=False, interactive=True)
            temperature = gr.Slider(0, 1, value=0.3, step=0.1, label="Temperature")
            max_tokens = gr.Slider(128, 4096, value=2048, step=128, label="Max Tokens")
            with gr.Accordion("System Prompt", open=False):
                system_prompt = gr.Textbox(value=DEFAULT_SYSTEM_PROMPT, lines=12, show_label=False)
            clear_button = gr.Button("Clear Conversation")

        with gr.Column(elem_id="chat-panel"):
            gr.Markdown("## Chat Conversation\n\nAsk questions in **Bahasa Indonesia or English**.")
            chatbot = gr.Chatbot(type="messages", height=520, elem_id="main-chat", show_label=False)
            status = gr.Markdown("Ready", elem_id="runtime-status")
            with gr.Row(elem_id="message-row"):
                message = gr.Textbox(placeholder="Ask a question about your business data...", show_label=False, lines=2, elem_id="message-input")
                send_button = gr.Button("Send", elem_id="send-button")
            gr.Markdown("#### Suggested questions")
            with gr.Row():
                q1 = gr.Button("Why did sales decline?", elem_classes="quick-button")
                q2 = gr.Button("Top performing products", elem_classes="quick-button")
            with gr.Row():
                q3 = gr.Button("Analyze inventory risk", elem_classes="quick-button")
                q4 = gr.Button("Forecast next month", elem_classes="quick-button")

    chat_inputs = [message, chatbot, endpoint, system_prompt, thinking, temperature, max_tokens]
    chat_outputs = [chatbot, message, status]

    send_button.click(fn=send_message, inputs=chat_inputs, outputs=chat_outputs)
    message.submit(fn=send_message, inputs=chat_inputs, outputs=chat_outputs)
    test_connection.click(fn=check_endpoint, inputs=endpoint, outputs=[connection_status, model_info])
    clear_button.click(fn=clear_chat, outputs=[chatbot, message, status])
    q1.click(lambda: "Kenapa sales Jawa Barat turun bulan ini? Jelaskan key driver dan recommended action.", outputs=message)
    q2.click(lambda: "Produk mana yang memiliki performa terbaik dan terburuk bulan ini?", outputs=message)
    q3.click(lambda: "Analisis risiko inventory yang perlu diperhatikan management.", outputs=message)
    q4.click(lambda: "Apa faktor utama yang perlu dipertimbangkan untuk forecast sales bulan depan?", outputs=message)

demo.launch(server_name="127.0.0.1", server_port=int(APP_PORT), share=False, show_error=True)
