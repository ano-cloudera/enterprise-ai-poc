import os
import sys
import re
import time
import subprocess
import importlib.util


# =========================================================
# Dependencies
# =========================================================

def ensure_package(module_name, pip_name):
    if importlib.util.find_spec(module_name) is None:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            pip_name
        ])


ensure_package("gradio", "gradio==5.49.1")
ensure_package("requests", "requests==2.32.5")

import gradio as gr
import requests


# =========================================================
# Configuration
# =========================================================

APP_PORT = (
    os.getenv("CDSW_READONLY_PORT")
    or os.getenv("CDSW_APP_PORT")
)

if not APP_PORT:
    raise RuntimeError(
        "CDSW_READONLY_PORT / CDSW_APP_PORT not found."
    )


DEFAULT_VLLM_URL = os.getenv(
    "VLLM_BASE_URL",
    "https://qwen-model.ml-6e4750a0-e43.ano03-cd.a465-9q4k.cloudera.site"
)


DEFAULT_MODEL = os.getenv(
    "MODEL_NAME",
    "/home/cdsw/models/Qwen3.8-27B-AWQ"
)


VLLM_API_KEY = os.getenv(
    "VLLM_API_KEY",
    ""
)


DEFAULT_SYSTEM_PROMPT = """
You are Tempo Scan Commercial Intelligence Assistant.

Your primary users are management and business leaders.

Your role is to help users analyze and understand business
performance using trusted company data such as:

- Sales
- Product
- Outlet
- Customer
- Inventory
- Region
- Channel
- Market and external signals

Response guidelines:

1. Answer using the same language as the user.
2. Prioritize business impact and management-level insights.
3. Be concise, clear, and actionable.
4. Do not invent facts or numerical values that are not provided.
5. Clearly state assumptions when information is incomplete.
6. When analyzing a business issue, structure the answer into:
   - Executive Summary
   - Key Drivers
   - Recommended Actions
7. When data is not available, explain what data should be checked.
8. Avoid exposing internal reasoning or chain-of-thought.
""".strip()


# =========================================================
# API helpers
# =========================================================

def normalize_endpoint(endpoint):
    endpoint = endpoint.strip().rstrip("/")

    if endpoint.endswith("/v1"):
        endpoint = endpoint[:-3]

    return endpoint


def build_headers():
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    return headers


def clean_model_output(content):
    if not content:
        return ""

    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE
    )

    if "</think>" in content.lower():
        lower_content = content.lower()
        position = lower_content.rfind("</think>")

        content = content[
            position + len("</think>"):
        ]

    return content.strip()


# =========================================================
# Endpoint test
# =========================================================

def check_endpoint(endpoint):
    base_url = normalize_endpoint(endpoint)
    url = f"{base_url}/v1/models"

    try:
        start_time = time.time()

        response = requests.get(
            url,
            headers=build_headers(),
            timeout=30
        )

        latency = time.time() - start_time

        content_type = response.headers.get(
            "content-type",
            ""
        )

        if "text/html" in content_type:
            return (
                "Authentication / Proxy Issue",
                "Endpoint returned HTML instead of JSON"
            )

        if response.status_code != 200:
            return (
                f"HTTP {response.status_code}",
                response.text[:500]
            )

        data = response.json()
        models = data.get("data", [])

        if models:
            model_name = models[0].get("id", "Unknown")
        else:
            model_name = "Unknown"

        return (
            f"Connected · {latency:.2f}s",
            model_name
        )

    except Exception as e:
        return (
            "Connection Failed",
            str(e)[:500]
        )


# =========================================================
# Chat
# =========================================================

