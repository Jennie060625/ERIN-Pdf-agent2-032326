from __future__ import annotations

import os
import io
import re
import json
import time
import uuid
import base64
import random
import zipfile
import hashlib
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import requests
import yaml
import altair as alt

# -----------------------------
# Optional PDF engines
# -----------------------------
PDF_ENGINE_IMPORTS = {}

try:
    from pypdf import PdfReader, PdfWriter
    PDF_ENGINE_IMPORTS["pypdf"] = True
except Exception:
    PDF_ENGINE_IMPORTS["pypdf"] = False

try:
    import fitz  # PyMuPDF
    PDF_ENGINE_IMPORTS["pymupdf"] = True
except Exception:
    PDF_ENGINE_IMPORTS["pymupdf"] = False

try:
    import pikepdf
    PDF_ENGINE_IMPORTS["pikepdf"] = True
except Exception:
    PDF_ENGINE_IMPORTS["pikepdf"] = False

try:
    import pdfrw
    PDF_ENGINE_IMPORTS["pdfrw"] = True
except Exception:
    PDF_ENGINE_IMPORTS["pdfrw"] = False


# -----------------------------
# Constants / Model catalog
# -----------------------------
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4.1-mini"]
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]
GROK_MODELS = ["grok-4-fast-reasoning", "grok-3-mini"]
# Anthropic is model-string dependent; keep a safe defaults list + allow admin whitelist later.
ANTHROPIC_MODELS = ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]

ALL_MODELS = OPENAI_MODELS + GEMINI_MODELS + ANTHROPIC_MODELS + GROK_MODELS

DEFAULT_MAX_TOKENS = 12000
DEFAULT_TEMPERATURE = 0.2

APP_VERSION = "2.9"
APP_TITLE = f"FDA 510(k) Review Studio v{APP_VERSION} — Nordic WOW Edition"

# PDF trimming "5 packages" mapping to best-effort engines
TRIM_ENGINES = [
    ("Option 1 — High-speed high-fidelity (PyMuPDF)", "pymupdf"),
    ("Option 2 — Stable pure parsing (pypdf)", "pypdf"),
    ("Option 3 — Layout preservation (pikepdf)", "pikepdf"),
    ("Option 4 — Velocity & resilience (pdfrw)", "pdfrw"),
    ("Option 5 — Lightweight object manipulation (pypdf-fast)", "pypdf"),  # alias to pypdf with different behavior
]