def send_message(
    message,
    history,
    endpoint,
    system_prompt,
    thinking,
    temperature,
    max_tokens
):
    history = history or []

    if not message or not message.strip():
        return history, "", "Ready"

    base_url = normalize_endpoint(endpoint)

    api_url = (
        f"{base_url}/v1/chat/completions"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt.strip()
        }
    ]

    for item in history:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in ["user", "assistant"]:
            continue

        if not content:
            continue

        messages.append({
            "role": role,
            "content": content
        })

    messages.append({
        "role": "user",
        "content": message
    })

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),

        "chat_template_kwargs": {
            "enable_thinking": bool(thinking),
            "preserve_thinking": False
        }
    }

    new_history = history + [
        {
            "role": "user",
            "content": message
        }
    ]

    start_time = time.time()

    try:
        response = requests.post(
            api_url,
            headers=build_headers(),
            json=payload,
            timeout=300
        )

        latency = time.time() - start_time

        content_type = response.headers.get(
            "content-type",
            ""
        )

        if "text/html" in content_type:
            answer = (
                "⚠️ Model endpoint returned HTML instead of JSON. "
                "Check Cloudera AI Application authentication/proxy."
            )

            new_history.append({
                "role": "assistant",
                "content": answer
            })

            return (
                new_history,
                "",
                f"Authentication / Proxy Issue · {latency:.2f}s"
            )

        if response.status_code != 200:
            answer = (
                f"⚠️ vLLM HTTP {response.status_code}\n\n"
                f"```text\n"
                f"{response.text[:2000]}"
                f"\n```"
            )

            new_history.append({
                "role": "assistant",
                "content": answer
            })

            return (
                new_history,
                "",
                f"HTTP {response.status_code} · {latency:.2f}s"
            )

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:
            answer = "Model returned no choices."
        else:
            raw_answer = (
                choices[0]
                .get("message", {})
                .get("content", "")
            )

            answer = clean_model_output(
                raw_answer
            )

            if not answer:
                answer = "Model returned an empty response."

        new_history.append({
            "role": "assistant",
            "content": answer
        })

        usage = data.get("usage", {}) or {}

        prompt_tokens = usage.get(
            "prompt_tokens",
            "?"
        )

        completion_tokens = usage.get(
            "completion_tokens",
            "?"
        )

        mode = (
            "Reasoning"
            if thinking
            else "Direct"
        )

        status = (
            f"Ready · {latency:.2f}s · "
            f"{mode} · "
            f"Input {prompt_tokens} · "
            f"Output {completion_tokens}"
        )

        return (
            new_history,
            "",
            status
        )

    except requests.Timeout:
        new_history.append({
            "role": "assistant",
            "content": (
                "Request timeout. "
                "The model may still be processing."
            )
        })

        return (
            new_history,
            "",
            "Request Timeout"
        )

    except Exception as e:
        new_history.append({
            "role": "assistant",
            "content": (
                "Connection error:\n\n"
                f"{str(e)}"
            )
        })

        return (
            new_history,
            "",
            "Connection Error"
        )


def clear_chat():
    return [], "", "Ready"


# =========================================================
# Theme
# =========================================================

theme = gr.themes.Soft(
    primary_hue="red",
    secondary_hue="slate",
    neutral_hue="slate"
)


# =========================================================
# CSS
# =========================================================

CSS = """

:root {
    color-scheme: light !important;
}

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    background: #f5f7fa !important;
    color: #111827 !important;
}

.gradio-container {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 18px 22px !important;
    background: #f5f7fa !important;
    color: #111827 !important;
}


/* ======================================================
   HEADER
   ====================================================== */

#tempo-header {
    width: 100%;
    box-sizing: border-box;
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 14px;
    padding: 18px 24px;
    margin-bottom: 16px;
}

.tempo-title {
    font-size: 24px;
    font-weight: 800;
    color: #11285a !important;
}

.tempo-mark {
    color: #ed1b2f !important;
    margin-right: 10px;
}

.tempo-subtitle {
    color: #667085 !important;
    margin-top: 4px;
    font-size: 14px;
}


/* ======================================================
   WORKSPACE
   ====================================================== */

#workspace-row {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    width: 100% !important;
    gap: 16px !important;
    align-items: stretch !important;
}


/* ======================================================
   LEFT PANEL
   ====================================================== */

#left-panel {
    flex: 0 0 320px !important;
    width: 320px !important;
    min-width: 320px !important;
    max-width: 320px !important;
    background: #ffffff !important;
    border: 1px solid #e4e7ec !important;
    border-radius: 14px !important;
    padding: 18px !important;
    box-sizing: border-box !important;
}

#left-panel h1,
#left-panel h2,
#left-panel h3,
#left-panel h4,
#left-panel .prose h1,
#left-panel .prose h2,
#left-panel .prose h3,
#left-panel .prose h4 {
    color: #111827 !important;
    opacity: 1 !important;
}


/* ======================================================
   CHAT PANEL
   ====================================================== */

#chat-panel {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    background: #ffffff !important;
    border: 1px solid #e4e7ec !important;
    border-radius: 14px !important;
    padding: 20px !important;
    box-sizing: border-box !important;
}

#chat-panel h1,
#chat-panel h2,
#chat-panel h3,
#chat-panel h4,
#chat-panel .prose h1,
#chat-panel .prose h2,
#chat-panel .prose h3,
#chat-panel .prose h4 {
    color: #111827 !important;
    opacity: 1 !important;
}

#chat-panel .prose p {
    color: #475467 !important;
}


/* ======================================================
   CHATBOX FINAL
   ====================================================== */

#main-chat {
    width: 100% !important;
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
}


/* ======================================================
   FORCE ALL CHAT TEXT WHITE
   ====================================================== */

#main-chat,
#main-chat * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}


/* ======================================================
   MESSAGE CONTAINERS
   ====================================================== */

#main-chat .message,
#main-chat .message *,
#main-chat .bubble-wrap,
#main-chat .bubble-wrap *,
#main-chat .message-wrap,
#main-chat .message-wrap *,
#main-chat .markdown,
#main-chat .markdown *,
#main-chat .prose,
#main-chat .prose * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}


/* ======================================================
   USER MESSAGE
   ====================================================== */

#main-chat [data-testid="user"],
#main-chat [data-testid="user"] *,
#main-chat .user,
#main-chat .user * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}


/* ======================================================
   ASSISTANT MESSAGE
   ====================================================== */

#main-chat [data-testid="assistant"],
#main-chat [data-testid="assistant"] *,
#main-chat [data-testid="bot"],
#main-chat [data-testid="bot"] *,
#main-chat .bot,
#main-chat .bot * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}


/* ======================================================
   MARKDOWN ELEMENTS
   ====================================================== */

#main-chat p,
#main-chat span,
#main-chat div,
#main-chat strong,
#main-chat b,
#main-chat em,
#main-chat i,
#main-chat li,
#main-chat ul,
#main-chat ol,
#main-chat blockquote,
#main-chat code,
#main-chat pre {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}


/* ======================================================
   MESSAGE BACKGROUNDS
   ====================================================== */

#main-chat [data-testid="user"],
#main-chat .user {
    background: #334155 !important;
}

#main-chat [data-testid="assistant"],
#main-chat [data-testid="bot"],
#main-chat .bot {
    background: #111827 !important;
}


/* ======================================================
   LINKS / CODE
   ====================================================== */

#main-chat a {
    color: #93c5fd !important;
    -webkit-text-fill-color: #93c5fd !important;
}

#main-chat pre,
#main-chat code {
    background: #111827 !important;
    color: #f8fafc !important;
    -webkit-text-fill-color: #f8fafc !important;
}


/* ======================================================
   FORM CONTROLS
   ====================================================== */

textarea,
input,
select {
    background: #ffffff !important;
    color: #111827 !important;
    border-color: #d0d5dd !important;
}

textarea::placeholder,
input::placeholder {
    color: #98a2b3 !important;
}

label,
label span {
    color: #111827 !important;
    opacity: 1 !important;
}


/* ======================================================
   THINKING CHECKBOX
   ====================================================== */

#thinking-box {
    background: #1e293b !important;
    border-radius: 8px !important;
    padding: 10px 12px !important;
    margin-top: 6px !important;
}


/* force label white */

#thinking-box label,
#thinking-box label span,
#thinking-box span,
#thinking-box p {
    color: #ffffff !important;
    opacity: 1 !important;
}


/* checkbox itself */

#thinking-box input[type="checkbox"] {
    cursor: pointer !important;
    pointer-events: auto !important;
    accent-color: #ed1b2f !important;
}


/* make whole row clickable */

#thinking-box label {
    cursor: pointer !important;
    pointer-events: auto !important;
}


/* ======================================================
   ACCORDION
   ====================================================== */

#left-panel details,
#left-panel summary,
#left-panel summary *,
#left-panel details summary span {
    color: #111827 !important;
    opacity: 1 !important;
}


/* ======================================================
   MESSAGE INPUT
   ====================================================== */

#message-row {
    display: flex !important;
    flex-wrap: nowrap !important;
    gap: 10px !important;
}

#message-input {
    flex: 1 !important;
    min-width: 0 !important;
}


/* ======================================================
   SEND BUTTON
   ====================================================== */

#send-button {
    flex: 0 0 100px !important;
    background: #ed1b2f !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

#send-button:hover {
    background: #d31326 !important;
}


/* ======================================================
   QUICK BUTTONS
   ====================================================== */

.quick-button {
    background: #ffffff !important;
    color: #11285a !important;
    border: 1px solid #d0d5dd !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}


/* ======================================================
   STATUS
   ====================================================== */

#runtime-status,
#runtime-status *,
#runtime-status p {
    color: #667085 !important;
    font-size: 12px !important;
}


/* ======================================================
   GENERAL MARKDOWN
   ====================================================== */

.gradio-container .prose {
    color: #111827 !important;
}

.gradio-container .prose strong {
    color: #111827 !important;
}

.gradio-container .prose h1,
.gradio-container .prose h2,
.gradio-container .prose h3,
.gradio-container .prose h4 {
    color: #111827 !important;
}


/* ======================================================
   FOOTER
   ====================================================== */

footer {
    display: none !important;
}


/* ======================================================
   RESPONSIVE
   ====================================================== */

@media (max-width: 780px) {

    #workspace-row {
        flex-direction: column !important;
    }

    #left-panel {
        width: 100% !important;
        min-width: 0 !important;
        max-width: none !important;
        flex: 1 1 auto !important;
    }

    #chat-panel {
        width: 100% !important;
    }
}
"""