# Painter style presets (inspired palettes; restrained)
PAINTER_STYLES = [
    ("Monet Mist", {"accent": "#4C8DAE", "bg": "#F5F7FA", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Van Gogh Vivid Night", {"accent": "#2F6FED", "bg": "#0B1220", "panel": "#111B2E", "text": "#E5E7EB", "muted": "#9CA3AF"}),
    ("Hokusai Wave Blue", {"accent": "#2563EB", "bg": "#F8FAFC", "panel": "#FFFFFF", "text": "#0B1220", "muted": "#475569"}),
    ("Klimt Gilded Calm", {"accent": "#B08900", "bg": "#FBFAF7", "panel": "#FFFFFF", "text": "#111827", "muted": "#6B7280"}),
    ("Picasso Minimal Line", {"accent": "#111827", "bg": "#FAFAFA", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#6B7280"}),
    ("Dali Surreal Sand", {"accent": "#B45309", "bg": "#FFFBEB", "panel": "#FFFFFF", "text": "#1F2937", "muted": "#6B7280"}),
    ("Kandinsky Geometry Pop", {"accent": "#DC2626", "bg": "#F8FAFC", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Rothko Deep Fields", {"accent": "#7C3AED", "bg": "#0A0A0A", "panel": "#121212", "text": "#EDEDED", "muted": "#A3A3A3"}),
    ("Vermeer Quiet Pearl", {"accent": "#0F766E", "bg": "#F6F7F9", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#6B7280"}),
    ("Turner Atmospheric Gold", {"accent": "#D97706", "bg": "#FFFBF5", "panel": "#FFFFFF", "text": "#1F2937", "muted": "#6B7280"}),
    ("Cézanne Structured Earth", {"accent": "#7C2D12", "bg": "#FAF7F2", "panel": "#FFFFFF", "text": "#1F2937", "muted": "#6B7280"}),
    ("Matisse Cutout Bright", {"accent": "#EC4899", "bg": "#FDF2F8", "panel": "#FFFFFF", "text": "#111827", "muted": "#6B7280"}),
    ("Pollock Speckle Neutral", {"accent": "#334155", "bg": "#F8FAFC", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Rembrandt Ember Shadow", {"accent": "#B91C1C", "bg": "#0B0B0B", "panel": "#141414", "text": "#F3F4F6", "muted": "#9CA3AF"}),
    ("Frida Botanical Jewel", {"accent": "#16A34A", "bg": "#F0FDF4", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Magritte Sky Paradox", {"accent": "#0284C7", "bg": "#F0F9FF", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Chagall Dream Indigo", {"accent": "#4F46E5", "bg": "#0B1020", "panel": "#111A33", "text": "#E5E7EB", "muted": "#9CA3AF"}),
    ("Edward Hopper Still Noon", {"accent": "#0EA5E9", "bg": "#F8FAFC", "panel": "#FFFFFF", "text": "#0F172A", "muted": "#64748B"}),
    ("Georgia O’Keeffe Desert Bloom", {"accent": "#F97316", "bg": "#FFF7ED", "panel": "#FFFFFF", "text": "#111827", "muted": "#6B7280"}),
    ("Ukiyo-e Ink Wash", {"accent": "#0F172A", "bg": "#F3F4F6", "panel": "#FFFFFF", "text": "#0B1220", "muted": "#475569"}),
]

LANGS = ["English", "繁體中文"]

I18N = {
    "English": {
        "nav_ingest": "Ingest & Trim",
        "nav_docprompt": "Direct Doc Prompting",
        "nav_agents": "Agent Orchestration",
        "nav_wow": "WOW Modules",
        "nav_notes": "AI Note Keeper",
        "nav_dashboard": "WOW Dashboard",
        "nav_export": "Export Center",
        "nav_logs": "Live Log",
        "nav_settings": "Settings",
        "theme": "Theme",
        "lang": "Language",
        "style": "Painter Style",
        "jackpot": "Jackpot",
        "purge": "Total Purge (Clear Session)",
        "providers": "Providers & Credentials",
        "connected_env": "Connected via environment",
        "missing_key": "Missing — enter session key",
        "key_input": "Session API Key (masked)",
        "save": "Save",
        "run": "Run",
        "commit": "Commit as Next Input",
        "download": "Download",
        "upload": "Upload PDFs",
        "trim_engine": "Trimming engine",
        "page_range": "Page ranges (e.g., 1-3,5,10-12)",
        "execute_trim": "Execute Trim",
        "cut_pdf": "Cut PDF",
        "doc_question": "Ask about the cut document",
        "skill": "Skill / Instructions",
        "default_skill": "Default Regulatory Skill",
        "model": "Model",
        "max_tokens": "Max tokens",
        "temperature": "Temperature",
        "agents_yaml": "agents.yaml",
        "load_agents": "Load agents.yaml",
        "macro_summary": "Macro Summary (3000–4000 words)",
        "make_summary": "Generate Macro Summary",
        "transform_note": "Transform into Organized Markdown",
        "ai_magics": "AI Magics",
        "keyword": "Keywords",
        "color": "Color",
        "apply": "Apply",
        "export_zip": "Build Export Bundle (ZIP)",
    },
    "繁體中文": {
        "nav_ingest": "匯入與裁切",
        "nav_docprompt": "文件即時提問",
        "nav_agents": "代理編排",
        "nav_wow": "WOW 模組",
        "nav_notes": "AI 筆記管家",
        "nav_dashboard": "WOW 儀表板",
        "nav_export": "匯出中心",
        "nav_logs": "即時日誌",
        "nav_settings": "設定",
        "theme": "主題",
        "lang": "語言",
        "style": "畫家風格",
        "jackpot": "隨機彩蛋",
        "purge": "全面清除（清空本次工作階段）",
        "providers": "供應商與金鑰",
        "connected_env": "已透過環境變數連線",
        "missing_key": "缺少金鑰 — 請輸入本次工作階段金鑰",
        "key_input": "工作階段 API Key（遮罩）",
        "save": "儲存",
        "run": "執行",
        "commit": "確認並作為下一步輸入",
        "download": "下載",
        "upload": "上傳 PDF",
        "trim_engine": "裁切引擎",
        "page_range": "頁碼範圍（例：1-3,5,10-12）",
        "execute_trim": "執行裁切",
        "cut_pdf": "已裁切 PDF",
        "doc_question": "針對裁切文件提問",
        "skill": "技能／指令",
        "default_skill": "預設法規稽核技能",
        "model": "模型",
        "max_tokens": "最大 tokens",
        "temperature": "溫度",
        "agents_yaml": "agents.yaml",
        "load_agents": "載入 agents.yaml",
        "macro_summary": "總覽摘要（3000–4000 字）",
        "make_summary": "生成總覽摘要",
        "transform_note": "整理成結構化 Markdown",
        "ai_magics": "AI 魔法",
        "keyword": "關鍵字",
        "color": "顏色",
        "apply": "套用",
        "export_zip": "建立匯出套件（ZIP）",
    },
}

DEFAULT_REG_SKILL = """You are a senior FDA 510(k) regulatory reviewer.
Analyze the provided document content with strict traceability and a compliance mindset.

MANDATES:
1) Extract safety, efficacy, and performance claims.
2) Identify all cited standards/guidance and any acceptance criteria.
3) Flag missing evidence, internal contradictions, and unsupported marketing language.
4) Output in a structured table:
   - Finding
   - Evidence quote
   - Source anchor (if available)
   - Risk level (Low/Med/High)
   - Recommended reviewer action
Be concise but complete. Avoid speculation and label uncertainty clearly.
"""

NOTE_ORGANIZER_PROMPT = """Transform the user's pasted notes into organized, audit-friendly Markdown.

Required structure:
# Title
## Executive Summary (5–10 bullets)
## Key Findings (grouped by topic)
## Evidence Snippets (quote → interpretation → risk)
## Open Questions
## Action Items
## Decision Log (if any)
Constraints:
- Preserve original meaning; do not invent facts.
- Use clear headings and bullet lists.
"""

MACRO_SUMMARY_PROMPT = """Generate a comprehensive FDA-style 510(k) review macro summary (target 3000–4000 words).
Use a structured format (headings) covering:
- Device description, intended use/indications
- Predicate comparison overview (if available)
- Performance testing (bench, software, EMC, biocomp, sterilization, shelf-life, packaging, usability, cybersecurity)
- Labeling and claims review
- Risk assessment and key deficiencies
- RTA-style completeness observations
- Evidence mapping / traceability notes

Rules:
- Do not fabricate evidence.
- Where evidence is missing/unclear, explicitly state it and propose reviewer follow-up questions.
- Use Traditional Chinese only if the output language preference indicates zh-TW.
"""

# -----------------------------
# Utilities: session state
# -----------------------------
def ss_init():
    defaults = {
        "lang": "English",
        "theme": "Light",
        "style_name": PAINTER_STYLES[0][0],
        "style": PAINTER_STYLES[0][1],
        "reduced_motion": False,
        "contrast_boost": False,
        "font_scale": 1.0,

        # credentials
        "session_keys": {},  # provider -> key (volatile)

        # logs + telemetry
        "logs": [],  # list of dict
        "telemetry": {
            "calls": [],  # list of call records
            "tokens_est": 0,
            "cost_est": 0.0,
            "latencies": [],
        },

        # ingestion artifacts
        "uploads": [],  # list of {id, name, bytes, page_count, metadata}
        "trim_specs": {},  # upload_id -> {range_str, engine}
        "cut_pdfs": {},  # upload_id -> bytes
        "cut_meta": {},  # upload_id -> {ranges, engine, created_at}

        # extracted text
        "extracted_text": {},  # artifact_id -> text
        "consolidated_text": "",

        # doc prompting
        "docprompt": {
            "active_upload_id": None,
            "skill": DEFAULT_REG_SKILL,
            "history": [],  # list of {q, a, model, ts}
            "last_output": "",
        },

        # agents
        "agents": [],  # parsed agents list
        "agents_yaml_raw": "",
        "agent_runs": [],  # list of run records
        "agent_outputs_raw": {},  # agent_index -> raw output
        "agent_outputs_committed": {},  # agent_index -> committed output
        "agent_input_context": "",  # current context passed to next agent

        # macro summary versions
        "macro_versions": [],  # list of {id, ts, model, text}

        # WOW modules outputs
        "wow_outputs": {},  # module_name -> text

        # notes
        "notes": {
            "raw_input": "",
            "organized_md": "",
            "versions": [],  # list of {id, ts, md}
            "chat": [],  # {q,a,model,ts}
        },

        # UI state
        "active_stage": "Idle",
        "output_language_pref": "Auto",  # Auto/English/繁體中文
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def t(key: str) -> str:
    lang = st.session_state.get("lang", "English")
    return I18N.get(lang, I18N["English"]).get(key, key)


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def log_event(kind: str, message: str, severity: str = "INFO", meta: Optional[Dict[str, Any]] = None):
    entry = {
        "ts": now_iso(),
        "severity": severity,
        "kind": kind,
        "message": message,
        "meta": meta or {},
    }
    st.session_state.logs.append(entry)


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def est_tokens(text: str) -> int:
    # Rough heuristic; keep simple and provider-agnostic
    return max(1, int(len(text) / 4))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sanitize_logs_for_export(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Keys are never logged, but sanitize meta just in case
    sanitized = []
    for e in logs:
        e2 = json.loads(json.dumps(e))
        meta = e2.get("meta", {})
        for k in list(meta.keys()):
            if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower():
                meta[k] = "[REDACTED]"
        e2["meta"] = meta
        sanitized.append(e2)
    return sanitized


# -----------------------------
# CSS theming
# -----------------------------
def apply_style():
    style = st.session_state.style
    accent = style["accent"]
    bg = style["bg"]
    panel = style["panel"]
    text = style["text"]
    muted = style["muted"]

    font_scale = float(st.session_state.get("font_scale", 1.0))
    contrast_boost = st.session_state.get("contrast_boost", False)
    reduced_motion = st.session_state.get("reduced_motion", False)

    border = "#CBD5E1" if not contrast_boost else "#64748B"
    shadow = "none" if reduced_motion else "0 8px 24px rgba(0,0,0,0.08)"

    st.markdown(
        f"""
        <style>
        :root {{
            --wow-accent: {accent};
            --wow-bg: {bg};
            --wow-panel: {panel};
            --wow-text: {text};
            --wow-muted: {muted};
            --wow-border: {border};
        }}

        html, body, [class*="stApp"] {{
            background: var(--wow-bg) !important;
            color: var(--wow-text) !important;
            font-size: {font_scale * 16}px;
        }}

        /* Panels */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--wow-panel);
            border: 1px solid var(--wow-border);
            border-radius: 14px;
            box-shadow: {shadow};
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 12px !important;
            border: 1px solid var(--wow-border) !important;
        }}
        .stButton > button[kind="primary"] {{
            background: var(--wow-accent) !important;
            border-color: var(--wow-accent) !important;
            color: white !important;
        }}

        /* Tabs accent */
        button[data-baseweb="tab"] > div {{
            font-weight: 600;
        }}

        /* Input focus accent */
        input:focus, textarea:focus {{
            outline: 2px solid var(--wow-accent) !important;
            border-color: var(--wow-accent) !important;
        }}

        /* Reduce motion */
        * {{
            scroll-behavior: {"auto" if reduced_motion else "smooth"};
            transition: {"none" if reduced_motion else "all 120ms ease"};
        }}

        /* Subtle badge */
        .wow-badge {{
            display: inline-block;
            padding: 2px 10px;
            border: 1px solid var(--wow-border);
            border-radius: 999px;
            font-size: 12px;
            color: var(--wow-muted);
            background: rgba(127,127,127,0.06);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Credential broker
# -----------------------------
def env_key_for(provider: str) -> Optional[str]:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    if provider == "grok":
        return os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    return None


def get_key(provider: str) -> Optional[str]:
    # env-first, then session
    k = env_key_for(provider)
    if k:
        return k
    return st.session_state.session_keys.get(provider)


def provider_for_model(model: str) -> str:
    if model in OPENAI_MODELS:
        return "openai"
    if model in GEMINI_MODELS:
        return "gemini"
    if model in GROK_MODELS:
        return "grok"
    # default anthopic if matches list or if starts with "claude"
    if model in ANTHROPIC_MODELS or model.lower().startswith("claude"):
        return "anthropic"
    # fallback
    return "openai"


# -----------------------------
# AI Call Adapters (minimal, non-stream)
# -----------------------------
@dataclass
class AIResult:
    text: str
    usage: Dict[str, Any]
    raw: Dict[str, Any]


def call_openai_chat(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> AIResult:
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = get_key("openai")
    if not key:
        raise RuntimeError("Missing OpenAI API key")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    dt_s = time.time() - t0
    if r.status_code >= 300:
        raise RuntimeError(f"OpenAI error {r.status_code}: {r.text[:1000]}")
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return AIResult(text=text, usage={**usage, "latency_s": dt_s}, raw=data)


def call_grok_chat(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> AIResult:
    # Grok is often OpenAI-compatible via xAI endpoint.
    base_url = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    key = get_key("grok")
    if not key:
        raise RuntimeError("Missing Grok API key")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    dt_s = time.time() - t0
    if r.status_code >= 300:
        raise RuntimeError(f"Grok error {r.status_code}: {r.text[:1000]}")
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return AIResult(text=text, usage={**usage, "latency_s": dt_s}, raw=data)


def call_anthropic(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> AIResult:
    # Use Anthropic Messages API via requests to keep dependencies minimal.
    key = get_key("anthropic")
    if not key:
        raise RuntimeError("Missing Anthropic API key")

    # Anthropic expects a different schema; map chat messages into content blocks.
    # We'll convert system messages into a top-level system string.
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    system_text = "\n\n".join(system_parts).strip() if system_parts else None

    user_assistant = [m for m in messages if m["role"] in ("user", "assistant")]
    anthro_msgs = [{"role": m["role"], "content": m["content"]} for m in user_assistant]

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthro_msgs,
    }
    if system_text:
        payload["system"] = system_text

    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    dt_s = time.time() - t0
    if r.status_code >= 300:
        raise RuntimeError(f"Anthropic error {r.status_code}: {r.text[:1000]}")
    data = r.json()
    # content is list of blocks; take text blocks
    parts = []
    for b in data.get("content", []):
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
    text = "\n".join(parts).strip()
    usage = data.get("usage", {})
    return AIResult(text=text, usage={**usage, "latency_s": dt_s}, raw=data)


def call_gemini(model: str, system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    # Gemini REST API (Generative Language)
    key = get_key("gemini")
    if not key:
        raise RuntimeError("Missing Gemini API key")

    # Minimal REST call (v1beta style endpoints are common; keep robust).
    # Many deployments use: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system}"}]})
    contents.append({"role": "user", "parts": [{"text": user}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    t0 = time.time()
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=180)
    dt_s = time.time() - t0
    if r.status_code >= 300:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:1000]}")
    data = r.json()

    # Extract candidate text
    text_parts = []
    for cand in data.get("candidates", []):
        content = cand.get("content", {})
        for p in content.get("parts", []):
            if "text" in p:
                text_parts.append(p["text"])
    text = "\n".join(text_parts).strip()

    usage = data.get("usageMetadata", {})  # differs from OpenAI schema
    return AIResult(text=text, usage={**usage, "latency_s": dt_s}, raw=data)


def ai_call(model: str, system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    provider = provider_for_model(model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    # Output language preference injection (UI-level control)
    pref = st.session_state.get("output_language_pref", "Auto")
    if pref in ("English", "繁體中文"):
        lang_hint = "Traditional Chinese (繁體中文)" if pref == "繁體中文" else "English"
        messages.insert(0, {"role": "system", "content": f"Output language requirement: {lang_hint}."})

    # Preflight: ensure credentials exist
    key = get_key(provider)
    if not key:
        raise RuntimeError(f"Missing API key for provider: {provider}")

    # Execute
    if provider == "openai":
        return call_openai_chat(model, messages, max_tokens, temperature)
    if provider == "grok":
        return call_grok_chat(model, messages, max_tokens, temperature)
    if provider == "anthropic":
        return call_anthropic(model, messages, max_tokens, temperature)
    if provider == "gemini":
        return call_gemini(model, system="\n".join([m["content"] for m in messages if m["role"] == "system"]),
                           user="\n".join([m["content"] for m in messages if m["role"] == "user"]),
                           max_tokens=max_tokens, temperature=temperature)
    # fallback openai
    return call_openai_chat(model, messages, max_tokens, temperature)


def record_telemetry(model: str, prompt_text: str, result: AIResult, kind: str):
    # Estimate tokens even if provider doesn't return.
    prompt_tok = est_tokens(prompt_text)
    completion_tok = est_tokens(result.text)
    total_tok = prompt_tok + completion_tok

    latency = float(result.usage.get("latency_s", 0.0))
    st.session_state.telemetry["tokens_est"] += total_tok
    st.session_state.telemetry["latencies"].append(latency)

    call_rec = {
        "ts": now_iso(),
        "kind": kind,
        "model": model,
        "provider": provider_for_model(model),
        "prompt_tok_est": prompt_tok,
        "completion_tok_est": completion_tok,
        "total_tok_est": total_tok,
        "latency_s": latency,
    }
    st.session_state.telemetry["calls"].append(call_rec)
    log_event("provider_call", f"{kind}: {model} completed in {latency:.2f}s", "INFO", meta=call_rec)


# -----------------------------
# PDF helpers
# -----------------------------
def parse_page_ranges(range_str: str, max_pages: int) -> List[int]:
    # 1-indexed ranges in UI; return 0-indexed page indices
    s = (range_str or "").strip()
    if not s:
        return list(range(max_pages))
    parts = [p.strip() for p in s.split(",") if p.strip()]
    pages = set()
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a.strip()); b = int(b.strip())
            if a > b:
                a, b = b, a
            for p in range(a, b + 1):
                if 1 <= p <= max_pages:
                    pages.add(p - 1)
        else:
            p = int(part)
            if 1 <= p <= max_pages:
                pages.add(p - 1)
    out = sorted(pages)
    return out


def pdf_page_count(pdf_bytes: bytes) -> int:
    if PDF_ENGINE_IMPORTS["pypdf"]:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    if PDF_ENGINE_IMPORTS["pymupdf"]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return doc.page_count
    raise RuntimeError("No PDF engine available to count pages (install pypdf or pymupdf).")


def trim_pdf(pdf_bytes: bytes, page_idxs: List[int], engine: str) -> bytes:
    # engine best-effort; fallback to pypdf
    if engine == "pymupdf" and PDF_ENGINE_IMPORTS["pymupdf"]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        new_doc = fitz.open()
        for i in page_idxs:
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
        out = new_doc.tobytes()
        return out

    if engine == "pikepdf" and PDF_ENGINE_IMPORTS["pikepdf"]:
        src = pikepdf.open(io.BytesIO(pdf_bytes))
        dst = pikepdf.Pdf.new()
        for i in page_idxs:
            dst.pages.append(src.pages[i])
        bio = io.BytesIO()
        dst.save(bio)
        return bio.getvalue()

    if engine == "pdfrw" and PDF_ENGINE_IMPORTS["pdfrw"]:
        src = pdfrw.PdfReader(fdata=pdf_bytes)
        dst = pdfrw.PdfWriter()
        for i in page_idxs:
            dst.addpage(src.pages[i])
        bio = io.BytesIO()
        dst.write(bio)
        return bio.getvalue()

    # default: pypdf
    if not PDF_ENGINE_IMPORTS["pypdf"]:
        raise RuntimeError("pypdf not installed; cannot trim PDF.")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i in page_idxs:
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 80) -> str:
    # text-only baseline extraction
    if PDF_ENGINE_IMPORTS["pypdf"]:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        n = min(len(reader.pages), max_pages)
        for i in range(n):
            try:
                texts.append(reader.pages[i].extract_text() or "")
            except Exception:
                texts.append("")
        return "\n\n".join(texts).strip()
    if PDF_ENGINE_IMPORTS["pymupdf"]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        n = min(doc.page_count, max_pages)
        for i in range(n):
            try:
                texts.append(doc.load_page(i).get_text("text") or "")
            except Exception:
                texts.append("")
        return "\n\n".join(texts).strip()
    return ""


def render_pdf_inline(pdf_bytes: bytes, height: int = 640):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f"""
    <iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" type="application/pdf"></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)


# -----------------------------
# agents.yaml
# -----------------------------
def load_agents_yaml(raw: str) -> List[Dict[str, Any]]:
    data = yaml.safe_load(raw) if raw.strip() else None
    if not data:
        return []
    # Accept either {"agents":[...]} or a list
    agents = data.get("agents") if isinstance(data, dict) else data
    if not isinstance(agents, list):
        raise ValueError("Invalid agents.yaml format: expected list or {agents: তাল}.")
    normalized = []
    for idx, a in enumerate(agents):
        if not isinstance(a, dict):
            continue
        normalized.append({
            "id": a.get("id", f"agent_{idx+1}"),
            "name": a.get("name", f"Agent {idx+1}"),
            "provider": a.get("provider", provider_for_model(a.get("model", "gpt-4o-mini"))),
            "model": a.get("model", "gpt-4o-mini"),
            "temperature": float(a.get("temperature", DEFAULT_TEMPERATURE)),
            "max_tokens": int(a.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "system": a.get("system", ""),
            "user": a.get("user", ""),
        })
    return normalized


def default_agents_yaml() -> str:
    # A small starter pipeline that preserves "original features" behavior without forcing a specific workflow.
    return """agents:
  - id: intake
    name: Intake Normalizer
    model: gpt-4o-mini
    temperature: 0.2
    max_tokens: 6000
    system: |
      You are a regulatory documentation analyst.
      Normalize and segment the provided consolidated submission text into a structured outline.
    user: |
      Create a structured outline of the submission. Identify major sections and any obvious gaps.
      Return Markdown.
  - id: risk_scan
    name: Risk & Deficiency Scan
    model: gemini-2.5-flash
    temperature: 0.2
    max_tokens: 8000
    system: |
      You are a strict FDA 510(k) reviewer.
    user: |
      Using the outline + text, identify top risks, missing evidence, contradictions, and unclear claims.
      Output a prioritized table with severity and recommended reviewer actions.
"""


# -----------------------------
# WOW modules prompts
# -----------------------------
WOW_MODULES = [
    ("Evidence Mapping System", """Map each factual claim in the macro summary to source anchors.
Output a table: Claim | Anchor(s) | Confidence | Notes. Flag unanchored claims explicitly."""),
    ("Consistency Guardian", """Detect internal inconsistencies and contradictions.
Output a prioritized list with anchors and recommended corrections/questions."""),
    ("Regulatory Risk Radar", """Create a scored risk register aligned to common FDA pain points.
Output a table + brief narrative + suggested reviewer focus areas."""),
    ("Completeness Heuristic Gatekeeper", """Apply a refuse-to-accept style heuristic checklist.
Output Pass/Fail/Unclear per item with evidence anchors."""),
    ("Labeling and Claims Inspector", """Extract all marketing/labeling claims and check for supporting evidence.
Flag claims that outpace evidence and suggest safer qualified wording."""),
    # New 3
    ("Predicate Comparison Matrix Builder", """Build a predicate comparison matrix.
Output: candidate predicates (if possible), and a side-by-side matrix of key characteristics.
Flag equivalence weak points and missing data needed to support substantial equivalence."""),
    ("Standards & Guidance Crosswalk", """Extract cited standards/guidance, crosswalk them to evidence of testing and declarations.
Flag outdated versions, missing declarations, and unclear test conditions."""),
    ("Test Coverage Gap Analyzer", """Infer expected verification/validation domains from claims/device type and identify gaps.
Output: coverage table, severity, and recommended sponsor questions."""),
]


# -----------------------------
# UI Components: WOW Indicator / Dashboard / Logs
# -----------------------------
def wow_indicator():
    stage = st.session_state.get("active_stage", "Idle")
    calls = st.session_state.telemetry.get("calls", [])
    last_call = calls[-1] if calls else None

    # Provider readiness
    providers = ["openai", "gemini", "anthropic", "grok"]
    readiness = {}
    for p in providers:
        readiness[p] = bool(get_key(p))

    # Memory pressure heuristic: based on uploads sizes
    total_mb = sum(len(u["bytes"]) for u in st.session_state.uploads) / (1024 * 1024) if st.session_state.uploads else 0.0
    token_est = st.session_state.telemetry.get("tokens_est", 0)

    with st.container(border=True):
        cols = st.columns([2.2, 1.2, 1.2, 1.2])
        cols[0].markdown(f"**WOW Status**: <span class='wow-badge'>{stage}</span>", unsafe_allow_html=True)
        cols[1].metric("Session MB", f"{total_mb:.1f}")
        cols[2].metric("Token Est.", f"{token_est:,}")
        cols[3].metric("Calls", f"{len(calls)}")

        st.caption("Provider readiness (env/session key present): " +
                   " | ".join([f"{p}: {'OK' if readiness[p] else '—'}" for p in providers]))
        if last_call:
            st.caption(f"Last call: {last_call['kind']} · {last_call['model']} · {last_call['latency_s']:.2f}s")


def wow_dashboard():
    st.session_state.active_stage = "WOW Dashboard"
    wow_indicator()

    calls = st.session_state.telemetry.get("calls", [])
    if not calls:
        st.info("No telemetry yet. Run document prompting, agents, macro summary, or WOW modules to populate the dashboard.")
        return

    df = calls  # list of dicts; altair can accept via st.dataframe but we’ll chart via DataFrame-less dict by converting
    import pandas as pd
    pdf = pd.DataFrame(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total calls", int(pdf.shape[0]))
    c2.metric("Avg latency (s)", f"{pdf['latency_s'].mean():.2f}")
    c3.metric("Total token est.", f"{int(pdf['total_tok_est'].sum()):,}")

    st.subheader("Latency by model")
    chart = alt.Chart(pdf).mark_bar().encode(
        x=alt.X("model:N", sort="-y", title="Model"),
        y=alt.Y("mean(latency_s):Q", title="Mean latency (s)"),
        color=alt.Color("provider:N", title="Provider"),
        tooltip=["model", "provider", alt.Tooltip("mean(latency_s):Q", title="Mean latency (s)", format=".2f")]
    ).properties(height=280)
    st.altair_chart(chart, use_container_width=True)

    st.subheader("Token estimate over time")
    pdf["ts_dt"] = pd.to_datetime(pdf["ts"])
    chart2 = alt.Chart(pdf).mark_line(point=True).encode(
        x=alt.X("ts_dt:T", title="Time"),
        y=alt.Y("total_tok_est:Q", title="Total tokens (estimate)"),
        color=alt.Color("kind:N", title="Kind"),
        tooltip=["ts", "kind", "model", "total_tok_est"]
    ).properties(height=280)
    st.altair_chart(chart2, use_container_width=True)

    st.subheader("Pipeline timeline (artifact events)")
    # Timeline from logs
    logs = st.session_state.logs[-250:]
    st.dataframe(logs, use_container_width=True, hide_index=True)


def live_log_view():
    st.session_state.active_stage = "Live Log"
    wow_indicator()

    logs = st.session_state.logs
    if not logs:
        st.info("No logs yet.")
        return

    severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    kinds = sorted({e["kind"] for e in logs})

    colf = st.columns([1, 1, 2])
    sev = colf[0].multiselect("Severity", severities, default=["INFO", "WARNING", "ERROR", "CRITICAL"])
    kind = colf[1].multiselect("Kind", kinds, default=kinds[:])
    q = colf[2].text_input("Search", value="")

    def ok(e):
        if e["severity"] not in sev:
            return False
        if kind and e["kind"] not in kind:
            return False
        if q and q.lower() not in (e["message"] + " " + json.dumps(e.get("meta", {}))).lower():
            return False
        return True

    filtered = [e for e in logs if ok(e)]
    st.dataframe(filtered[-500:], use_container_width=True, hide_index=True)


# -----------------------------
# UI: Settings / Appearance
# -----------------------------
def sidebar_controls():
    st.sidebar.title("Nordic WOW")

    # Language / Theme / Style
    lang = st.sidebar.selectbox(t("lang"), LANGS, index=LANGS.index(st.session_state.lang))
    st.session_state.lang = lang

    theme = st.sidebar.selectbox(t("theme"), ["Light", "Dark"], index=["Light", "Dark"].index(st.session_state.theme))
    st.session_state.theme = theme

    style_names = [s[0] for s in PAINTER_STYLES]
    st.sidebar.write(t("style"))
    style_name = st.sidebar.selectbox("", style_names, index=style_names.index(st.session_state.style_name))
    st.session_state.style_name = style_name
    st.session_state.style = dict([s for s in PAINTER_STYLES if s[0] == style_name][0][1])

    c = st.sidebar.columns([1, 1])
    if c[0].button(t("jackpot"), use_container_width=True):
        chosen = random.choice(PAINTER_STYLES)
        st.session_state.style_name = chosen[0]
        st.session_state.style = chosen[1]
        log_event("ui", f"Jackpot style selected: {chosen[0]}", "INFO")

    st.sidebar.toggle("Reduced motion", key="reduced_motion")
    st.sidebar.toggle("Contrast boost", key="contrast_boost")
    st.sidebar.slider("Font scale", 0.9, 1.25, st.session_state.font_scale, 0.05, key="font_scale")

    st.sidebar.divider()
    st.sidebar.selectbox("AI Output Language Preference", ["Auto", "English", "繁體中文"],
                         index=["Auto", "English", "繁體中文"].index(st.session_state.output_language_pref),
                         key="output_language_pref")

    st.sidebar.divider()
    if st.sidebar.button(t("purge"), type="primary", use_container_width=True):
        purge_session()

    st.sidebar.caption(f"Version {APP_VERSION}")


def purge_session():
    # Preserve cosmetic preferences but clear artifacts/keys/logs
    keep = {
        "lang": st.session_state.lang,
        "theme": st.session_state.theme,
        "style_name": st.session_state.style_name,
        "style": st.session_state.style,
        "reduced_motion": st.session_state.reduced_motion,
        "contrast_boost": st.session_state.contrast_boost,
        "font_scale": st.session_state.font_scale,
        "output_language_pref": st.session_state.output_language_pref,
    }
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    ss_init()
    # Restore kept
    for k, v in keep.items():
        st.session_state[k] = v
    log_event("security", "Total purge executed. Session artifacts and session keys cleared.", "WARNING")


def providers_panel():
    st.subheader(t("providers"))

    providers = [
        ("OpenAI", "openai", "OPENAI_API_KEY"),
        ("Gemini", "gemini", "GEMINI_API_KEY / GOOGLE_API_KEY"),
        ("Anthropic", "anthropic", "ANTHROPIC_API_KEY"),
        ("Grok (xAI)", "grok", "GROK_API_KEY / XAI_API_KEY"),
    ]

    for label, p, env_hint in providers:
        with st.container(border=True):
            env = env_key_for(p)
            if env:
                st.write(f"**{label}** — {t('connected_env')}")
                st.caption(f"Env: {env_hint}")
            else:
                st.write(f"**{label}** — {t('missing_key')}")
                k = st.text_input(f"{label} · {t('key_input')}", type="password", key=f"key_{p}")
                col = st.columns([1, 1, 2])
                if col[0].button(t("save"), key=f"save_{p}"):
                    if k.strip():
                        st.session_state.session_keys[p] = k.strip()
                        log_event("security", f"Session key set for provider: {p}", "INFO")
                        st.success("Saved for this session.")
                    else:
                        st.warning("Empty key not saved.")
                if col[1].button("Clear", key=f"clear_{p}"):
                    st.session_state.session_keys.pop(p, None)
                    log_event("security", f"Session key cleared for provider: {p}", "INFO")
                    st.info("Cleared.")


# -----------------------------
# Tab: Ingest & Trim
# -----------------------------
def ingest_trim_tab():
    st.session_state.active_stage = "Ingest & Trim"
    wow_indicator()

    st.header(t("nav_ingest"))

    with st.container(border=True):
        uploaded = st.file_uploader(t("upload"), type=["pdf"], accept_multiple_files=True)
        if uploaded:
            for f in uploaded:
                b = f.read()
                uid = str(uuid.uuid4())
                try:
                    n_pages = pdf_page_count(b)
                except Exception as e:
                    n_pages = 0
                    log_event("ingest", f"Failed to read page count for {f.name}: {e}", "ERROR")
                item = {
                    "id": uid,
                    "name": f.name,
                    "bytes": b,
                    "page_count": n_pages,
                    "sha256": sha256_bytes(b),
                    "uploaded_at": now_iso(),
                }
                st.session_state.uploads.append(item)
                log_event("ingest", f"Uploaded {f.name} ({len(b)/1024/1024:.1f} MB, {n_pages} pages)", "INFO",
                          meta={"upload_id": uid, "sha256": item["sha256"], "pages": n_pages})

    if not st.session_state.uploads:
        st.info("Upload PDFs to begin.")
        return

    st.subheader("Staging Registry")
    for u in st.session_state.uploads:
        with st.container(border=True):
            st.markdown(f"**{u['name']}**  \n"
                        f"<span class='wow-badge'>pages: {u['page_count']}</span> "
                        f"<span class='wow-badge'>sha256: {u['sha256'][:10]}…</span>",
                        unsafe_allow_html=True)

            col = st.columns([1.4, 1.4, 1.0])
            engine_label = col[0].selectbox(t("trim_engine"), [x[0] for x in TRIM_ENGINES], key=f"engine_{u['id']}")
            engine = dict(TRIM_ENGINES)[engine_label]
            ranges = col[1].text_input(t("page_range"), value="1-3", key=f"range_{u['id']}")
            show_preview = col[2].toggle("Preview", value=False, key=f"preview_{u['id']}")

            st.session_state.trim_specs[u["id"]] = {"range_str": ranges, "engine": engine}

            if show_preview:
                st.caption("Preview renders original PDF. For very large files, disable preview.")
                render_pdf_inline(u["bytes"], height=520)

            c = st.columns([1.0, 1.0, 2.0])
            if c[0].button(t("execute_trim"), key=f"trim_{u['id']}", type="primary"):
                if u["page_count"] <= 0:
                    st.error("Cannot trim: unknown page count.")
                else:
                    try:
                        page_idxs = parse_page_ranges(ranges, u["page_count"])
                        if not page_idxs:
                            raise ValueError("Empty page selection.")
                        # Best-effort engine with fallback logging
                        chosen = engine
                        if not PDF_ENGINE_IMPORTS.get(engine, False):
                            log_event("trim", f"Engine {engine} not available. Falling back to pypdf.", "WARNING",
                                      meta={"upload_id": u["id"], "requested_engine": engine})
                            chosen = "pypdf"
                        cut = trim_pdf(u["bytes"], page_idxs, chosen)
                        st.session_state.cut_pdfs[u["id"]] = cut
                        st.session_state.cut_meta[u["id"]] = {
                            "ranges": ranges,
                            "engine": chosen,
                            "created_at": now_iso(),
                            "pages_selected": len(page_idxs),
                            "sha256": sha256_bytes(cut),
                        }
                        log_event("trim", f"Trimmed {u['name']} via {chosen} ({len(page_idxs)} pages)", "INFO",
                                  meta={"upload_id": u["id"], **st.session_state.cut_meta[u["id"]]})
                        st.success("Trim successful.")
                    except Exception as e:
                        log_event("trim", f"Trim failed for {u['name']}: {e}", "ERROR", meta={"upload_id": u["id"]})
                        st.error(f"Trim failed: {e}")

            if u["id"] in st.session_state.cut_pdfs:
                cut = st.session_state.cut_pdfs[u["id"]]
                meta = st.session_state.cut_meta.get(u["id"], {})
                st.markdown(f"**{t('cut_pdf')}**  "
                            f"<span class='wow-badge'>engine: {meta.get('engine','')}</span> "
                            f"<span class='wow-badge'>ranges: {meta.get('ranges','')}</span> "
                            f"<span class='wow-badge'>sha256: {meta.get('sha256','')[:10]}…</span>",
                            unsafe_allow_html=True)
                c2 = st.columns([1.2, 1.2, 2.0])
                c2[0].download_button(
                    label=f"{t('download')} (cut PDF)",
                    data=cut,
                    file_name=f"cut_{u['name']}",
                    mime="application/pdf",
                    use_container_width=True,
                )
                if c2[1].button("Set as Active for Doc Prompting", key=f"setactive_{u['id']}"):
                    st.session_state.docprompt["active_upload_id"] = u["id"]
                    log_event("docprompt", f"Active cut PDF set: {u['name']}", "INFO", meta={"upload_id": u["id"]})
                    st.success("Active cut PDF set.")

    st.divider()
    with st.container(border=True):
        st.subheader("Consolidation (Text)")
        st.caption("Baseline text extraction consolidates cut PDFs (or original PDFs if not cut). OCR/multimodal extraction can be added.")
        if st.button("Build Consolidated Text Artifact", type="primary"):
            texts = []
            for u in st.session_state.uploads:
                pdfb = st.session_state.cut_pdfs.get(u["id"], u["bytes"])
                txt = extract_text_from_pdf(pdfb, max_pages=120)
                anchor = f"\n\n[[SOURCE_FILE={u['name']}|UPLOAD_ID={u['id']}|SHA256={sha256_bytes(pdfb)}]]\n"
                texts.append(anchor + txt)
            st.session_state.consolidated_text = "\n\n".join(texts).strip()
            log_event("consolidation", "Consolidated text artifact built.", "INFO",
                      meta={"chars": len(st.session_state.consolidated_text)})
            st.success("Consolidated artifact ready.")
        st.text_area("Consolidated Text (editable)", value=st.session_state.consolidated_text, height=260, key="consolidated_text")


# -----------------------------
# Tab: Direct Doc Prompting
# -----------------------------
def doc_prompt_tab():
    st.session_state.active_stage = "Direct Doc Prompting"
    wow_indicator()

    st.header(t("nav_docprompt"))

    active_id = st.session_state.docprompt.get("active_upload_id")
    if not active_id:
        st.info("Select an active cut PDF from Ingest & Trim (or set one here).")
        # allow selection
        ids = [u["id"] for u in st.session_state.uploads]
        if ids:
            names = {u["id"]: u["name"] for u in st.session_state.uploads}
            pick = st.selectbox("Select upload", ids, format_func=lambda x: names.get(x, x))
            if st.button("Set Active", type="primary"):
                st.session_state.docprompt["active_upload_id"] = pick
                log_event("docprompt", "Active document set from selector.", "INFO", meta={"upload_id": pick})
                st.rerun()
        return

    u = next((x for x in st.session_state.uploads if x["id"] == active_id), None)
    if not u:
        st.error("Active upload not found.")
        return

    pdfb = st.session_state.cut_pdfs.get(active_id, u["bytes"])
    with st.container(border=True):
        st.markdown(f"**Active Document:** {u['name']}  "
                    f"<span class='wow-badge'>bytes: {len(pdfb)/1024/1024:.1f} MB</span>",
                    unsafe_allow_html=True)

        cols = st.columns([1.2, 1.2, 1.0])
        model = cols[0].selectbox(t("model"), GEMINI_MODELS + OPENAI_MODELS + ANTHROPIC_MODELS + GROK_MODELS,
                                  index=0, key="docprompt_model")
        max_tokens = cols[1].number_input(t("max_tokens"), min_value=256, max_value=24000, value=DEFAULT_MAX_TOKENS, step=256)
        temperature = cols[2].slider(t("temperature"), 0.0, 1.0, float(DEFAULT_TEMPERATURE), 0.05)

        skill = st.text_area(t("skill"), value=st.session_state.docprompt.get("skill", DEFAULT_REG_SKILL), height=200)
        st.session_state.docprompt["skill"] = skill

        render = st.toggle("Render PDF preview", value=False)
        if render:
            render_pdf_inline(pdfb, height=520)

        # Extract baseline text context
        with st.expander("Extracted text context (baseline)"):
            txt = extract_text_from_pdf(pdfb, max_pages=80)
            st.write(f"Extracted characters: {len(txt)}")
            st.text_area("Extracted text (read-only snapshot)", value=txt[:200000], height=240, disabled=True)

        q = st.text_area(t("doc_question"), height=120)
        if st.button(t("run"), type="primary"):
            try:
                log_event("docprompt", "Doc prompting started.", "INFO", meta={"upload_id": active_id, "model": model})
                # Compose prompt with extracted text
                doc_txt = extract_text_from_pdf(pdfb, max_pages=120)
                system = skill
                user = f"""Question:
{q}

Document content (extracted text; may be incomplete if scanned):
{doc_txt}
"""
                res = ai_call(model, system=system, user=user, max_tokens=int(max_tokens), temperature=float(temperature))
                st.session_state.docprompt["last_output"] = res.text
                st.session_state.docprompt["history"].append({"q": q, "a": res.text, "model": model, "ts": now_iso()})
                record_telemetry(model, prompt_text=system + "\n\n" + user, result=res, kind="doc_prompt")
                st.success("Done.")
            except Exception as e:
                log_event("docprompt", f"Doc prompting failed: {e}", "ERROR")
                st.error(str(e))

        if st.session_state.docprompt.get("last_output"):
            st.subheader("Output")
            view = st.radio("View", ["Markdown", "Text"], horizontal=True, index=0)
            out = st.session_state.docprompt["last_output"]
            if view == "Markdown":
                st.markdown(out)
            else:
                st.text_area("Output", value=out, height=260)

            c = st.columns([1.2, 1.2, 2.0])
            if c[0].button("Save to Note Keeper"):
                st.session_state.notes["raw_input"] += "\n\n" + out
                log_event("notes", "Doc prompting output appended to Note Keeper raw input.", "INFO")
                st.success("Saved.")
            if c[1].button("Append to Agent Context"):
                st.session_state.agent_input_context += "\n\n" + out
                log_event("agents", "Doc prompting output appended to agent input context.", "INFO")
                st.success("Appended to context.")

    with st.expander("History"):
        st.json(st.session_state.docprompt.get("history", [])[-20:])


# -----------------------------
# Tab: Agent Orchestration
# -----------------------------
def agents_tab():
    st.session_state.active_stage = "Agent Orchestration"
    wow_indicator()

    st.header(t("nav_agents"))

    with st.container(border=True):
        st.subheader(t("agents_yaml"))
        default_raw = st.session_state.agents_yaml_raw or default_agents_yaml()
        raw = st.text_area("Edit agents.yaml", value=default_raw, height=220)
        col = st.columns([1, 1, 2])
        if col[0].button(t("load_agents"), type="primary"):
            try:
                st.session_state.agents_yaml_raw = raw
                agents = load_agents_yaml(raw)
                st.session_state.agents = agents
                log_event("agents", f"Loaded agents.yaml with {len(agents)} agents.", "INFO")
                st.success(f"Loaded {len(agents)} agents.")
            except Exception as e:
                log_event("agents", f"Failed to load agents.yaml: {e}", "ERROR")
                st.error(str(e))
        if col[1].button("Reset to Default"):
            st.session_state.agents_yaml_raw = default_agents_yaml()
            st.session_state.agents = load_agents_yaml(st.session_state.agents_yaml_raw)
            log_event("agents", "agents.yaml reset to default.", "WARNING")
            st.info("Reset.")
        st.caption("Tip: per-agent overrides are available before each run.")

    if not st.session_state.agents:
        st.info("Load agents.yaml to start.")
        return

    # Input context
    with st.container(border=True):
        st.subheader("Agent Input Context (editable)")
        st.caption("This is the context passed into Agent 1. After each agent, you can edit and commit output to become the next input.")
        base = st.text_area("Context", value=st.session_state.agent_input_context or st.session_state.consolidated_text,
                            height=220, key="agent_input_context")
        st.session_state.agent_input_context = base

    # Run sequentially, one by one
    for idx, agent in enumerate(st.session_state.agents):
        with st.container(border=True):
            st.markdown(f"### {idx+1}. {agent['name']}  <span class='wow-badge'>{agent['id']}</span>", unsafe_allow_html=True)

            # Override controls
            cols = st.columns([1.4, 1.0, 1.0])
            model = cols[0].selectbox(t("model"), ALL_MODELS,
                                      index=ALL_MODELS.index(agent["model"]) if agent["model"] in ALL_MODELS else 0,
                                      key=f"agent_model_{idx}")
            max_tokens = cols[1].number_input(t("max_tokens"), min_value=256, max_value=24000,
                                              value=int(agent.get("max_tokens", DEFAULT_MAX_TOKENS)), step=256,
                                              key=f"agent_maxtok_{idx}")
            temperature = cols[2].slider(t("temperature"), 0.0, 1.0, float(agent.get("temperature", DEFAULT_TEMPERATURE)),
                                         0.05, key=f"agent_temp_{idx}")

            system = st.text_area("System prompt", value=agent.get("system", ""), height=120, key=f"agent_sys_{idx}")
            user_prompt = st.text_area("User prompt", value=agent.get("user", ""), height=120, key=f"agent_user_{idx}")

            # Run button
            run_col = st.columns([1.0, 2.0])
            if run_col[0].button(f"{t('run')} Agent {idx+1}", type="primary", key=f"run_agent_{idx}"):
                try:
                    st.session_state.active_stage = f"Agent {idx+1}: running"
                    log_event("agents", f"Agent {idx+1} started: {agent['name']}", "INFO",
                              meta={"agent_index": idx, "model": model, "max_tokens": int(max_tokens)})

                    input_ctx = st.session_state.agent_input_context
                    prompt_user = f"""{user_prompt}

INPUT CONTEXT:
{input_ctx}
"""
                    res = ai_call(model, system=system, user=prompt_user, max_tokens=int(max_tokens), temperature=float(temperature))
                    st.session_state.agent_outputs_raw[idx] = res.text
                    record_telemetry(model, prompt_text=system + "\n\n" + prompt_user, result=res, kind=f"agent_{idx+1}")

                    run_record = {
                        "ts": now_iso(),
                        "agent_index": idx,
                        "agent_id": agent["id"],
                        "agent_name": agent["name"],
                        "model": model,
                        "max_tokens": int(max_tokens),
                        "temperature": float(temperature),
                        "raw_len": len(res.text),
                    }
                    st.session_state.agent_runs.append(run_record)
                    log_event("agents", f"Agent {idx+1} completed.", "INFO", meta=run_record)
                    st.success("Agent completed.")
                except Exception as e:
                    log_event("agents", f"Agent {idx+1} failed: {e}", "ERROR")
                    st.error(str(e))
                finally:
                    st.session_state.active_stage = "Agent Orchestration"

            # Output + editable handoff
            raw_out = st.session_state.agent_outputs_raw.get(idx)
            if raw_out:
                st.subheader("Agent Output")
                view = st.radio("View mode", ["Markdown", "Text"], horizontal=True, key=f"view_{idx}")
                if view == "Markdown":
                    st.markdown(raw_out)
                else:
                    st.text_area("Raw output", value=raw_out, height=240, key=f"rawout_{idx}")

                st.markdown("**Edit & Commit (becomes input for next agent)**")
                committed_default = st.session_state.agent_outputs_committed.get(idx, raw_out)
                committed = st.text_area("Committed output", value=committed_default, height=240, key=f"commitout_{idx}")

                if st.button(t("commit"), key=f"commitbtn_{idx}", type="primary"):
                    st.session_state.agent_outputs_committed[idx] = committed
                    st.session_state.agent_input_context = committed
                    log_event("agents", f"Committed output of Agent {idx+1} as next input.", "INFO",
                              meta={"agent_index": idx, "committed_len": len(committed)})
                    st.success("Committed as next input context.")


    st.divider()
    with st.container(border=True):
        st.subheader(t("macro_summary"))
        cols = st.columns([1.6, 1.0, 1.0])
        model = cols[0].selectbox(t("model"), ALL_MODELS, index=ALL_MODELS.index("gpt-4.1-mini") if "gpt-4.1-mini" in ALL_MODELS else 0,
                                  key="macro_model")
        max_tokens = cols[1].number_input(t("max_tokens"), min_value=1024, max_value=24000, value=DEFAULT_MAX_TOKENS, step=256,
                                          key="macro_maxtok")
        temperature = cols[2].slider(t("temperature"), 0.0, 1.0, 0.2, 0.05, key="macro_temp")

        if st.button(t("make_summary"), type="primary"):
            try:
                st.session_state.active_stage = "Macro Summary: running"
                ctx = st.session_state.agent_input_context or st.session_state.consolidated_text
                system = "You are a senior FDA 510(k) reviewer producing a defensible review artifact."
                user = f"""{MACRO_SUMMARY_PROMPT}

CONTEXT:
{ctx}
"""
                res = ai_call(model, system=system, user=user, max_tokens=int(max_tokens), temperature=float(temperature))
                record_telemetry(model, prompt_text=system + "\n\n" + user, result=res, kind="macro_summary")
                ver = {"id": str(uuid.uuid4()), "ts": now_iso(), "model": model, "text": res.text}
                st.session_state.macro_versions.insert(0, ver)
                log_event("macro", "Macro summary generated (new version).", "INFO",
                          meta={"version_id": ver["id"], "len": len(ver["text"])})
                st.success("Macro summary created.")
            except Exception as e:
                log_event("macro", f"Macro summary failed: {e}", "ERROR")
                st.error(str(e))
            finally:
                st.session_state.active_stage = "Agent Orchestration"

        if st.session_state.macro_versions:
            st.subheader("Macro Summary Versions")
            v = st.session_state.macro_versions[0]
            st.caption(f"Latest: {v['ts']} · {v['model']} · chars={len(v['text'])}")
            st.markdown(v["text"])


# -----------------------------
# Tab: WOW Modules
# -----------------------------
def wow_modules_tab():
    st.session_state.active_stage = "WOW Modules"
    wow_indicator()

    st.header(t("nav_wow"))

    if not st.session_state.macro_versions:
        st.warning("Generate a Macro Summary first (Agent Orchestration tab). WOW modules can run with less context, but work best with a macro summary.")
    macro = st.session_state.macro_versions[0]["text"] if st.session_state.macro_versions else ""
    consolidated = st.session_state.consolidated_text or st.session_state.agent_input_context

    with st.container(border=True):
        cols = st.columns([1.4, 1.0, 1.0])
        model = cols[0].selectbox(t("model"), ALL_MODELS, index=0, key="wow_model")
        max_tokens = cols[1].number_input(t("max_tokens"), 1024, 24000, DEFAULT_MAX_TOKENS, 256, key="wow_maxtok")
        temperature = cols[2].slider(t("temperature"), 0.0, 1.0, 0.2, 0.05, key="wow_temp")

        for (name, prompt) in WOW_MODULES:
            with st.expander(name, expanded=False):
                st.caption("Click Run to generate/update this module output.")
                if st.button(f"{t('run')} · {name}", key=f"run_wow_{name}", type="primary"):
                    try:
                        st.session_state.active_stage = f"WOW: {name} running"
                        system = "You are a regulatory intelligence module producing audit-friendly outputs."
                        user = f"""MODULE: {name}

INSTRUCTIONS:
{prompt}

MACRO SUMMARY (if any):
{macro}

CONSOLIDATED CONTEXT:
{consolidated}
"""
                        res = ai_call(model, system=system, user=user, max_tokens=int(max_tokens), temperature=float(temperature))
                        record_telemetry(model, prompt_text=system + "\n\n" + user, result=res, kind="wow_module")
                        st.session_state.wow_outputs[name] = res.text
                        log_event("wow", f"WOW module completed: {name}", "INFO", meta={"module": name, "len": len(res.text)})
                        st.success("Updated.")
                    except Exception as e:
                        log_event("wow", f"WOW module failed ({name}): {e}", "ERROR")
                        st.error(str(e))
                    finally:
                        st.session_state.active_stage = "WOW Modules"

                out = st.session_state.wow_outputs.get(name)
                if out:
                    view = st.radio("View", ["Markdown", "Text"], horizontal=True, key=f"wow_view_{name}")
                    if view == "Markdown":
                        st.markdown(out)
                    else:
                        st.text_area("Output", value=out, height=240, key=f"wow_txt_{name}")


# -----------------------------
# Tab: AI Note Keeper
# -----------------------------
def highlight_keywords_md(md: str, keywords: List[str], color: str) -> str:
    # Simple safe highlighting via HTML mark; Streamlit markdown allows unsafe HTML if enabled.
    # We'll wrap keywords in <mark> with style; avoid regex injection.
    if not keywords:
        return md
    # Create legend
    legend = f"\n\n---\n**Keyword Highlight Legend**: <mark style='background:{color}; padding:2px 6px; border-radius:6px;'>highlight</mark>\n"
    out = md
    for kw in keywords:
        kw2 = kw.strip()
        if not kw2:
            continue
        pattern = re.escape(kw2)
        out = re.sub(pattern, lambda m: f"<mark style='background:{color}; padding:2px 6px; border-radius:6px;'>{m.group(0)}</mark>",
                     out, flags=re.IGNORECASE)
    return out + legend


def notes_tab():
    st.session_state.active_stage = "AI Note Keeper"
    wow_indicator()

    st.header(t("nav_notes"))

    with st.container(border=True):
        cols = st.columns([1.4, 1.0, 1.0])
        model = cols[0].selectbox(t("model"), ALL_MODELS, index=0, key="note_model")
        max_tokens = cols[1].number_input(t("max_tokens"), 512, 24000, DEFAULT_MAX_TOKENS, 256, key="note_maxtok")
        temperature = cols[2].slider(t("temperature"), 0.0, 1.0, 0.2, 0.05, key="note_temp")

        st.session_state.notes["raw_input"] = st.text_area(
            "Paste notes (text or markdown)",
            value=st.session_state.notes.get("raw_input", ""),
            height=200,
        )

        if st.button(t("transform_note"), type="primary"):
            try:
                st.session_state.active_stage = "Note Keeper: organizing"
                system = "You are an expert regulatory note organizer. Do not fabricate."
                user = f"""{NOTE_ORGANIZER_PROMPT}

INPUT NOTES:
{st.session_state.notes["raw_input"]}
"""
                res = ai_call(model, system=system, user=user, max_tokens=int(max_tokens), temperature=float(temperature))
                record_telemetry(model, prompt_text=system + "\n\n" + user, result=res, kind="note_organize")
                st.session_state.notes["organized_md"] = res.text
                ver = {"id": str(uuid.uuid4()), "ts": now_iso(), "md": res.text}
                st.session_state.notes["versions"].insert(0, ver)
                log_event("notes", "Note organized into markdown (new version).", "INFO", meta={"version_id": ver["id"]})
                st.success("Organized markdown created.")
            except Exception as e:
                log_event("notes", f"Note organization failed: {e}", "ERROR")
                st.error(str(e))
            finally:
                st.session_state.active_stage = "AI Note Keeper"

    if st.session_state.notes.get("organized_md"):
        with st.container(border=True):
            st.subheader("Organized Note (Editable)")
            view = st.radio("View", ["Markdown", "Text"], horizontal=True, key="note_view")
            md = st.text_area("Markdown", value=st.session_state.notes["organized_md"], height=280, key="note_md_edit")
            st.session_state.notes["organized_md"] = md
            if view == "Markdown":
                st.markdown(md, unsafe_allow_html=True)
            else:
                st.text_area("Text view", value=md, height=240)

            c = st.columns([1.2, 1.2, 2.0])
            if c[0].button("Append to Agent Context", type="primary"):
                st.session_state.agent_input_context += "\n\n" + md
                log_event("notes", "Organized note appended to agent context.", "INFO")
                st.success("Appended.")

            if c[1].button("Save Version Snapshot"):
                ver = {"id": str(uuid.uuid4()), "ts": now_iso(), "md": md}
                st.session_state.notes["versions"].insert(0, ver)
                log_event("notes", "Note version snapshot saved.", "INFO", meta={"version_id": ver["id"]})
                st.success("Saved.")

    # AI Magics
    with st.container(border=True):
        st.subheader(t("ai_magics"))
        st.caption("One-click enhancements applied to the organized markdown.")
        cols = st.columns([1.4, 1.0, 1.0])
        model = cols[0].selectbox(t("model"), ALL_MODELS, index=0, key="magic_model")
        max_tokens = cols[1].number_input(t("max_tokens"), 512, 24000, 6000, 256, key="magic_maxtok")
        temperature = cols[2].slider(t("temperature"), 0.0, 1.0, 0.2, 0.05, key="magic_temp")

        magic = st.selectbox("Select Magic", [
            "AI Formatting (Regulatory Markdown)",
            "AI Keywords Highlighter (Color-Selectable)",
            "AI Executive Brief (1-page)",
            "AI Action Items & Questions Generator",
            "AI Terminology Harmonizer (EN/zh-TW aware)",
            "AI Evidence-to-Note Binder",
        ])

        if magic == "AI Keywords Highlighter (Color-Selectable)":
            kw = st.text_input(t("keyword"), value="sterilization, biocompatibility, cybersecurity")
            color = st.color_picker(t("color"), value="#FDE047")
            if st.button(t("apply"), type="primary"):
                kws = [x.strip() for x in kw.split(",")]
                st.session_state.notes["organized_md"] = highlight_keywords_md(
                    st.session_state.notes.get("organized_md", ""),
                    kws,
                    color,
                )
                log_event("notes", "Keyword highlighting applied.", "INFO", meta={"keywords": kws, "color": color})
                st.success("Applied.")
        else:
            if st.button(t("apply"), type="primary"):
                try:
                    st.session_state.active_stage = f"Note Magic: {magic}"
                    system = "You are a regulatory writing assistant. Do not invent facts."
                    md = st.session_state.notes.get("organized_md", "")
                    if not md.strip():
                        st.warning("Organize a note first.")
                    else:
                        user = f"""Apply the following transformation to the markdown note.

MAGIC:
{magic}

NOTE (Markdown):
{md}
"""
                        res = ai_call(model, system=system, user=user, max_tokens=int(max_tokens), temperature=float(temperature))
                        record_telemetry(model, prompt_text=system + "\n\n" + user, result=res, kind="note_magic")
                        st.session_state.notes["organized_md"] = res.text
                        log_event("notes", f"Applied note magic: {magic}", "INFO")
                        st.success("Applied.")
                except Exception as e:
                    log_event("notes", f"Note magic failed: {e}", "ERROR")
                    st.error(str(e))
                finally:
                    st.session_state.active_stage = "AI Note Keeper"

    with st.expander("Note Versions"):
        st.json(st.session_state.notes.get("versions", [])[:20])


# -----------------------------
# Tab: Export Center
# -----------------------------
def export_center_tab():
    st.session_state.active_stage = "Export Center"
    wow_indicator()

    st.header(t("nav_export"))

    with st.container(border=True):
        st.subheader("What will be included")
        st.write("- Consolidated text artifact (editable final state)")
        st.write("- Cut PDFs (if generated)")
        st.write("- Agent run outputs (raw + committed)")
        st.write("- Macro summary versions")
        st.write("- WOW module outputs")
        st.write("- Note Keeper organized markdown + versions")
        st.write("- Sanitized logs + telemetry")

        include_hashes = st.toggle("Include SHA-256 hashes manifest", value=True)
        if st.button(t("export_zip"), type="primary"):
            zbytes = build_export_zip(include_hashes=include_hashes)
            st.download_button(
                "Download export_bundle.zip",
                data=zbytes,
                file_name="export_bundle.zip",
                mime="application/zip",
            )
            log_event("export", "Export bundle built.", "INFO", meta={"bytes": len(zbytes)})


def build_export_zip(include_hashes: bool = True) -> bytes:
    mem = io.BytesIO()
    manifest = {}

    def write_file(z: zipfile.ZipFile, path: str, data: bytes):
        z.writestr(path, data)
        if include_hashes:
            manifest[path] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # consolidated
        cons = (st.session_state.consolidated_text or "").encode("utf-8")
        write_file(z, "artifacts/consolidated_text.txt", cons)

        # uploads metadata (hashes only; not including original PDFs by default to reduce sensitivity)
        uploads_meta = []
        for u in st.session_state.uploads:
            uploads_meta.append({k: u.get(k) for k in ["id", "name", "page_count", "sha256", "uploaded_at"]})
        write_file(z, "artifacts/uploads_registry.json", json.dumps(uploads_meta, indent=2).encode("utf-8"))

        # cut PDFs
        for uid, b in st.session_state.cut_pdfs.items():
            name = next((u["name"] for u in st.session_state.uploads if u["id"] == uid), uid)
            write_file(z, f"artifacts/cut_pdfs/{uid}_{name}", b)

        # agents
        write_file(z, "agents/agents.yaml", (st.session_state.agents_yaml_raw or default_agents_yaml()).encode("utf-8"))
        write_file(z, "agents/agent_runs.json", json.dumps(st.session_state.agent_runs, indent=2).encode("utf-8"))
        write_file(z, "agents/agent_outputs_raw.json", json.dumps(st.session_state.agent_outputs_raw, indent=2).encode("utf-8"))
        write_file(z, "agents/agent_outputs_committed.json", json.dumps(st.session_state.agent_outputs_committed, indent=2).encode("utf-8"))

        # macro
        write_file(z, "macro/macro_versions.json", json.dumps(st.session_state.macro_versions, indent=2).encode("utf-8"))
        if st.session_state.macro_versions:
            write_file(z, "macro/latest_macro_summary.md", st.session_state.macro_versions[0]["text"].encode("utf-8"))

        # wow outputs
        write_file(z, "wow/wow_outputs.json", json.dumps(st.session_state.wow_outputs, indent=2).encode("utf-8"))

        # notes
        write_file(z, "notes/organized_note.md", (st.session_state.notes.get("organized_md") or "").encode("utf-8"))
        write_file(z, "notes/note_versions.json", json.dumps(st.session_state.notes.get("versions", []), indent=2).encode("utf-8"))

        # logs + telemetry
        logs = sanitize_logs_for_export(st.session_state.logs)
        write_file(z, "logs/live_log_sanitized.json", json.dumps(logs, indent=2).encode("utf-8"))
        write_file(z, "logs/telemetry.json", json.dumps(st.session_state.telemetry, indent=2).encode("utf-8"))

        if include_hashes:
            write_file(z, "manifest/hashes.json", json.dumps(manifest, indent=2).encode("utf-8"))

    return mem.getvalue()


# -----------------------------
# App entry
# -----------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    ss_init()
    apply_style()
    sidebar_controls()

    st.title(APP_TITLE)
    st.caption("Regulatory Command Center — Nordic WOW Edition (Painter Studio + Note Keeper)")

    # Top-level navigation tabs
    tabs = st.tabs([
        t("nav_ingest"),
        t("nav_docprompt"),
        t("nav_agents"),
        t("nav_wow"),
        t("nav_notes"),
        t("nav_dashboard"),
        t("nav_logs"),
        t("nav_export"),
        t("nav_settings"),
    ])

    with tabs[0]:
        ingest_trim_tab()
    with tabs[1]:
        doc_prompt_tab()
    with tabs[2]:
        agents_tab()
    with tabs[3]:
        wow_modules_tab()
    with tabs[4]:
        notes_tab()
    with tabs[5]:
        wow_dashboard()
    with tabs[6]:
        live_log_view()
    with tabs[7]:
        export_center_tab()
    with tabs[8]:
        providers_panel()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Last-resort guard to keep UI alive
        log_event("fatal", f"Unhandled error: {e}", "CRITICAL")
        st.exception(e)