# =========================================================
# UI
# =========================================================

with gr.Blocks(
    theme=theme,
    css=CSS,
    title="Tempo Scan Commercial Intelligence",
    fill_width=True
) as demo:

    gr.HTML(
        """
        <div id="tempo-header">

            <div class="tempo-title">
                <span class="tempo-mark">
                    TT
                </span>
                TEMPO SCAN
            </div>

            <div class="tempo-subtitle">
                Commercial Intelligence Assistant
                · Powered by Cloudera AI
            </div>

        </div>
        """
    )


    with gr.Row(
        elem_id="workspace-row"
    ):

        # =================================================
        # SETTINGS
        # =================================================

        with gr.Column(
            elem_id="left-panel"
        ):

            gr.Markdown(
                "### Settings"
            )


            endpoint = gr.Textbox(
                label="Model Endpoint",
                value=DEFAULT_VLLM_URL,
                lines=2
            )


            test_connection = gr.Button(
                "Test Connection"
            )


            connection_status = gr.Textbox(
                label="Connection",
                value="Not checked",
                interactive=False
            )


            model_info = gr.Textbox(
                label="Model",
                value=DEFAULT_MODEL,
                interactive=False,
                lines=2
            )


            # =============================================
            # THINKING CONTROL
            # =============================================

            with gr.Group(
                elem_id="thinking-box"
            ):

                thinking = gr.Checkbox(
                    label="Thinking / Reasoning",
                    value=False,
                    interactive=True
                )


            temperature = gr.Slider(
                minimum=0,
                maximum=1,
                value=0.3,
                step=0.1,
                label="Temperature"
            )


            max_tokens = gr.Slider(
                minimum=128,
                maximum=4096,
                value=2048,
                step=128,
                label="Max Tokens"
            )


            with gr.Accordion(
                "System Prompt",
                open=False
            ):

                system_prompt = gr.Textbox(
                    value=DEFAULT_SYSTEM_PROMPT,
                    lines=12,
                    show_label=False
                )


            clear_button = gr.Button(
                "Clear Conversation"
            )


        # =================================================
        # CHAT
        # =================================================

        with gr.Column(
            elem_id="chat-panel"
        ):

            gr.Markdown(
                """
                ## Chat Conversation

                Ask questions in **Bahasa Indonesia or English**.
                """
            )


            chatbot = gr.Chatbot(
                type="messages",
                height=520,
                elem_id="main-chat",
                show_label=False
            )


            status = gr.Markdown(
                "Ready",
                elem_id="runtime-status"
            )


            with gr.Row(
                elem_id="message-row"
            ):

                message = gr.Textbox(
                    placeholder=(
                        "Ask a question about "
                        "your business data..."
                    ),
                    show_label=False,
                    lines=2,
                    elem_id="message-input"
                )


                send_button = gr.Button(
                    "Send",
                    elem_id="send-button"
                )


            gr.Markdown(
                "#### Suggested questions"
            )


            with gr.Row():

                q1 = gr.Button(
                    "Why did sales decline?",
                    elem_classes="quick-button"
                )

                q2 = gr.Button(
                    "Top performing products",
                    elem_classes="quick-button"
                )


            with gr.Row():

                q3 = gr.Button(
                    "Analyze inventory risk",
                    elem_classes="quick-button"
                )

                q4 = gr.Button(
                    "Forecast next month",
                    elem_classes="quick-button"
                )


    # =====================================================
    # EVENTS
    # =====================================================

    chat_inputs = [
        message,
        chatbot,
        endpoint,
        system_prompt,
        thinking,
        temperature,
        max_tokens
    ]

    chat_outputs = [
        chatbot,
        message,
        status
    ]


    send_button.click(
        fn=send_message,
        inputs=chat_inputs,
        outputs=chat_outputs
    )


    message.submit(
        fn=send_message,
        inputs=chat_inputs,
        outputs=chat_outputs
    )


    test_connection.click(
        fn=check_endpoint,
        inputs=endpoint,
        outputs=[
            connection_status,
            model_info
        ]
    )


    clear_button.click(
        fn=clear_chat,
        outputs=[
            chatbot,
            message,
            status
        ]
    )


    q1.click(
        lambda: (
            "Kenapa sales Jawa Barat turun bulan ini? "
            "Jelaskan key driver dan recommended action."
        ),
        outputs=message
    )


    q2.click(
        lambda: (
            "Produk mana yang memiliki performa "
            "terbaik dan terburuk bulan ini?"
        ),
        outputs=message
    )


    q3.click(
        lambda: (
            "Analisis risiko inventory yang perlu "
            "diperhatikan management."
        ),
        outputs=message
    )


    q4.click(
        lambda: (
            "Apa faktor utama yang perlu "
            "dipertimbangkan untuk forecast sales bulan depan?"
        ),
        outputs=message
    )


# =========================================================
# START
# =========================================================

print("=" * 60)
print("Tempo Scan Commercial Intelligence")
print("=" * 60)
print("Python :", sys.version)
print("Port   :", APP_PORT)
print("vLLM   :", DEFAULT_VLLM_URL)
print("=" * 60)


demo.launch(
    server_name="127.0.0.1",
    server_port=int(APP_PORT),
    share=False,
    show_error=True
)