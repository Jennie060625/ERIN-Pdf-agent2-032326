from __future__ import annotations

import os
import io
import re
import gc
import time
import json
import math
import uuid
import yaml
import base64
import hashlib
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple, Set

import streamlit as st

# Optional deps (graceful degradation)
try:
    import pandas as pd
except Exception:
    pd = None

try:
    from pydantic import BaseModel, Field
except Exception:
    BaseModel = object
    Field = lambda *a, **k: None

try:
    from rapidfuzz import fuzz, process
except Exception:
    fuzz = None
    process = None

try:
    from PyPDF2 import PdfReader, PdfWriter
except Exception:
    PdfReader = None
    PdfWriter = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import plotly.graph_objects as go
except Exception:
    go = None

# LLM provider SDKs (optional; show guidance if missing)
try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import anthropic
except Exception:
    anthropic = None


# -----------------------------
# 0) App metadata / constants
# -----------------------------
APP_VERSION = "2.7"
APP_TITLE = f"FDA 510(k) Review Studio v{APP_VERSION} — Regulatory Command Center: Nordic WOW"
TZ_NAME = "Asia/Taipei"

PROVIDERS = ["openai", "gemini", "anthropic", "grok"]

OPENAI_MODELS = ["gpt-4o-mini", "gpt-4.1-mini"]
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]
ANTHROPIC_MODELS = ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]
GROK_MODELS = ["grok-4-fast-reasoning", "grok-3-mini"]

SUPPORTED_MODELS = {
    "openai": OPENAI_MODELS,
    "gemini": GEMINI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "grok": GROK_MODELS,
}

DEFAULT_MAX_TOKENS = 12000
DEFAULT_TEMPERATURE = 0.2

# Reserved semantic color for critical insights/deficiencies
RESERVED_CORAL = "#FF6F61"

# Nordic surfaces (base); accent comes from painter style
NORDIC_LIGHT = {
    "bg": "#F6F7F9",
    "surface": "#FFFFFF",
    "surface_2": "#F0F2F5",
    "text": "#0B1220",
    "muted": "#5B667A",
    "border": "rgba(20,28,40,0.10)",
    "shadow": "rgba(20,28,40,0.08)",
}
NORDIC_DARK = {
    "bg": "#0B0F16",
    "surface": "#0F1622",
    "surface_2": "#101B2A",
    "text": "#EAF0FF",
    "muted": "#A5B3CC",
    "border": "rgba(234,240,255,0.10)",
    "shadow": "rgba(0,0,0,0.35)",
}

# 20 painter accents (kept); in Nordic UI, used sparingly as highlight/accent.
PAINTER_STYLES = {
    "van_gogh": {"name": "Van Gogh", "accent": "#F4D03F"},
    "monet": {"name": "Monet", "accent": "#76D7C4"},
    "picasso": {"name": "Picasso", "accent": "#AF7AC5"},
    "da_vinci": {"name": "Da Vinci", "accent": "#D4AC0D"},
    "hokusai": {"name": "Hokusai", "accent": "#3498DB"},
    "kahlo": {"name": "Frida Kahlo", "accent": "#E74C3C"},
    "matisse": {"name": "Matisse", "accent": "#F39C12"},
    "warhol": {"name": "Warhol", "accent": "#FF2D95"},
    "turner": {"name": "Turner", "accent": "#F5B041"},
    "rembrandt": {"name": "Rembrandt", "accent": "#A04000"},
    "klimt": {"name": "Klimt", "accent": "#D4AF37"},
    "dali": {"name": "Dali", "accent": "#1ABC9C"},
    "pollock": {"name": "Pollock", "accent": "#E67E22"},
    "cezanne": {"name": "Cezanne", "accent": "#27AE60"},
    "vermeer": {"name": "Vermeer", "accent": "#2E86C1"},
    "goya": {"name": "Goya", "accent": "#922B21"},
    "cyberpunk": {"name": "Cyberpunk", "accent": "#00E5FF"},
    "ukiyo_e": {"name": "Ukiyo-e", "accent": "#5DADE2"},
    "surreal": {"name": "Surreal", "accent": "#9B59B6"},
    "minimal": {"name": "Minimal", "accent": "#95A5A6"},
}

OCR_PROMPT_TEMPLATES = {
    "General (tables+text)": "Extract all text. Reconstruct all tables in GitHub-flavored Markdown. Preserve headings. Ignore headers/footers/watermarks. No commentary; output only Markdown.",
    "Tables-first": "Focus on accurate table reconstruction. For each table: output a Markdown table with correct columns/rows. Preserve units and footnotes. Ignore decorative lines. Output only Markdown.",
    "Specs-first": "Extract technical specifications (dimensions, materials, tolerances, electrical ratings). Normalize units. Use Markdown headings + bullet lists + spec tables. Output only Markdown.",
    "Labeling/IFU": "Extract labeling, IFU, contraindications, warnings, precautions, indications, and instructions. Preserve section order. Output only Markdown.",
    "Software/Cybersecurity": "Extract software architecture, versioning, cybersecurity controls, SBOM mentions, threat modeling, patching, authentication, logging, and encryption. Output only Markdown.",
    "Sterilization/Packaging": "Extract sterilization method, SAL, validation standards, packaging configuration, shelf-life claims, storage conditions, and integrity testing. Output only Markdown.",
}

LANG = {
    "en": {
        "mode": "Mode",
        "command_center": "Command Center",
        "note_keeper": "AI Note Keeper",
        "theme": "Theme",
        "light": "Light",
        "dark": "Dark",
        "language": "Language",
        "painter_style": "Painter Style",
        "jackpot": "Jackpot",
        "api_keys": "API Keys",
        "managed_by_system": "Managed by System",
        "missing_key": "Missing",
        "session_key": "Session Key",
        "danger_zone": "Danger Zone",
        "total_purge": "Total Purge",
        "datasets": "Datasets",
        "search": "Search",
        "ingestion": "Ingestion",
        "upload_pdfs": "Upload PDFs",
        "paths": "File paths (optional)",
        "register_files": "Register Files",
        "queue": "File Queue",
        "trim": "Trim",
        "global_range": "Global page range",
        "execute_trim": "Execute Trim",
        "ocr": "OCR",
        "ocr_mode": "OCR Mode",
        "python_pack": "Python Pack (PyPDF2 + Tesseract)",
        "llm_ocr": "LLM OCR (Gemini multimodal)",
        "ocr_prompt": "OCR Prompt",
        "execute_ocr": "Execute OCR",
        "consolidated": "Consolidated OCR Markdown",
        "agent_orchestration": "Agent Orchestration",
        "agents_yaml": "agents.yaml",
        "upload_yaml": "Upload agents.yaml",
        "download_yaml": "Download agents.yaml",
        "standardize_yaml": "Standardize YAML",
        "validate_yaml": "Validate YAML",
        "macro_summary": "Macro Summary",
        "persistent_prompt": "Persistent Prompt",
        "run_persistent_prompt": "Run Persistent Prompt",
        "dynamic_skill": "Dynamic Skill Execution",
        "skill_desc": "Skill Description",
        "run_skill": "Execute Skill on Summary",
        "wow_ai": "WOW AI",
        "evidence_mapper": "Evidence Mapper",
        "consistency_guardian": "Consistency Guardian",
        "risk_radar": "Regulatory Risk Radar",
        "rta_gatekeeper": "RTA Gatekeeper",
        "claims_inspector": "Labeling & Claims Inspector",
        "dashboards": "Dashboards",
        "mission_control": "Mission Control",
        "timeline": "Timeline / DAG",
        "logs": "Session Logs",
        "intel_board": "Regulatory Intelligence Board",
        "export": "Export",
        "low_resource": "Low-resource mode",
    },
    "zh-TW": {
        "mode": "模式",
        "command_center": "指揮中心",
        "note_keeper": "AI 筆記管家",
        "theme": "主題",
        "light": "亮色",
        "dark": "暗色",
        "language": "語言",
        "painter_style": "畫家風格",
        "jackpot": "隨機",
        "api_keys": "API 金鑰",
        "managed_by_system": "系統管理",
        "missing_key": "缺少",
        "session_key": "本次會話金鑰",
        "danger_zone": "危險區",
        "total_purge": "完全清除",
        "datasets": "資料集",
        "search": "搜尋",
        "ingestion": "匯入",
        "upload_pdfs": "上傳 PDF",
        "paths": "檔案路徑（選用）",
        "register_files": "登錄檔案",
        "queue": "檔案佇列",
        "trim": "裁切",
        "global_range": "全域頁碼範圍",
        "execute_trim": "執行裁切",
        "ocr": "OCR",
        "ocr_mode": "OCR 模式",
        "python_pack": "Python 套件（PyPDF2 + Tesseract）",
        "llm_ocr": "LLM OCR（Gemini 多模態）",
        "ocr_prompt": "OCR 提示詞",
        "execute_ocr": "執行 OCR",
        "consolidated": "合併 OCR Markdown",
        "agent_orchestration": "代理人編排",
        "agents_yaml": "agents.yaml",
        "upload_yaml": "上傳 agents.yaml",
        "download_yaml": "下載 agents.yaml",
        "standardize_yaml": "標準化 YAML",
        "validate_yaml": "驗證 YAML",
        "macro_summary": "巨集摘要",
        "persistent_prompt": "持續提示",
        "run_persistent_prompt": "執行持續提示",
        "dynamic_skill": "動態技能執行",
        "skill_desc": "技能描述",
        "run_skill": "對摘要執行技能",
        "wow_ai": "WOW AI",
        "evidence_mapper": "證據映射",
        "consistency_guardian": "一致性守護",
        "risk_radar": "法規風險雷達",
        "rta_gatekeeper": "RTA 守門員",
        "claims_inspector": "標示與主張檢查器",
        "dashboards": "儀表板",
        "mission_control": "任務控制台",
        "timeline": "時間線 / DAG",
        "logs": "會話紀錄",
        "intel_board": "法規智慧看板",
        "export": "匯出",
        "low_resource": "低資源模式",
    },
}


# -----------------------------
# 1) Utilities
# -----------------------------
def now_taipei_str() -> str:
    t = dt.datetime.utcnow() + dt.timedelta(hours=8)
    return t.strftime("%Y-%m-%d %H:%M:%S") + " (Asia/Taipei)"


def t(key: str) -> str:
    lang = st.session_state.get("ui.lang", "en")
    return LANG.get(lang, LANG["en"]).get(key, key)


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def safe_event(component: str, severity: str, message: str, meta: Optional[dict] = None):
    if "obs.events" not in st.session_state:
        st.session_state["obs.events"] = []
    st.session_state["obs.events"].append(
        {"ts": now_taipei_str(), "component": component, "severity": severity, "message": message, "meta": meta or {}}
    )


def bump_metric(key: str, delta: float = 1.0):
    m = st.session_state.setdefault("obs.metrics", {})
    m[key] = m.get(key, 0.0) + delta


def set_pipeline_state(node: str, status: str, detail: str = ""):
    ps = st.session_state.setdefault("obs.pipeline_state", {})
    obj = ps.setdefault(node, {"status": "idle", "last_update": None, "detail": ""})
    obj["status"] = status
    obj["last_update"] = now_taipei_str()
    obj["detail"] = detail


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        n /= 1024.0
        if n < 1024:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"


def mem_estimate_bytes() -> int:
    total = 0
    reg = st.session_state.get("docs.registry", [])
    for f in reg:
        b = f.get("bytes")
        if isinstance(b, (bytes, bytearray)):
            total += len(b)
    trim = st.session_state.get("docs.trim.outputs", {})
    for b in trim.values():
        if isinstance(b, (bytes, bytearray)):
            total += len(b)
    total += len(st.session_state.get("docs.consolidated_markdown", "") or "")
    return total


def parse_page_ranges(range_str: str) -> List[int]:
    if not range_str or not range_str.strip():
        return []
    parts = [p.strip() for p in range_str.split(",") if p.strip()]
    pages = set()
    for p in parts:
        if "-" in p:
            a, b = p.split("-", 1)
            a = int(a.strip())
            b = int(b.strip())
            if a <= 0 or b <= 0:
                raise ValueError("Page numbers must be >= 1.")
            if b < a:
                a, b = b, a
            for k in range(a, b + 1):
                pages.add(k - 1)
        else:
            k = int(p)
            if k <= 0:
                raise ValueError("Page numbers must be >= 1.")
            pages.add(k - 1)
    return sorted(pages)


def simple_diff(a: str, b: str, max_lines: int = 250) -> str:
    import difflib

    a_lines = (a or "").splitlines()
    b_lines = (b or "").splitlines()
    diff = difflib.unified_diff(a_lines, b_lines, lineterm="", fromfile="prev", tofile="current")
    out = "\n".join(list(diff)[:max_lines])
    return "```diff\n" + (out if out else "(no diff)") + "\n```"


def markdown_highlight_keywords(md: str, keywords_to_color: Dict[str, str]) -> str:
    if not md:
        return md
    # user palette (longest-first)
    items = sorted((keywords_to_color or {}).items(), key=lambda kv: len(kv[0]), reverse=True)
    out = md
    for kw, color in items:
        if not kw:
            continue
        if (color or "").strip().lower() == RESERVED_CORAL.lower():
            continue
        pattern = re.compile(rf"(?i)\b({re.escape(kw)})\b")
        out = pattern.sub(rf"<span style='color:{color}; font-weight:700;'>\1</span>", out)

    critical = ["warning", "recall", "latex", "implantable", "steril", "biocompat", "MDR", "adverse", "cybersecurity"]
    for kw in critical:
        pattern = re.compile(rf"(?i)\b({re.escape(kw)})\b")
        out = pattern.sub(rf"<span style='color:{RESERVED_CORAL}; font-weight:800;'>\1</span>", out)
    return out


# -----------------------------
# 2) Canonical Agent Schema
# -----------------------------
class AgentSpec(BaseModel):
    id: str
    name: str
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=DEFAULT_TEMPERATURE)
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS)
    system_prompt: str = Field(default="")
    user_prompt: str = Field(default="")
    expected_format: str = Field(default="markdown")


class AgentsConfig(BaseModel):
    agents: List[AgentSpec]


DEFAULT_AGENTS_YAML = """\
agents:
  - id: "a1"
    name: "Submission Structurer"
    provider: "openai"
    model: "gpt-4o-mini"
    temperature: 0.2
    max_tokens: 12000
    system_prompt: |
      You are a senior FDA 510(k) reviewer. Produce structured, factual analysis. Do not invent data.
      Output in Markdown with clear headings.
    user_prompt: |
      Convert the provided OCR text into a structured 510(k) review outline: Device Description, Indications for Use,
      Predicate Devices, Substantial Equivalence, Performance Testing, Biocompatibility, Sterilization/Shelf-life,
      Software/Cybersecurity (if relevant), Labeling, and Key Open Questions.
  - id: "a2"
    name: "Macro Summary (3000–4000 words)"
    provider: "openai"
    model: "gpt-4.1-mini"
    temperature: 0.2
    max_tokens: 12000
    system_prompt: |
      You are a regulatory writing engine. Be exhaustive, factual, and analytical.
      IMPORTANT: Target 3000 to 4000 words. Use Markdown. Include a clear Executive Summary and sectioned analysis.
    user_prompt: |
      Write a comprehensive 3000–4000 word FDA-style analytical review report based strictly on the provided content.
      Include a final section: "Reviewer Follow-up Questions".
"""


# -----------------------------
# 3) State init / purge
# -----------------------------
def init_state():
    ss = st.session_state

    ss.setdefault("ui.mode", "command_center")
    ss.setdefault("ui.theme", "dark")
    ss.setdefault("ui.lang", "en")
    ss.setdefault("ui.painter_style", "minimal")
    ss.setdefault("ui.jackpot_seed", 0)
    ss.setdefault("ui.low_resource_mode", False)
    ss.setdefault("ui.preserve_prefs_on_purge", True)

    # Keys (session only; env handled separately)
    ss.setdefault("keys.openai", None)
    ss.setdefault("keys.gemini", None)
    ss.setdefault("keys.anthropic", None)
    ss.setdefault("keys.grok", None)

    # Datasets
    ss.setdefault("data.loaded", False)
    ss.setdefault("data.counts", {"510k": 0, "mdr": 0, "gudid": 0, "recall": 0})
    ss.setdefault("data.last_query", "")
    ss.setdefault("data.last_results", {})
    ss.setdefault("data.device_view", {})

    # Docs
    ss.setdefault("docs.registry", [])
    ss.setdefault("docs.queue.selected_ids", set())
    ss.setdefault("docs.trim.global_range", "1-5")
    ss.setdefault("docs.trim.per_file_override", {})
    ss.setdefault("docs.trim.outputs", {})

    ss.setdefault("docs.ocr.mode", "python_pack")
    ss.setdefault("docs.ocr.model", GEMINI_MODELS[0])
    ss.setdefault("docs.ocr.prompt_global", OCR_PROMPT_TEMPLATES["General (tables+text)"])
    ss.setdefault("docs.ocr.prompt_per_file", {})  # file_id -> prompt override
    ss.setdefault("docs.ocr.outputs_by_file", {})
    ss.setdefault("docs.consolidated_markdown", "")
    ss.setdefault("docs.consolidated_anchors", {})
    ss.setdefault("consolidated.artifact_id", None)

    # Artifacts
    ss.setdefault("artifacts", {})

    # agents.yaml management
    ss.setdefault("agents.yaml.raw", "")
    ss.setdefault("agents.yaml.validated", None)
    ss.setdefault("agents.yaml.original_upload", None)
    ss.setdefault("agents.yaml.standardize_report", "")
    ss.setdefault("agents.last_error", None)

    # Agent outputs
    ss.setdefault("agents.step.overrides", {})
    ss.setdefault("agents.step.outputs", {})
    ss.setdefault("agents.timeline", {"nodes": [], "edges": []})

    # Summary / Skills
    ss.setdefault("summary.artifact_id", None)
    ss.setdefault("summary.persistent_prompt", "")
    ss.setdefault("skills.last_description", "")
    ss.setdefault("skills.outputs", [])

    # WOW AI outputs
    ss.setdefault("wow.evidence.artifact_id", None)
    ss.setdefault("wow.evidence.rows", None)
    ss.setdefault("wow.consistency.artifact_id", None)
    ss.setdefault("wow.risk.artifact_id", None)
    ss.setdefault("wow.risk.domains", None)
    ss.setdefault("wow.rta.artifact_id", None)
    ss.setdefault("wow.rta.score", None)
    ss.setdefault("wow.claims.artifact_id", None)
    ss.setdefault("wow.claims.rows", None)

    # Note keeper
    ss.setdefault("notes.input_raw", "")
    ss.setdefault("notes.output_artifact_id", None)
    ss.setdefault("notes.model_provider", "openai")
    ss.setdefault("notes.model", "gpt-4o-mini")
    ss.setdefault("notes.prompt", "Organize the note into clean Markdown with headings, bullets, and action items.")
    ss.setdefault("notes.keywords.palette", {"FDA": "#2E86C1", "biocompatibility": "#27AE60"})
    ss.setdefault("notes.magics.history", [])

    # Observability
    ss.setdefault("obs.events", [])
    ss.setdefault("obs.metrics", {})
    ss.setdefault("obs.pipeline_state", {})
    ss.setdefault("obs.export.ready", {})


def total_purge():
    preserve = st.session_state.get("ui.preserve_prefs_on_purge", True)
    keep = {}
    if preserve:
        keep = {
            "ui.theme": st.session_state.get("ui.theme"),
            "ui.lang": st.session_state.get("ui.lang"),
            "ui.painter_style": st.session_state.get("ui.painter_style"),
            "ui.jackpot_seed": st.session_state.get("ui.jackpot_seed"),
            "ui.low_resource_mode": st.session_state.get("ui.low_resource_mode"),
            "ui.preserve_prefs_on_purge": True,
        }
    st.session_state.clear()
    init_state()
    for k, v in keep.items():
        st.session_state[k] = v
    safe_event("danger_zone", "warn", "Total purge executed.")
    gc.collect()


# -----------------------------
# 4) Nordic Architecture CSS
# -----------------------------
def inject_nordic_css():
    theme = st.session_state.get("ui.theme", "dark")
    style_id = st.session_state.get("ui.painter_style", "minimal")
    accent = PAINTER_STYLES.get(style_id, PAINTER_STYLES["minimal"])["accent"]
    tokens = NORDIC_DARK if theme == "dark" else NORDIC_LIGHT

    css = f"""
    <style>
      :root {{
        --bg: {tokens["bg"]};
        --surface: {tokens["surface"]};
        --surface2: {tokens["surface_2"]};
        --text: {tokens["text"]};
        --muted: {tokens["muted"]};
        --border: {tokens["border"]};
        --shadow: {tokens["shadow"]};
        --accent: {accent};
        --coral: {RESERVED_CORAL};
        --radius: 14px;
      }}

      .stApp {{
        background: var(--bg);
        color: var(--text);
      }}

      /* Typography */
      html, body, [class*="css"] {{
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji";
      }}
      h1, h2, h3, h4 {{
        letter-spacing: -0.02em;
      }}
      .muted {{
        color: var(--muted);
      }}

      /* Nordic surfaces */
      .nordic-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px 14px;
        box-shadow: 0 8px 24px var(--shadow);
      }}

      .nordic-card.soft {{
        background: var(--surface2);
      }}

      /* Minimal chips */
      .chip {{
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(127,127,127,0.06);
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 12px;
      }}
      .chip .dot {{
        width:8px; height:8px; border-radius:99px;
        background: var(--accent);
        opacity: 0.9;
      }}
      .chip.ok .dot {{ background: rgba(46, 204, 113, 0.9); }}
      .chip.warn .dot {{ background: rgba(241, 196, 15, 0.9); }}
      .chip.err .dot {{ background: rgba(231, 76, 60, 0.9); }}

      /* Buttons */
      div.stButton > button {{
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02)) !important;
        color: var(--text) !important;
      }}
      div.stButton > button:hover {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(0,0,0,0), 0 0 14px rgba(0,0,0,0), 0 0 0 3px rgba(0,229,255,0.05);
      }}

      /* Accent helpers */
      .accent {{ color: var(--accent); font-weight: 700; }}
      .coral {{ color: var(--coral); font-weight: 800; }}

      /* Markdown tables */
      .stMarkdown table {{
        border-collapse: collapse;
        width: 100%;
      }}
      .stMarkdown th, .stMarkdown td {{
        border: 1px solid var(--border);
        padding: 6px 8px;
        vertical-align: top;
      }}
      .stMarkdown th {{
        background: rgba(127,127,127,0.08);
      }}

      /* Code blocks */
      pre {{
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(127,127,127,0.06);
        padding: 10px;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# -----------------------------
# 5) Provider key management
# -----------------------------
def get_env_key(provider: str) -> Optional[str]:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENERATIVEAI_API_KEY")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    if provider == "grok":
        return os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    return None


def get_effective_key(provider: str) -> Optional[str]:
    env = get_env_key(provider)
    if env:
        return env
    return st.session_state.get(f"keys.{provider}")


def provider_key_source(provider: str) -> str:
    if get_env_key(provider):
        return "env"
    if st.session_state.get(f"keys.{provider}"):
        return "session"
    return "missing"


def render_key_section():
    st.sidebar.markdown(f"### {t('api_keys')}")
    for p in PROVIDERS:
        src = provider_key_source(p)
        if src == "env":
            st.sidebar.success(f"{p.upper()} — {t('managed_by_system')}")
        elif src == "session":
            st.sidebar.warning(f"{p.upper()} — {t('session_key')}")
        else:
            st.sidebar.error(f"{p.upper()} — {t('missing_key')}")

        # Only show input if env key absent
        if src != "env":
            st.sidebar.text_input(
                f"{p.upper()} API Key",
                type="password",
                value=st.session_state.get(f"keys.{p}") or "",
                key=f"keys.{p}",
                help="Stored only in session state. Not logged. Cleared by Total Purge.",
            )


# -----------------------------
# 6) Artifacts / Versioning
# -----------------------------
def create_artifact(initial_text: str, fmt: str, metadata: Optional[dict] = None) -> str:
    artifacts = st.session_state["artifacts"]
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    artifacts[artifact_id] = {
        "current_version_id": version_id,
        "versions": [
            {
                "version_id": version_id,
                "created_at": now_taipei_str(),
                "created_by": "system",
                "content_text": initial_text or "",
                "content_format": fmt,
                "metadata": metadata or {},
                "parent_version_id": None,
            }
        ],
    }
    return artifact_id


def artifact_get_current(artifact_id: str) -> Tuple[str, dict]:
    artifacts = st.session_state["artifacts"]
    a = artifacts.get(artifact_id)
    if not a:
        return "", {}
    cur = a["current_version_id"]
    for v in reversed(a["versions"]):
        if v["version_id"] == cur:
            return v["content_text"], v
    v = a["versions"][-1]
    return v["content_text"], v


def artifact_add_version(artifact_id: str, new_text: str, created_by: str, metadata: Optional[dict] = None, parent_version_id: Optional[str] = None) -> str:
    artifacts = st.session_state["artifacts"]
    a = artifacts.get(artifact_id)
    if not a:
        raise KeyError("artifact not found")
    version_id = str(uuid.uuid4())
    a["versions"].append(
        {
            "version_id": version_id,
            "created_at": now_taipei_str(),
            "created_by": created_by,
            "content_text": new_text or "",
            "content_format": "markdown",
            "metadata": metadata or {},
            "parent_version_id": parent_version_id or a.get("current_version_id"),
        }
    )
    a["current_version_id"] = version_id
    return version_id


def artifact_versions(artifact_id: str) -> List[dict]:
    a = st.session_state["artifacts"].get(artifact_id, {})
    return a.get("versions", [])


# -----------------------------
# 7) agents.yaml: load/validate/standardize/upload/download
# -----------------------------
def load_agents_yaml_once():
    if st.session_state.get("agents.yaml.raw"):
        return
    raw = ""
    if os.path.exists("agents.yaml"):
        try:
            with open("agents.yaml", "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            safe_event("agents", "err", f"Failed reading agents.yaml: {e}")
    st.session_state["agents.yaml.raw"] = raw.strip() or DEFAULT_AGENTS_YAML


def validate_agents_yaml(raw: str) -> Optional[AgentsConfig]:
    try:
        parsed = yaml.safe_load(raw) or {}
        cfg = AgentsConfig(**parsed)
        for a in cfg.agents:
            if a.provider not in PROVIDERS:
                raise ValueError(f"Unsupported provider '{a.provider}' in agent '{a.id}'")
        return cfg
    except Exception as e:
        st.session_state["agents.last_error"] = str(e)
        return None


def _normalize_provider(p: Optional[str]) -> str:
    p = (p or "").strip().lower()
    if p in PROVIDERS:
        return p
    # loose mapping
    if p in ["xai", "grok", "x-ai"]:
        return "grok"
    if p in ["google", "gemini", "generativeai"]:
        return "gemini"
    if p in ["openai", "oai"]:
        return "openai"
    if p in ["anthropic", "claude"]:
        return "anthropic"
    return "openai"


def standardize_agents_yaml(raw: str) -> Tuple[str, str]:
    """
    Deterministic standardizer:
    - Accepts many shapes:
        - {agents: [...]}
        - top-level list [...]
        - {steps: [...]}, {pipeline: [...]}
    - Maps common keys into canonical AgentSpec fields.
    Returns (standard_yaml, report_md)
    """
    report = ["## Agent YAML Standardization Report", ""]
    try:
        parsed = yaml.safe_load(raw)
    except Exception as e:
        # fallback: return default
        report += [f"**Parsing failed:** {e}", "", "Falling back to default schema."]
        return DEFAULT_AGENTS_YAML, "\n".join(report)

    candidates = None
    shape = "unknown"
    if isinstance(parsed, dict):
        if isinstance(parsed.get("agents"), list):
            candidates = parsed.get("agents")
            shape = "dict.agents"
        elif isinstance(parsed.get("steps"), list):
            candidates = parsed.get("steps")
            shape = "dict.steps"
        elif isinstance(parsed.get("pipeline"), list):
            candidates = parsed.get("pipeline")
            shape = "dict.pipeline"
        else:
            # try find first list value
            for k, v in parsed.items():
                if isinstance(v, list):
                    candidates = v
                    shape = f"dict.{k}"
                    break
    elif isinstance(parsed, list):
        candidates = parsed
        shape = "list"

    if not isinstance(candidates, list):
        report += [f"**Unrecognized YAML structure** ({shape}).", "", "Falling back to default schema."]
        return DEFAULT_AGENTS_YAML, "\n".join(report)

    report.append(f"- Detected structure: **{shape}**")
    report.append(f"- Candidate steps: **{len(candidates)}**")
    report.append("")

    standardized = {"agents": []}
    for i, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            item = {"user_prompt": str(item)}

        # key mapping
        agent_id = str(item.get("id") or item.get("agent_id") or item.get("key") or f"a{i}")
        name = str(item.get("name") or item.get("title") or item.get("display_name") or f"Agent {i}")

        provider = _normalize_provider(item.get("provider") or item.get("llm_provider") or item.get("vendor"))
        model = str(item.get("model") or item.get("llm_model") or item.get("engine") or SUPPORTED_MODELS.get(provider, ["gpt-4o-mini"])[0])

        temp = item.get("temperature", item.get("temp", DEFAULT_TEMPERATURE))
        try:
            temperature = float(temp)
        except Exception:
            temperature = DEFAULT_TEMPERATURE

        mt = item.get("max_tokens", item.get("maxTokens", item.get("output_tokens", DEFAULT_MAX_TOKENS)))
        try:
            max_tokens = int(mt)
        except Exception:
            max_tokens = DEFAULT_MAX_TOKENS

        system_prompt = str(item.get("system_prompt") or item.get("system") or item.get("role") or "")
        user_prompt = str(item.get("user_prompt") or item.get("prompt") or item.get("user") or item.get("instruction") or "")

        # fill placeholders if missing prompts
        changes = []
        if not system_prompt.strip():
            system_prompt = "You are a regulatory assistant. Be factual. Output in Markdown. Do not invent data."
            changes.append("system_prompt defaulted")
        if not user_prompt.strip():
            user_prompt = "Analyze the provided context and produce a structured Markdown output."
            changes.append("user_prompt defaulted")

        expected_format = str(item.get("expected_format") or item.get("format") or "markdown")

        standardized["agents"].append(
            {
                "id": agent_id,
                "name": name,
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "expected_format": expected_format,
            }
        )

        report.append(f"- Standardized agent **{agent_id}** — {name}" + (f" _(changes: {', '.join(changes)})_" if changes else ""))

    report.append("")
    report.append("### Notes")
    report.append("- This standardization is deterministic; please review prompts and model/provider selections.")
    report.append(f"- Default `max_tokens` is {DEFAULT_MAX_TOKENS} when missing.")
    report.append("- You can edit the standardized YAML in the editor and download it.")

    # dump YAML
    std_yaml = yaml.safe_dump(standardized, sort_keys=False, allow_unicode=True)
    return std_yaml, "\n".join(report)


# -----------------------------
# 8) Datasets / search
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataset_csv(path: str) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pandas not installed")
    return pd.read_csv(path)


def load_datasets_best_effort():
    if pd is None:
        safe_event("data", "warn", "pandas not installed; dataset features disabled.")
        st.session_state["data.loaded"] = False
        return

    base = "data"
    files = {
        "510k": os.path.join(base, "510k.csv"),
        "mdr": os.path.join(base, "mdr.csv"),
        "gudid": os.path.join(base, "gudid.csv"),
        "recall": os.path.join(base, "recall.csv"),
    }
    dfs = {}
    counts = {}
    for k, fp in files.items():
        if os.path.exists(fp):
            try:
                df = load_dataset_csv(fp)
                dfs[k] = df
                counts[k] = int(len(df))
                safe_event("data", "info", f"Loaded dataset {k} ({counts[k]} rows).")
            except Exception as e:
                dfs[k] = pd.DataFrame()
                counts[k] = 0
                safe_event("data", "err", f"Failed loading dataset {k}: {e}")
        else:
            dfs[k] = pd.DataFrame()
            counts[k] = 0

    st.session_state["dataframes"] = dfs
    st.session_state["data.counts"] = counts
    st.session_state["data.loaded"] = True
    set_pipeline_state("data", "done", f"Loaded datasets: {counts}")


def fuzzy_search_all(query: str, limit: int = 25) -> Dict[str, Any]:
    dfs = st.session_state.get("dataframes", {})
    results = {}
    if not query.strip():
        return results

    for name, df in (dfs or {}).items():
        if df is None or getattr(df, "empty", True):
            results[name] = None
            continue

        cols = [c for c in df.columns if any(s in c.lower() for s in ["device", "name", "applicant", "k_number", "product", "code", "manufacturer", "udi"])]
        cols = cols[:6] if cols else list(df.columns[:4])

        try:
            if fuzz and process:
                comb = df[cols].astype(str).fillna("").agg(" | ".join, axis=1).tolist()
                matches = process.extract(query, comb, scorer=fuzz.partial_ratio, limit=min(limit, len(comb)))
                idxs = [m[2] for m in matches if m[1] >= 60]
                sub = df.iloc[idxs].copy()
                sub["_score"] = [m[1] for m in matches if m[1] >= 60]
                results[name] = sub
            else:
                mask = None
                for c in cols:
                    m = df[c].astype(str).str.contains(query, case=False, na=False)
                    mask = m if mask is None else (mask | m)
                results[name] = df[mask].head(limit).copy()
        except Exception as e:
            safe_event("search", "err", f"Search failed for {name}: {e}")
            results[name] = None

    return results


# -----------------------------
# 9) LLM execution gateway
# -----------------------------
def llm_execute(provider: str, model: str, system_prompt: str, user_prompt: str, context: str,
                max_tokens: int, temperature: float) -> Tuple[str, dict]:
    start = time.time()
    safe_event("llm", "info", f"LLM start: {provider}/{model}", {"max_tokens": max_tokens})

    key = get_effective_key(provider)
    if not key:
        raise RuntimeError(f"Missing API key for provider: {provider}")

    full_user = (user_prompt or "").strip()
    if context:
        full_user = full_user + "\n\n--- CONTEXT START ---\n" + context + "\n--- CONTEXT END ---\n"

    content = ""
    usage = {"input_tokens_est": approx_tokens(system_prompt + full_user)}

    if provider == "openai":
        if OpenAI is None:
            raise RuntimeError("openai SDK not installed.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": full_user},
            ],
            max_tokens=int(max_tokens),
            temperature=float(temperature),
        )
        content = resp.choices[0].message.content or ""

    elif provider == "grok":
        if OpenAI is None:
            raise RuntimeError("openai SDK not installed (used for OpenAI-compatible endpoints).")
        base_url = os.getenv("GROK_BASE_URL") or os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1"
        client = OpenAI(api_key=key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": full_user},
            ],
            max_tokens=int(max_tokens),
            temperature=float(temperature),
        )
        content = resp.choices[0].message.content or ""

    elif provider == "anthropic":
        if anthropic is None:
            raise RuntimeError("anthropic SDK not installed.")
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            system=system_prompt or "",
            messages=[{"role": "user", "content": full_user}],
        )
        parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        content = "\n".join(parts).strip()

    elif provider == "gemini":
        if genai is None:
            raise RuntimeError("google-generativeai SDK not installed.")
        genai.configure(api_key=key)
        mdl = genai.GenerativeModel(model)
        msg = ""
        if system_prompt:
            msg += f"[SYSTEM]\n{system_prompt}\n\n"
        msg += full_user
        resp = mdl.generate_content(msg)
        content = getattr(resp, "text", "") or ""

    else:
        raise RuntimeError(f"Unsupported provider: {provider}")

    elapsed = int((time.time() - start) * 1000)
    bump_metric(f"{provider}.calls", 1)
    bump_metric(f"{provider}.latency_ms_total", elapsed)
    safe_event("llm", "info", f"LLM done: {provider}/{model} ({elapsed}ms)")
    return content, {
        "latency_ms": elapsed,
        "usage": usage,
        "provider": provider,
        "model": model,
        "prompts_hash": {"system": sha256_hex(system_prompt), "user": sha256_hex(user_prompt), "context": sha256_hex((context or "")[:5000])},
    }


# -----------------------------
# 10) Document pipeline: ingest/scan/trim/OCR/consolidate
# -----------------------------
def register_uploaded_files(uploaded_files: list):
    if not uploaded_files:
        return
    reg = st.session_state["docs.registry"]
    existing_names = {f["name"] for f in reg}

    for uf in uploaded_files:
        try:
            b = uf.read()
            file_id = str(uuid.uuid4())
            name = uf.name
            if name in existing_names:
                name = f"{name} ({file_id[:8]})"
            reg.append(
                {
                    "id": file_id,
                    "name": name,
                    "source": "upload",
                    "bytes": b,
                    "path": None,
                    "size": len(b),
                    "page_count": None,
                    "health": "unknown",
                    "created_at": now_taipei_str(),
                }
            )
            safe_event("ingestion", "info", f"Registered upload: {name} ({human_size(len(b))}).")
        except Exception as e:
            safe_event("ingestion", "err", f"Failed registering upload: {e}")

    set_pipeline_state("ingestion", "done", f"Registry size: {len(st.session_state['docs.registry'])}")


def register_file_paths(paths_text: str):
    if not paths_text.strip():
        return
    reg = st.session_state["docs.registry"]
    lines = [ln.strip() for ln in paths_text.splitlines() if ln.strip()]
    for p in lines:
        try:
            if not os.path.exists(p):
                safe_event("ingestion", "warn", f"Path not found: {p}")
                continue
            if not p.lower().endswith(".pdf"):
                safe_event("ingestion", "warn", f"Not a PDF: {p}")
                continue
            with open(p, "rb") as f:
                b = f.read()
            file_id = str(uuid.uuid4())
            reg.append(
                {
                    "id": file_id,
                    "name": os.path.basename(p),
                    "source": "path",
                    "bytes": b,
                    "path": p,
                    "size": len(b),
                    "page_count": None,
                    "health": "unknown",
                    "created_at": now_taipei_str(),
                }
            )
            safe_event("ingestion", "info", f"Registered path: {os.path.basename(p)} ({human_size(len(b))}).")
        except Exception as e:
            safe_event("ingestion", "err", f"Failed reading path {p}: {e}")

    set_pipeline_state("ingestion", "done", f"Registry size: {len(st.session_state['docs.registry'])}")


def scan_pdf_metadata(file_obj: dict):
    if PdfReader is None:
        file_obj["health"] = "no_pypdf2"
        return
    try:
        reader = PdfReader(io.BytesIO(file_obj["bytes"]))
        file_obj["page_count"] = len(reader.pages)
        file_obj["health"] = "ok"
    except Exception as e:
        file_obj["health"] = f"error: {e}"


def ensure_scanned_metadata():
    for f in st.session_state["docs.registry"]:
        if f.get("page_count") is None and isinstance(f.get("bytes"), (bytes, bytearray)):
            scan_pdf_metadata(f)


def trim_pdf_bytes(pdf_bytes: bytes, page_indices: List[int]) -> bytes:
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("PyPDF2 not available.")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    max_page = len(reader.pages) - 1
    for idx in page_indices:
        if 0 <= idx <= max_page:
            writer.add_page(reader.pages[idx])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def execute_trimming(policy_out_of_range: str = "clip_with_warn"):
    set_pipeline_state("trim", "running", "Trimming selected PDFs...")
    reg = st.session_state["docs.registry"]
    selected: Set[str] = st.session_state["docs.queue.selected_ids"] or set()
    global_range = st.session_state.get("docs.trim.global_range", "1-5")
    per_override = st.session_state.get("docs.trim.per_file_override", {})

    outputs = {}
    warnings = 0

    for f in reg:
        if f["id"] not in selected:
            continue
        rng = (per_override.get(f["id"]) or "").strip() or global_range
        try:
            indices = parse_page_ranges(rng)
            if f.get("page_count") is not None and indices:
                max_page = f["page_count"] - 1
                if indices[-1] > max_page:
                    if policy_out_of_range == "block":
                        raise ValueError(f"Range exceeds page count ({f['page_count']}).")
                    if policy_out_of_range == "skip_file":
                        safe_event("trim", "warn", f"Skipping {f['name']}: range exceeds page count.")
                        warnings += 1
                        continue
                    # clip with warn
                    indices = [i for i in indices if i <= max_page]
                    safe_event("trim", "warn", f"Clipped range for {f['name']} to max page {f['page_count']}.")

            outputs[f["id"]] = trim_pdf_bytes(f["bytes"], indices)
            safe_event("trim", "info", f"Trimmed {f['name']} with range '{rng}'.")
        except Exception as e:
            safe_event("trim", "err", f"Trimming failed for {f['name']}: {e}")
            warnings += 1

    st.session_state["docs.trim.outputs"] = outputs
    set_pipeline_state("trim", "done" if warnings == 0 else "warn", f"Trimmed files: {len(outputs)}")
    bump_metric("trim.files", len(outputs))


def ocr_python_pack(pdf_bytes: bytes, low_resource: bool = False) -> str:
    text = ""
    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            chunks = []
            for i, p in enumerate(reader.pages):
                try:
                    chunks.append(p.extract_text() or "")
                except Exception:
                    chunks.append("")
                if low_resource and i >= 4:
                    break
            text = "\n".join(chunks).strip()
        except Exception as e:
            safe_event("ocr", "warn", f"PyPDF2 extraction failed: {e}")

    if text:
        return text

    if convert_from_bytes is None or pytesseract is None:
        safe_event("ocr", "warn", "Tesseract/pdf2image not available; returning empty text.")
        return ""

    images = convert_from_bytes(pdf_bytes, dpi=200 if low_resource else 300)
    out_chunks = []
    for idx, img in enumerate(images):
        try:
            out_chunks.append(pytesseract.image_to_string(img))
        except Exception as e:
            safe_event("ocr", "warn", f"Tesseract OCR failed page {idx+1}: {e}")
        if low_resource and idx >= 4:
            break
    return "\n".join(out_chunks).strip()


def gemini_llm_ocr(pdf_bytes: bytes, model: str, prompt: str, low_resource: bool = False) -> str:
    if genai is None:
        raise RuntimeError("google-generativeai not installed.")
    api_key = get_effective_key("gemini")
    if not api_key:
        raise RuntimeError("Gemini API key missing.")
    genai.configure(api_key=api_key)

    if convert_from_bytes is None:
        raise RuntimeError("pdf2image not installed; cannot render images.")

    images = convert_from_bytes(pdf_bytes, dpi=180 if low_resource else 300)
    if low_resource:
        images = images[:5]

    mdl = genai.GenerativeModel(model)
    out = []
    for i, img in enumerate(images, start=1):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b = buf.getvalue()
        parts = [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(b).decode("utf-8")}},
        ]
        try:
            resp = mdl.generate_content(parts)
            out_text = getattr(resp, "text", "") or ""
            out.append(out_text.strip())
            safe_event("ocr", "info", f"Gemini OCR page {i}/{len(images)} done.", {"model": model})
            bump_metric("gemini.calls", 1)
        except Exception as e:
            safe_event("ocr", "err", f"Gemini OCR failed page {i}: {e}", {"model": model})
            bump_metric("gemini.errors", 1)
            out.append(f"\n\n[OCR ERROR page {i}: {e}]\n\n")
    return "\n\n".join(out).strip()


def assemble_consolidated_markdown(outputs_by_file: Dict[str, str]) -> Tuple[str, Dict[str, dict]]:
    anchors = {}
    reg = {f["id"]: f for f in st.session_state["docs.registry"]}
    pieces = []
    for file_id, content in outputs_by_file.items():
        f = reg.get(file_id, {"name": file_id})
        anchor_id = f"anc_{file_id[:8]}_p1"
        anchors[anchor_id] = {"file_id": file_id, "file_name": f.get("name"), "page": 1}
        pieces.append(f"--- ANCHOR: {anchor_id} | FILE: {f.get('name')} | PAGE: 1 ---")
        pieces.append(content or "")
        pieces.append("\n")
    return "\n".join(pieces).strip(), anchors


def execute_ocr():
    set_pipeline_state("ocr", "running", "OCR running...")
    selected: Set[str] = st.session_state["docs.queue.selected_ids"] or set()
    trimmed = st.session_state.get("docs.trim.outputs", {})
    mode = st.session_state.get("docs.ocr.mode", "python_pack")
    low_resource = st.session_state.get("ui.low_resource_mode", False)

    if not selected:
        raise RuntimeError("No files selected.")
    if not trimmed:
        raise RuntimeError("No trimmed PDFs found. Run Trim first.")

    outputs = {}
    file_ids = [fid for fid in trimmed.keys() if fid in selected]
    total = len(file_ids)
    progress = st.progress(0.0)

    for idx, file_id in enumerate(file_ids, start=1):
        progress.progress(idx / max(1, total))
        pdf_bytes = trimmed[file_id]
        name = next((f["name"] for f in st.session_state["docs.registry"] if f["id"] == file_id), file_id)

        try:
            if mode == "python_pack":
                text = ocr_python_pack(pdf_bytes, low_resource=low_resource)
                outputs[file_id] = text
                bump_metric("ocr.python.files", 1)
                safe_event("ocr", "info", f"Python OCR done: {name}")
            else:
                model = st.session_state.get("docs.ocr.model", GEMINI_MODELS[0])
                global_prompt = st.session_state.get("docs.ocr.prompt_global", "")
                per_file_prompt = (st.session_state.get("docs.ocr.prompt_per_file", {}) or {}).get(file_id, "").strip()
                prompt = per_file_prompt or global_prompt
                md = gemini_llm_ocr(pdf_bytes, model=model, prompt=prompt, low_resource=low_resource)
                outputs[file_id] = md
                bump_metric("ocr.gemini.files", 1)
        except Exception as e:
            safe_event("ocr", "err", f"OCR failed for {name}: {e}")
            outputs[file_id] = f"\n\n[OCR ERROR for {name}: {e}]\n\n"
            bump_metric("ocr.errors", 1)

    st.session_state["docs.ocr.outputs_by_file"] = outputs
    consolidated, anchors = assemble_consolidated_markdown(outputs)
    st.session_state["docs.consolidated_markdown"] = consolidated
    st.session_state["docs.consolidated_anchors"] = anchors

    if not st.session_state.get("consolidated.artifact_id"):
        aid = create_artifact(consolidated, fmt="markdown", metadata={"source": "ocr_consolidation"})
        st.session_state["consolidated.artifact_id"] = aid
    else:
        aid = st.session_state["consolidated.artifact_id"]
        cur, curm = artifact_get_current(aid)
        artifact_add_version(aid, consolidated, created_by="ocr", metadata={"source": "ocr_consolidation"}, parent_version_id=curm.get("version_id"))

    set_pipeline_state("ocr", "done", f"OCR files: {len(outputs)}")
    set_pipeline_state("consolidation", "done", f"Chars: {len(consolidated)}")
    bump_metric("ocr.files", len(outputs))


# -----------------------------
# 11) Timeline / DAG (simple registry)
# -----------------------------
def timeline_add_node(kind: str, title: str, artifact_id: Optional[str], meta: dict) -> str:
    node_id = str(uuid.uuid4())
    tl = st.session_state["agents.timeline"]
    tl["nodes"].append({"node_id": node_id, "kind": kind, "title": title, "artifact_id": artifact_id, "ts": now_taipei_str(), "meta": meta})
    return node_id


def timeline_add_edge(src_node_id: str, dst_node_id: str, label: str = "handoff"):
    st.session_state["agents.timeline"]["edges"].append({"src": src_node_id, "dst": dst_node_id, "label": label, "ts": now_taipei_str()})


# -----------------------------
# 12) WOW AI core helpers
# -----------------------------
def extract_claims(text: str, max_claims: int = 80) -> List[str]:
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    claims = []
    for ln in lines:
        if ln.startswith(("-", "*", "•")) and len(ln) > 25:
            claims.append(ln.lstrip("-*• ").strip())

    sents = re.split(r"(?<=[\.\?!])\s+", text)
    for s in sents:
        s = s.strip()
        if len(s) < 40:
            continue
        if re.search(r"\d", s) or any(k in s.lower() for k in ["shall", "must", "demonstrat", "tested", "complied", "indicat"]):
            claims.append(s)

    uniq = []
    seen = set()
    for c in claims:
        key = c.lower()[:180]
        if key not in seen:
            uniq.append(c)
            seen.add(key)
        if len(uniq) >= max_claims:
            break
    return uniq


def build_anchor_index(consolidated_md: str) -> List[Tuple[int, str]]:
    idx = []
    for m in re.finditer(r"---\s*ANCHOR:\s*([A-Za-z0-9_\-]+)\s*\|", consolidated_md or ""):
        idx.append((m.start(), m.group(1)))
    idx.sort(key=lambda x: x[0])
    return idx


def find_nearest_anchor(anchor_index: List[Tuple[int, str]], position: int) -> Optional[str]:
    if not anchor_index:
        return None
    lo, hi = 0, len(anchor_index) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        pos, aid = anchor_index[mid]
        if pos <= position:
            best = aid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def evidence_mapper_run(target_text: str) -> Tuple[str, List[dict]]:
    consolidated = st.session_state.get("docs.consolidated_markdown", "") or ""
    anchors = st.session_state.get("docs.consolidated_anchors", {}) or {}
    if not consolidated.strip():
        raise RuntimeError("No consolidated OCR text available.")

    anchor_index = build_anchor_index(consolidated)
    claims = extract_claims(target_text, max_claims=60)
    if not claims:
        return "No claims detected.", []

    lines = consolidated.splitlines()
    positions = []
    cur = 0
    for ln in lines:
        positions.append(cur)
        cur += len(ln) + 1

    results = []
    for c in claims:
        best = {"score": 0, "line": "", "pos": None}
        if fuzz is not None:
            for i, ln in enumerate(lines):
                if not ln.strip():
                    continue
                s = fuzz.partial_ratio(c[:300], ln[:400])
                if s > best["score"]:
                    best = {"score": s, "line": ln, "pos": positions[i]}
        else:
            for i, ln in enumerate(lines):
                if c[:40].lower() in ln.lower():
                    best = {"score": 70, "line": ln, "pos": positions[i]}
                    break

        anchor_id = find_nearest_anchor(anchor_index, best["pos"] or 0) if best["pos"] is not None else None
        anc_meta = anchors.get(anchor_id, {}) if anchor_id else {}

        results.append(
            {
                "claim": c,
                "confidence": best["score"],
                "evidence_quote": (best["line"] or "")[:500],
                "anchor_id": anchor_id or "",
                "file": anc_meta.get("file_name", ""),
                "page": anc_meta.get("page", ""),
            }
        )

    md_lines = [
        "## Evidence Map",
        "",
        f"- Claims analyzed: **{len(results)}**",
        f"- Coverage (has anchor): **{sum(1 for r in results if r['anchor_id'])}/{len(results)}**",
        "",
        "| Claim | Confidence | Evidence Quote | Anchor | File | Page |",
        "|---|---:|---|---|---|---:|",
    ]
    for r in results:
        claim = (r["claim"][:160] + "…") if len(r["claim"]) > 160 else r["claim"]
        quote = (r["evidence_quote"][:140] + "…") if len(r["evidence_quote"]) > 140 else r["evidence_quote"]
        md_lines.append(
            f"| {claim.replace('|','\\|')} | {r['confidence']} | {quote.replace('|','\\|')} | {r['anchor_id']} | {r['file']} | {r['page']} |"
        )
    return "\n".join(md_lines), results


def consistency_guardian_run(summary_text: str) -> str:
    issues = []
    text = summary_text or ""
    lower = text.lower()

    required_headings = [
        "device description",
        "indications",
        "predicate",
        "performance",
        "biocompat",
        "steril",
        "label",
    ]
    missing = [h for h in required_headings if h not in lower]
    for h in missing:
        issues.append({"severity": "high", "title": "Missing section", "detail": f"Required section not found: '{h}'"})

    shelf = re.findall(r"(shelf\s*life[^.\n]{0,80})", lower)
    vals = set()
    for s in shelf:
        m = re.search(r"(\d+(\.\d+)?)\s*(year|years|month|months|day|days)", s)
        if m:
            vals.add(m.group(0))
    if len(vals) >= 2:
        issues.append({"severity": "critical", "title": "Conflicting shelf life", "detail": f"Multiple shelf-life values found: {sorted(vals)}"})

    steril_methods = set()
    for pat in ["eto", "ethylene oxide", "gamma", "e-beam", "steam", "autoclave", "radiation"]:
        if pat in lower:
            steril_methods.add(pat)
    if len(steril_methods) >= 3:
        issues.append({"severity": "medium", "title": "Multiple sterilization methods mentioned", "detail": f"Sterilization terms found: {sorted(steril_methods)}"})

    md = ["## Consistency Guardian Report", ""]
    if not issues:
        md.append("No major consistency issues detected by heuristic checks.")
        return "\n".join(md)

    md.append(f"Detected issues: **{len(issues)}**")
    md.append("")
    md.append("| Severity | Issue | Detail |")
    md.append("|---|---|---|")
    for it in issues:
        md.append(f"| {it['severity']} | {it['title']} | {it['detail'].replace('|','\\|')} |")

    md.append("")
    md.append("### Recommended Actions")
    md.append("- Review flagged sections and harmonize terminology and numeric values.")
    md.append("- Use Evidence Mapper to confirm that key claims are traceable to OCR anchors.")
    return "\n".join(md)


def risk_radar_run(summary_text: str, evidence_results: Optional[List[dict]] = None) -> Tuple[dict, str]:
    text = summary_text or ""
    lower = text.lower()

    coverage = None
    if evidence_results:
        mapped = sum(1 for r in evidence_results if r.get("anchor_id"))
        coverage = mapped / max(1, len(evidence_results))

    domains = {
        "Device Description": 0,
        "Indications for Use": 0,
        "Predicate Comparison": 0,
        "Performance Testing": 0,
        "Biocompatibility": 0,
        "Sterilization/Shelf-life": 0,
        "Software/Cybersecurity": 0,
        "Labeling/IFU": 0,
        "Post-market Signals": 0,
    }

    def missing_penalty(keywords: List[str], weight: int):
        return weight if not any(k in lower for k in keywords) else 0

    domains["Device Description"] += missing_penalty(["device description", "overview", "device"], 35)
    domains["Indications for Use"] += missing_penalty(["indications", "intended use"], 40)
    domains["Predicate Comparison"] += missing_penalty(["predicate", "substantial equivalence", "equivalent"], 45)
    domains["Performance Testing"] += missing_penalty(["performance", "bench", "verification", "validation", "test"], 40)
    domains["Biocompatibility"] += missing_penalty(["biocompat", "iso 10993"], 45)
    domains["Sterilization/Shelf-life"] += missing_penalty(["steril", "shelf life", "packaging"], 45)
    domains["Software/Cybersecurity"] += missing_penalty(["software", "cyber", "security", "sbom"], 35)
    domains["Labeling/IFU"] += missing_penalty(["label", "ifu", "instructions for use"], 35)

    dv = st.session_state.get("data.device_view", {}) or {}
    mdr_count = dv.get("mdr_count", 0) or 0
    recall_sev = dv.get("recall_max_class", 0) or 0
    if mdr_count > 0:
        domains["Post-market Signals"] += min(60, 10 + int(math.log1p(mdr_count) * 15))
    if recall_sev:
        domains["Post-market Signals"] += 20 + (recall_sev * 10)

    if coverage is not None:
        if coverage < 0.4:
            for k in domains:
                domains[k] += 10
        elif coverage < 0.65:
            for k in domains:
                domains[k] += 5

    for k in domains:
        domains[k] = int(max(0, min(100, domains[k])))

    md = ["## Regulatory Risk Radar", ""]
    md.append(f"- Evidence coverage signal: **{coverage:.2f}**" if coverage is not None else "- Evidence coverage signal: *(not available)*")
    md.append("")
    md.append("| Domain | Attention Score (0-100) | Rationale (brief) |")
    md.append("|---|---:|---|")
    for k, v in domains.items():
        rationale = "Missing or weak coverage in summary." if v >= 60 else ("Some gaps detected." if v >= 35 else "Appears reasonably covered.")
        if k == "Post-market Signals" and (mdr_count or recall_sev):
            rationale = f"Dataset signals: MDR={mdr_count}, RecallClassMax={recall_sev}."
        md.append(f"| {k} | {v} | {rationale} |")

    md.append("")
    md.append("### Priority Reading Plan (Suggested)")
    md.append("1. Review domains with the highest scores first.")
    md.append("2. Use Evidence Mapper to confirm traceability for high-impact claims.")
    md.append("3. Convert gaps into concrete reviewer follow-up questions.")
    return domains, "\n".join(md)


def rta_gatekeeper_run(summary_text: str) -> Tuple[int, str]:
    """
    WOW AI #4 — RTA Gatekeeper (heuristic completeness scan).
    Produces score 0-100 and a Markdown checklist.
    """
    lower = (summary_text or "").lower()
    checklist = [
        ("Device Description", ["device description", "device overview", "components"]),
        ("Indications for Use", ["indications", "intended use"]),
        ("Predicate Device Identification", ["predicate", "k-number", "substantial equivalence"]),
        ("Technology Comparison", ["comparison", "technological characteristics", "equivalence"]),
        ("Performance Testing", ["performance", "bench", "verification", "validation", "test"]),
        ("Biocompatibility", ["biocompat", "iso 10993"]),
        ("Sterilization", ["steril", "eto", "gamma", "sal"]),
        ("Shelf-life / Packaging", ["shelf life", "packaging", "integrity"]),
        ("Software (if applicable)", ["software", "cyber", "security", "sbom", "firmware"]),
        ("Labeling/IFU", ["label", "ifu", "instructions for use", "warnings", "precautions"]),
        ("Clinical Evidence (if applicable)", ["clinical", "study", "trial", "human data"]),
    ]

    rows = []
    passed = 0
    for item, keys in checklist:
        found = any(k in lower for k in keys)
        status = "Pass" if found else "Missing/Unclear"
        if found:
            passed += 1
        rows.append((item, status, ", ".join(keys)))

    score = int(round(100 * passed / max(1, len(checklist))))

    md = ["## RTA Gatekeeper (Heuristic)", ""]
    md.append("> This is an assistant heuristic and not an official FDA Refuse-to-Accept determination.")
    md.append("")
    md.append(f"**RTA Readiness Score:** **{score}/100**  (coverage: {passed}/{len(checklist)})")
    md.append("")
    md.append("| Checklist Item | Status | Signals |")
    md.append("|---|---|---|")
    for item, status, signals in rows:
        md.append(f"| {item} | {status} | {signals} |")
    md.append("")
    md.append("### Suggested Next Actions")
    md.append("- For each Missing/Unclear item, locate evidence in OCR text and update the macro summary.")
    md.append("- Use Evidence Mapper to verify traceability for claims in high-impact sections.")
    return score, "\n".join(md)


def labeling_claims_inspector_run(consolidated: str, summary_text: str, evidence_rows: Optional[List[dict]] = None) -> Tuple[str, List[dict]]:
    """
    WOW AI #5 — Labeling & Claims Inspector (heuristic).
    - Extracts candidate claims from summary + consolidated.
    - Flags risky/absolute/superiority language.
    - Attempts to find supporting anchor (via fuzzy match).
    """
    if not consolidated.strip():
        raise RuntimeError("No consolidated OCR available (run OCR first).")
    anchors = st.session_state.get("docs.consolidated_anchors", {}) or {}
    anchor_index = build_anchor_index(consolidated)
    lines = consolidated.splitlines()
    positions = []
    cur = 0
    for ln in lines:
        positions.append(cur)
        cur += len(ln) + 1

    # Candidate claim sentences
    combined = (summary_text or "") + "\n\n" + (consolidated[:8000] or "")
    sents = re.split(r"(?<=[\.\?!])\s+", combined)
    risky_terms = ["safe and effective", "guarantee", "superior", "best", "proven", "prevents", "eliminates", "no risk", "never"]
    perf_terms = ["reduces", "improves", "increases", "detects", "diagnoses", "treats", "prevents", "supports", "enhances"]
    label_terms = ["warning", "warnings", "precaution", "contraindication", "indications", "intended use", "label", "ifu"]

    claims = []
    for s in sents:
        s = s.strip()
        if len(s) < 40:
            continue
        l = s.lower()
        if any(rt in l for rt in risky_terms) or any(pt in l for pt in perf_terms) or any(lt in l for lt in label_terms):
            claims.append(s)
        if len(claims) >= 40:
            break

    if not claims:
        return "No candidate labeling/claims sentences detected.", []

    rows = []
    for c in claims:
        l = c.lower()
        risk_flags = []
        if any(rt in l for rt in risky_terms):
            risk_flags.append("Absolute/Superiority phrasing")
        if "safe and effective" in l:
            risk_flags.append("Regulatory-sensitive claim")
        if "guarantee" in l or "proven" in l:
            risk_flags.append("High certainty wording")

        # find evidence line in consolidated
        best = {"score": 0, "line": "", "pos": None}
        if fuzz is not None:
            for i, ln in enumerate(lines):
                if not ln.strip():
                    continue
                s = fuzz.partial_ratio(c[:260], ln[:400])
                if s > best["score"]:
                    best = {"score": s, "line": ln, "pos": positions[i]}
        else:
            for i, ln in enumerate(lines):
                if c[:40].lower() in ln.lower():
                    best = {"score": 70, "line": ln, "pos": positions[i]}
                    break

        anchor_id = find_nearest_anchor(anchor_index, best["pos"] or 0) if best["pos"] is not None else None
        anc_meta = anchors.get(anchor_id, {}) if anchor_id else {}

        supported = bool(anchor_id) and best["score"] >= 65
        status = "Supported" if supported else "Unsupported/Weak"

        safer = ""
        if "safe and effective" in l:
            safer = c.replace("safe and effective", "designed and intended for its indicated use").strip()
        elif "guarantee" in l:
            safer = re.sub(r"(?i)\bguarantee(s|d)?\b", "aims to", c).strip()
        elif "superior" in l or "best" in l:
            safer = re.sub(r"(?i)\b(superior|best)\b", "comparable", c).strip()

        rows.append(
            {
                "claim": c,
                "risk_flags": "; ".join(risk_flags) if risk_flags else "",
                "support_status": status,
                "match_confidence": best["score"],
                "anchor_id": anchor_id or "",
                "file": anc_meta.get("file_name", ""),
                "page": anc_meta.get("page", ""),
                "suggested_safer_wording": safer,
            }
        )

    md = ["## Labeling & Claims Inspector (Heuristic)", ""]
    md.append("| Claim (truncated) | Support | Confidence | Risk Flags | Anchor |")
    md.append("|---|---|---:|---|---|")
    for r in rows:
        claim = r["claim"]
        claim = (claim[:140] + "…") if len(claim) > 140 else claim
        md.append(f"| {claim.replace('|','\\|')} | {r['support_status']} | {r['match_confidence']} | {r['risk_flags'].replace('|','\\|')} | {r['anchor_id']} |")
    md.append("")
    md.append("### Reviewer Notes")
    md.append("- Unsupported/Weak items should be verified in the source PDFs and/or rewritten to remove over-claims.")
    md.append("- Consider adding explicit evidence references or removing absolute phrasing.")
    return "\n".join(md), rows


def plot_radar(domains: dict):
    if go is None:
        st.info("plotly not installed; radar visualization unavailable.")
        return
    labels = list(domains.keys())
    values = list(domains.values())
    labels2 = labels + [labels[0]]
    values2 = values + [values[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values2, theta=labels2, fill="toself", name="Attention Score"))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        margin=dict(l=30, r=30, t=30, b=30),
        height=360,
    )
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------
# 13) UI: Nordic header + status strip
# -----------------------------
def render_header():
    col1, col2, col3, col4 = st.columns([2.4, 1.3, 1.3, 1.2], vertical_alignment="center")
    with col1:
        st.markdown(f"## {APP_TITLE}")
        st.markdown("<div class='muted'>Nordic Architecture UI • Split-pane regulatory workspace • Human-in-the-loop agent chain</div>", unsafe_allow_html=True)

    with col2:
        mode = st.selectbox(
            t("mode"),
            ["command_center", "note_keeper"],
            index=0 if st.session_state["ui.mode"] == "command_center" else 1,
            format_func=lambda x: t("command_center") if x == "command_center" else t("note_keeper"),
        )
        st.session_state["ui.mode"] = mode

        low_res = st.toggle(t("low_resource"), value=st.session_state.get("ui.low_resource_mode", False))
        st.session_state["ui.low_resource_mode"] = low_res

    with col3:
        theme = st.selectbox(
            t("theme"),
            ["dark", "light"],
            index=0 if st.session_state["ui.theme"] == "dark" else 1,
            format_func=lambda x: t("dark") if x == "dark" else t("light"),
        )
        st.session_state["ui.theme"] = theme

        lang = st.selectbox(t("language"), ["en", "zh-TW"], index=0 if st.session_state["ui.lang"] == "en" else 1)
        st.session_state["ui.lang"] = lang

    with col4:
        style_ids = list(PAINTER_STYLES.keys())
        current = st.session_state.get("ui.painter_style", "minimal")
        idx = style_ids.index(current) if current in style_ids else 0
        chosen = st.selectbox(t("painter_style"), style_ids, index=idx, format_func=lambda x: PAINTER_STYLES[x]["name"])
        st.session_state["ui.painter_style"] = chosen

        if st.button(t("jackpot")):
            seed = (st.session_state.get("ui.jackpot_seed", 0) + 1) % len(PAINTER_STYLES)
            st.session_state["ui.jackpot_seed"] = seed
            style = list(PAINTER_STYLES.keys())[seed]
            st.session_state["ui.painter_style"] = style
            safe_event("ui", "info", f"Jackpot style selected: {PAINTER_STYLES[style]['name']}")

    st.session_state["ui.preserve_prefs_on_purge"] = st.checkbox(
        "Preserve UI prefs on purge",
        value=st.session_state.get("ui.preserve_prefs_on_purge", True),
    )


def render_status_strip():
    srcs = {p: provider_key_source(p) for p in PROVIDERS}
    reg = st.session_state.get("docs.registry", [])
    sel = st.session_state.get("docs.queue.selected_ids", set())
    trimmed = st.session_state.get("docs.trim.outputs", {})
    consolidated = st.session_state.get("docs.consolidated_markdown", "") or ""
    ps = st.session_state.get("obs.pipeline_state", {})

    def chip(label: str, status: str):
        st.markdown(
            f"<span class='chip {status}'><span class='dot'></span>{label}</span>",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='nordic-card'>", unsafe_allow_html=True)

    for p in PROVIDERS:
        src = srcs[p]
        status = "ok" if src in ["env", "session"] else "err"
        chip(f"{p.upper()} key: {src}", status)

    chip(f"PDFs: {len(reg)} ingested / {len(sel)} selected", "ok" if len(sel) else "warn")
    chip(f"Trimmed: {len(trimmed)}", "ok" if len(trimmed) else "warn")
    chip(f"OCR chars: {len(consolidated)} (~{approx_tokens(consolidated)} tok)", "ok" if consolidated else "warn")

    for node in ["ingestion", "trim", "ocr", "consolidation", "agents", "summary", "wow_ai", "data"]:
        stt = ps.get(node, {}).get("status", "idle")
        status = "ok" if stt == "done" else ("warn" if stt in ["running", "warn", "idle"] else "err")
        chip(f"{node}: {stt}", status)

    mana = min(100, int((len(consolidated) / 9000) + (len(st.session_state.get("agents.timeline", {}).get("nodes", [])) * 7)))
    st.progress(mana / 100.0, text=f"Review Mana: {mana}/100")

    mem = mem_estimate_bytes()
    st.caption(f"Memory estimate (rough): {human_size(mem)}")
    if mem > 650 * 1024 * 1024:
        st.warning("Memory pressure risk on Spaces. Consider low-resource mode, trimming fewer pages, or OCR on fewer files.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 14) UI: Left pane (source material)
# -----------------------------
def render_left_pane():
    st.markdown("<div class='nordic-card'><span class='accent'>Source Material</span><div class='muted'>Ingest → Queue → Trim → OCR → Consolidate</div></div>", unsafe_allow_html=True)
    st.write("")

    with st.expander(t("ingestion"), expanded=True):
        uploaded = st.file_uploader(t("upload_pdfs"), type=["pdf"], accept_multiple_files=True)
        paths = st.text_area(t("paths"), placeholder="/path/to/file1.pdf\n/path/to/file2.pdf")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button(t("register_files")):
                set_pipeline_state("ingestion", "running", "Registering files...")
                if uploaded:
                    register_uploaded_files(uploaded)
                if paths.strip():
                    register_file_paths(paths)
                ensure_scanned_metadata()
                set_pipeline_state("ingestion", "done", f"Registry size: {len(st.session_state['docs.registry'])}")
        with c2:
            if st.button("Scan PDF metadata"):
                ensure_scanned_metadata()
                st.success("Metadata scanned.")

    with st.expander(t("queue"), expanded=True):
        ensure_scanned_metadata()
        reg = st.session_state.get("docs.registry", [])
        if not reg:
            st.info("No PDFs registered yet.")
            return

        # Select all/none
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("Select all"):
                st.session_state["docs.queue.selected_ids"] = {f["id"] for f in reg}
        with c2:
            if st.button("Select none"):
                st.session_state["docs.queue.selected_ids"] = set()
        with c3:
            st.caption("Advanced: set per-file Trim Range and per-file LLM OCR Prompt Override (optional).")

        # Build editor table
        if pd is not None:
            per_trim = st.session_state.get("docs.trim.per_file_override", {}) or {}
            per_prompt = st.session_state.get("docs.ocr.prompt_per_file", {}) or {}
            df = pd.DataFrame(
                [
                    {
                        "selected": f["id"] in st.session_state["docs.queue.selected_ids"],
                        "name": f["name"],
                        "source": f["source"],
                        "size": human_size(f["size"]),
                        "pages": f.get("page_count"),
                        "health": f.get("health"),
                        "trim_override": per_trim.get(f["id"], ""),
                        "ocr_prompt_override": per_prompt.get(f["id"], ""),
                        "id": f["id"],
                    }
                    for f in reg
                ]
            )
            edited = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "selected": st.column_config.CheckboxColumn(required=True),
                    "trim_override": st.column_config.TextColumn(help="Optional per-file page range e.g., 1-5,10"),
                    "ocr_prompt_override": st.column_config.TextColumn(help="Optional per-file LLM OCR prompt override (LLM OCR mode only)"),
                    "id": st.column_config.TextColumn(disabled=True),
                },
                disabled=["name", "source", "size", "pages", "health", "id"],
            )
            st.session_state["docs.queue.selected_ids"] = set(edited.loc[edited["selected"] == True, "id"].tolist())

            # Update overrides from edited
            new_trim = {}
            new_prompt = {}
            for _, row in edited.iterrows():
                fid = row["id"]
                tr = str(row.get("trim_override", "") or "").strip()
                pr = str(row.get("ocr_prompt_override", "") or "").strip()
                if tr:
                    new_trim[fid] = tr
                if pr:
                    new_prompt[fid] = pr
            st.session_state["docs.trim.per_file_override"] = new_trim
            st.session_state["docs.ocr.prompt_per_file"] = new_prompt
        else:
            st.write(reg)

    with st.expander(t("trim"), expanded=True):
        st.session_state["docs.trim.global_range"] = st.text_input(t("global_range"), value=st.session_state.get("docs.trim.global_range", "1-5"))
        policy = st.selectbox("Out-of-range policy", ["clip_with_warn", "skip_file", "block"], index=0)
        if st.button(t("execute_trim")):
            try:
                _ = parse_page_ranges(st.session_state["docs.trim.global_range"])
                execute_trimming(policy_out_of_range=policy)
                st.success("Trim complete.")
            except Exception as e:
                st.error(str(e))

    with st.expander(t("ocr"), expanded=True):
        mode = st.selectbox(
            t("ocr_mode"),
            ["python_pack", "llm_ocr"],
            format_func=lambda x: t("python_pack") if x == "python_pack" else t("llm_ocr"),
            index=0 if st.session_state["docs.ocr.mode"] == "python_pack" else 1,
        )
        st.session_state["docs.ocr.mode"] = mode

        if mode == "llm_ocr":
            st.session_state["docs.ocr.model"] = st.selectbox("Gemini model", GEMINI_MODELS, index=GEMINI_MODELS.index(st.session_state.get("docs.ocr.model", GEMINI_MODELS[0])))

            # Template library
            tpl_name = st.selectbox("OCR Prompt Template", list(OCR_PROMPT_TEMPLATES.keys()), index=0)
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Apply template (replace)"):
                    st.session_state["docs.ocr.prompt_global"] = OCR_PROMPT_TEMPLATES[tpl_name]
            with c2:
                if st.button("Append template"):
                    st.session_state["docs.ocr.prompt_global"] = (st.session_state.get("docs.ocr.prompt_global", "") + "\n\n" + OCR_PROMPT_TEMPLATES[tpl_name]).strip()

            st.session_state["docs.ocr.prompt_global"] = st.text_area(t("ocr_prompt"), value=st.session_state.get("docs.ocr.prompt_global", ""), height=140)
            st.caption("Per-file OCR prompt overrides (if provided in the queue) will override this global prompt for those files.")

        if st.button(t("execute_ocr")):
            try:
                execute_ocr()
                st.success("OCR complete.")
            except Exception as e:
                st.error(str(e))

    with st.expander(t("consolidated"), expanded=True):
        aid = st.session_state.get("consolidated.artifact_id")
        if not aid and st.session_state.get("docs.consolidated_markdown"):
            aid = create_artifact(st.session_state["docs.consolidated_markdown"], fmt="markdown", metadata={"source": "ocr_consolidation"})
            st.session_state["consolidated.artifact_id"] = aid

        if not aid:
            st.info("No consolidated OCR artifact yet.")
            return

        tabs = st.tabs(["Text", "Markdown", "Diff", "Versions"])
        cur_text, cur_meta = artifact_get_current(aid)

        with tabs[0]:
            new_text = st.text_area("Edit consolidated text", value=cur_text, height=240)
            if st.button("Save consolidated edit"):
                artifact_add_version(aid, new_text, created_by="user_edit", metadata={"type": "consolidated_edit"}, parent_version_id=cur_meta.get("version_id"))
                st.session_state["docs.consolidated_markdown"] = new_text
                safe_event("artifact", "info", "Consolidated OCR edited and versioned.")
                st.success("Saved.")

        with tabs[1]:
            st.markdown(markdown_highlight_keywords(cur_text, st.session_state.get("notes.keywords.palette", {})), unsafe_allow_html=True)

        with tabs[2]:
            versions = artifact_versions(aid)
            if len(versions) >= 2:
                prev = versions[-2]["content_text"]
                st.markdown(simple_diff(prev, cur_text), unsafe_allow_html=True)
            else:
                st.info("Need at least 2 versions for diff.")

        with tabs[3]:
            versions = artifact_versions(aid)
            for v in reversed(versions[-10:]):
                st.write(f"- {v['created_at']} | {v['created_by']} | {v['version_id'][:8]}")
            sel_vid = st.selectbox("Restore version", [v["version_id"] for v in versions][::-1])
            if st.button("Restore selected version"):
                st.session_state["artifacts"][aid]["current_version_id"] = sel_vid
                restored, _ = artifact_get_current(aid)
                st.session_state["docs.consolidated_markdown"] = restored
                safe_event("artifact", "warn", f"Restored consolidated version {sel_vid[:8]}.")
                st.success("Restored.")

        st.download_button("Download consolidated markdown", data=cur_text.encode("utf-8"), file_name="consolidated_ocr.md", mime="text/markdown")


# -----------------------------
# 15) UI: Right pane (intelligence deck)
# -----------------------------
def preflight_require(condition: bool, ok_msg: str, fail_msg: str) -> bool:
    if condition:
        st.success(ok_msg)
        return True
    st.error(fail_msg)
    return False


def render_agents_and_intelligence():
    load_agents_yaml_once()
    cfg = st.session_state.get("agents.yaml.validated")
    if cfg is None:
        cfg = validate_agents_yaml(st.session_state.get("agents.yaml.raw", ""))
        st.session_state["agents.yaml.validated"] = cfg
        if cfg:
            set_pipeline_state("agents_yaml", "done", f"Agents: {len(cfg.agents)}")
        else:
            set_pipeline_state("agents_yaml", "warn", "agents.yaml not validated yet.")

    tabs = st.tabs([t("agent_orchestration"), t("macro_summary"), t("dynamic_skill"), t("wow_ai"), t("search"), t("dashboards")])

    # ---- Agent Orchestration (plus upload/download/standardize) ----
    with tabs[0]:
        st.markdown("<div class='nordic-card'><span class='accent'>Agents</span><div class='muted'>Upload • Standardize • Edit • Validate • Download</div></div>", unsafe_allow_html=True)
        st.write("")

        # Upload/download UI
        c1, c2, c3 = st.columns([1.2, 1.2, 2.0])
        with c1:
            up = st.file_uploader(t("upload_yaml"), type=["yaml", "yml"], accept_multiple_files=False)
            if up is not None:
                raw_up = up.read().decode("utf-8", errors="replace")
                st.session_state["agents.yaml.original_upload"] = raw_up
                st.session_state["agents.yaml.raw"] = raw_up
                st.session_state["agents.yaml.validated"] = None
                st.session_state["agents.yaml.standardize_report"] = ""
                safe_event("agents", "info", "Uploaded agents.yaml")
                st.success("Uploaded. Validate or Standardize.")

        with c2:
            if st.button(t("standardize_yaml")):
                raw_in = st.session_state.get("agents.yaml.raw", "")
                std_yaml, report = standardize_agents_yaml(raw_in)
                st.session_state["agents.yaml.standardize_report"] = report
                st.session_state["agents.yaml.raw"] = std_yaml
                st.session_state["agents.yaml.validated"] = None
                safe_event("agents", "info", "Standardized agents.yaml")
                st.success("Standardized into canonical schema. Please review and validate.")

        with c3:
            st.download_button(
                t("download_yaml"),
                data=(st.session_state.get("agents.yaml.raw", "") or "").encode("utf-8"),
                file_name="agents.yaml",
                mime="text/yaml",
            )

        # Editor + report + diff
        orig = st.session_state.get("agents.yaml.original_upload")
        std_report = st.session_state.get("agents.yaml.standardize_report", "")
        raw = st.text_area(t("agents_yaml"), value=st.session_state.get("agents.yaml.raw", ""), height=260)
        st.session_state["agents.yaml.raw"] = raw

        if orig and std_report:
            with st.expander("Standardization Report + Diff", expanded=False):
                st.markdown(std_report)
                st.markdown("### Diff (Original → Standardized)")
                st.markdown(simple_diff(orig, raw), unsafe_allow_html=True)

        c4, c5 = st.columns([1, 2])
        with c4:
            if st.button(t("validate_yaml")):
                cfg = validate_agents_yaml(raw)
                st.session_state["agents.yaml.validated"] = cfg
                if cfg:
                    st.success(f"Validated. Agents: {len(cfg.agents)}")
                    safe_event("agents", "info", "agents.yaml validated.")
                    set_pipeline_state("agents_yaml", "done", f"Agents: {len(cfg.agents)}")
                else:
                    st.error(st.session_state.get("agents.last_error", "Validation failed."))
                    safe_event("agents", "err", f"agents.yaml validation failed: {st.session_state.get('agents.last_error')}")
                    set_pipeline_state("agents_yaml", "error", st.session_state.get("agents.last_error", ""))

        with c5:
            cfg = st.session_state.get("agents.yaml.validated")
            if cfg:
                st.caption("Agent Orchestration is ready. Run agents step-by-step below.")
            else:
                st.caption("Validate the YAML to enable agent execution. If your YAML is nonstandard, click Standardize YAML.")

        st.divider()
        cfg = st.session_state.get("agents.yaml.validated")
        consolidated = st.session_state.get("docs.consolidated_markdown", "") or ""
        consolidated_aid = st.session_state.get("consolidated.artifact_id")

        # Preflight
        st.markdown("### Preflight")
        preflight_require(bool(cfg), "agents.yaml validated.", "agents.yaml not validated.")
        preflight_require(bool(consolidated.strip()), "Consolidated OCR available.", "No consolidated OCR yet. Run OCR or provide manual input.")
        st.caption("You can still run an agent with manual input even if OCR is empty; select Manual Input below.")

        if not cfg:
            return

        # Choose agent
        agent_ids = [a.id for a in cfg.agents]
        selected_agent_id = st.selectbox("Select agent", agent_ids, format_func=lambda aid: next((a.name for a in cfg.agents if a.id == aid), aid))
        agent = next(a for a in cfg.agents if a.id == selected_agent_id)

        # Overrides before run
        ov = st.session_state["agents.step.overrides"].setdefault(agent.id, {})
        st.markdown("### Step Overrides (before run)")
        c1, c2, c3 = st.columns(3)
        with c1:
            ov["provider"] = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(ov.get("provider", agent.provider)))
        with c2:
            model_list = SUPPORTED_MODELS.get(ov["provider"], [])
            fallback_model = agent.model if agent.model in model_list else (model_list[0] if model_list else "gpt-4o-mini")
            ov["model"] = st.selectbox("Model", model_list, index=model_list.index(ov.get("model", fallback_model)) if model_list else 0)
        with c3:
            ov["max_tokens"] = st.number_input("max_tokens", min_value=256, max_value=32000, value=int(ov.get("max_tokens", agent.max_tokens or DEFAULT_MAX_TOKENS)), step=256)

        ov["temperature"] = st.slider("temperature", 0.0, 1.0, float(ov.get("temperature", agent.temperature if agent.temperature is not None else DEFAULT_TEMPERATURE)), 0.05)
        ov["system_prompt"] = st.text_area("System prompt", value=ov.get("system_prompt", agent.system_prompt or ""), height=110)
        ov["user_prompt"] = st.text_area("User prompt", value=ov.get("user_prompt", agent.user_prompt or ""), height=110)
        st.session_state["agents.step.overrides"][agent.id] = ov

        # Input builder
        st.markdown("### Input Builder")
        src = st.selectbox("Input source", ["consolidated_ocr", "previous_agent_output", "manual_paste", "combined"], index=0)
        context_parts = []
        manual = ""
        outs = st.session_state.get("agents.step.outputs", {}) or {}

        if src == "consolidated_ocr":
            context_parts.append(consolidated)
        elif src == "previous_agent_output":
            if not outs:
                st.warning("No previous agent outputs yet.")
            else:
                prev_id = st.selectbox("Select previous agent output", list(outs.keys()), format_func=lambda aid: next((a.name for a in cfg.agents if a.id == aid), aid))
                prev_art = outs[prev_id]
                prev_text, _ = artifact_get_current(prev_art)
                context_parts.append(prev_text)
        elif src == "manual_paste":
            manual = st.text_area("Manual input", height=140)
            context_parts.append(manual)
        else:
            include_consolidated = st.checkbox("Include consolidated OCR", value=bool(consolidated.strip()))
            include_prev = st.checkbox("Include previous agent output", value=bool(outs))
            include_manual = st.checkbox("Include manual paste", value=False)
            if include_consolidated:
                context_parts.append(consolidated)
            if include_prev and outs:
                prev_id = st.selectbox("Previous output", list(outs.keys()), format_func=lambda aid: next((a.name for a in cfg.agents if a.id == aid), aid))
                prev_art = outs[prev_id]
                prev_text, _ = artifact_get_current(prev_art)
                context_parts.append(prev_text)
            if include_manual:
                manual = st.text_area("Manual input", height=120)
                context_parts.append(manual)

        context = "\n\n".join([p for p in context_parts if p and p.strip()])
        st.caption(f"Context size: {len(context)} chars (~{approx_tokens(context)} tok est)")

        # Run agent
        if st.button("Run Agent"):
            if not context.strip():
                st.error("Empty context. Select a valid input source or paste manual input.")
            else:
                try:
                    set_pipeline_state("agents", "running", f"Running agent {agent.id}...")
                    out, meta = llm_execute(
                        provider=ov["provider"],
                        model=ov["model"],
                        system_prompt=ov["system_prompt"],
                        user_prompt=ov["user_prompt"],
                        context=context,
                        max_tokens=int(ov["max_tokens"]),
                        temperature=float(ov["temperature"]),
                    )
                    meta["kind"] = "agent_run"
                    artifact_id = create_artifact(out, fmt="markdown", metadata=meta)
                    st.session_state["agents.step.outputs"][agent.id] = artifact_id
                    node = timeline_add_node("agent_run", agent.name, artifact_id, meta)
                    # connect consolidated node if exists
                    if consolidated_aid:
                        if not st.session_state.get("timeline.consolidated_node_id"):
                            cn = timeline_add_node("ocr_consolidated", "Consolidated OCR", consolidated_aid, {"chars": len(consolidated)})
                            st.session_state["timeline.consolidated_node_id"] = cn
                        timeline_add_edge(st.session_state["timeline.consolidated_node_id"], node, "context")
                    set_pipeline_state("agents", "done", f"Agent {agent.id} done.")
                    st.success("Agent completed.")
                    safe_event("agents", "info", f"Agent run completed: {agent.id}")
                except Exception as e:
                    set_pipeline_state("agents", "error", str(e))
                    safe_event("agents", "err", f"Agent failed: {e}")
                    st.error(str(e))

        # Output editor
        out_aid = st.session_state.get("agents.step.outputs", {}).get(agent.id)
        if out_aid:
            st.divider()
            st.markdown("### Agent Output (editable handoff)")
            out_tabs = st.tabs(["Text", "Markdown", "Diff", "Versions"])
            out_text, out_meta = artifact_get_current(out_aid)

            with out_tabs[0]:
                edited = st.text_area("Edit output", value=out_text, height=240)
                cA, cB = st.columns([1, 1])
                with cA:
                    if st.button("Save output edit"):
                        artifact_add_version(out_aid, edited, created_by="user_edit", metadata={"type": "agent_output_edit"}, parent_version_id=out_meta.get("version_id"))
                        safe_event("artifact", "info", f"Edited agent output versioned: {agent.id}")
                        st.success("Saved.")
                with cB:
                    if st.button("Commit as Next Input"):
                        # Commit is conceptual; input builder can pick previous agent output.
                        timeline_add_node("handoff_commit", f"Handoff committed from {agent.name}", out_aid, {"agent_id": agent.id})
                        safe_event("agents", "info", f"Committed output as next input: {agent.id}")
                        st.success("Committed. Select it as 'previous agent output' in next step.")

            with out_tabs[1]:
                st.markdown(markdown_highlight_keywords(out_text, st.session_state.get("notes.keywords.palette", {})), unsafe_allow_html=True)
            with out_tabs[2]:
                versions = artifact_versions(out_aid)
                if len(versions) >= 2:
                    st.markdown(simple_diff(versions[-2]["content_text"], out_text), unsafe_allow_html=True)
                else:
                    st.info("Need at least 2 versions for diff.")
            with out_tabs[3]:
                versions = artifact_versions(out_aid)
                for v in reversed(versions[-10:]):
                    st.write(f"- {v['created_at']} | {v['created_by']} | {v['version_id'][:8]}")
                sel_vid = st.selectbox("Restore version (agent output)", [v["version_id"] for v in versions][::-1], key=f"restore_agent_{agent.id}")
                if st.button("Restore selected (agent output)", key=f"restore_btn_{agent.id}"):
                    st.session_state["artifacts"][out_aid]["current_version_id"] = sel_vid
                    safe_event("artifact", "warn", f"Restored agent {agent.id} output version {sel_vid[:8]}.")
                    st.success("Restored.")

    # ---- Macro Summary ----
    with tabs[1]:
        st.markdown("<div class='nordic-card'><span class='accent'>Macro Summary</span><div class='muted'>Versioned report + persistent prompt revisions</div></div>", unsafe_allow_html=True)
        st.write("")

        cfg = st.session_state.get("agents.yaml.validated")
        outs = st.session_state.get("agents.step.outputs", {}) or {}
        consolidated = st.session_state.get("docs.consolidated_markdown", "") or ""

        # Preflight
        st.markdown("### Preflight")
        preflight_require(bool(get_effective_key("openai") or get_effective_key("gemini") or get_effective_key("anthropic") or get_effective_key("grok")),
                          "At least one provider key available.", "No provider keys available (env or session).")
        st.caption("Macro summary can use any provider/model you choose below.")

        src = st.selectbox("Macro summary input source", ["consolidated_ocr", "agent_output", "manual_paste"], index=0)
        context = ""
        if src == "consolidated_ocr":
            context = consolidated
        elif src == "agent_output":
            if outs and cfg:
                aid_sel = st.selectbox("Select agent output", list(outs.keys()), format_func=lambda x: next((a.name for a in cfg.agents if a.id == x), x))
                art_id = outs[aid_sel]
                context, _ = artifact_get_current(art_id)
            else:
                st.info("No agent outputs available.")
        else:
            context = st.text_area("Manual markdown/text", height=160)

        provider = st.selectbox("Provider", PROVIDERS, index=0, key="macro_provider")
        model = st.selectbox("Model", SUPPORTED_MODELS.get(provider, []), index=0, key="macro_model")
        max_tokens = st.number_input("max_tokens", min_value=256, max_value=32000, value=DEFAULT_MAX_TOKENS, step=256, key="macro_tokens")
        temperature = st.slider("temperature", 0.0, 1.0, 0.2, 0.05, key="macro_temp")

        # Try to find a macro agent in YAML for prompt defaults
        macro_agent = None
        if cfg:
            macro_agent = next((a for a in cfg.agents if "macro" in a.name.lower() or "3000" in (a.system_prompt or "").lower()), None)
            if not macro_agent:
                macro_agent = cfg.agents[-1]

        system_prompt = st.text_area(
            "System prompt (macro)",
            value=(macro_agent.system_prompt if macro_agent else "You are a regulatory writing engine. Output 3000–4000 words in Markdown."),
            height=120,
        )
        user_prompt = st.text_area(
            "User prompt (macro)",
            value=(macro_agent.user_prompt if macro_agent else "Write a comprehensive 3000–4000 word FDA-style analytical review report based strictly on the provided content."),
            height=120,
        )

        st.caption(f"Context size: {len(context)} chars (~{approx_tokens(context)} tok est)")
        if st.button("Generate Macro Summary"):
            if not context.strip():
                st.error("No context.")
            else:
                try:
                    set_pipeline_state("summary", "running", "Generating macro summary...")
                    out, meta = llm_execute(provider, model, system_prompt, user_prompt, context, int(max_tokens), float(temperature))
                    meta["kind"] = "macro_summary"
                    if not st.session_state.get("summary.artifact_id"):
                        sid = create_artifact(out, fmt="markdown", metadata=meta)
                        st.session_state["summary.artifact_id"] = sid
                    else:
                        sid = st.session_state["summary.artifact_id"]
                        cur, curm = artifact_get_current(sid)
                        artifact_add_version(sid, out, created_by="macro_agent", metadata=meta, parent_version_id=curm.get("version_id"))
                    timeline_add_node("macro_summary", "Macro Summary", st.session_state["summary.artifact_id"], meta)
                    set_pipeline_state("summary", "done", "Macro summary generated.")
                    safe_event("summary", "info", "Macro summary generated.")
                    st.success("Macro summary generated.")
                except Exception as e:
                    set_pipeline_state("summary", "error", str(e))
                    safe_event("summary", "err", f"Macro summary failed: {e}")
                    st.error(str(e))

        sid = st.session_state.get("summary.artifact_id")
        if not sid:
            st.info("No macro summary artifact yet.")
        else:
            st.divider()
            st.markdown("### Macro Summary Editor")
            s_tabs = st.tabs(["Text", "Markdown", "Diff", "Versions"])
            s_text, s_meta = artifact_get_current(sid)

            with s_tabs[0]:
                edited = st.text_area("Edit macro summary", value=s_text, height=280)
                if st.button("Save summary edit"):
                    artifact_add_version(sid, edited, created_by="user_edit", metadata={"type": "summary_edit"}, parent_version_id=s_meta.get("version_id"))
                    safe_event("summary", "info", "Macro summary edited.")
                    st.success("Saved.")

            with s_tabs[1]:
                st.markdown(markdown_highlight_keywords(s_text, st.session_state.get("notes.keywords.palette", {})), unsafe_allow_html=True)

            with s_tabs[2]:
                versions = artifact_versions(sid)
                if len(versions) >= 2:
                    st.markdown(simple_diff(versions[-2]["content_text"], s_text), unsafe_allow_html=True)
                else:
                    st.info("Need at least 2 versions for diff.")

            with s_tabs[3]:
                versions = artifact_versions(sid)
                for v in reversed(versions[-10:]):
                    st.write(f"- {v['created_at']} | {v['created_by']} | {v['version_id'][:8]}")
                sel_vid = st.selectbox("Restore version (summary)", [v["version_id"] for v in versions][::-1], key="restore_summary")
                if st.button("Restore selected (summary)"):
                    st.session_state["artifacts"][sid]["current_version_id"] = sel_vid
                    safe_event("summary", "warn", f"Restored summary version {sel_vid[:8]}.")
                    st.success("Restored.")

            st.divider()
            st.markdown("### " + t("persistent_prompt"))
            st.session_state["summary.persistent_prompt"] = st.text_area("Prompt to revise current summary", value=st.session_state.get("summary.persistent_prompt", ""), height=90)
            if st.button(t("run_persistent_prompt")):
                prompt = st.session_state.get("summary.persistent_prompt", "")
                if not prompt.strip():
                    st.warning("Empty prompt.")
                else:
                    try:
                        set_pipeline_state("summary", "running", "Applying persistent prompt...")
                        cur_text, curm = artifact_get_current(sid)
                        sys_p = "You are revising an FDA-style regulatory report. Preserve factuality. Update per instruction. Output Markdown."
                        usr_p = prompt.strip()
                        out, meta = llm_execute(provider, model, sys_p, usr_p, cur_text, int(max_tokens), float(temperature))
                        artifact_add_version(sid, out, created_by="persistent_prompt", metadata={"kind": "persistent_prompt", **meta}, parent_version_id=curm.get("version_id"))
                        timeline_add_node("summary_revision", "Summary Revision (Persistent Prompt)", sid, {"prompt_hash": sha256_hex(prompt), **meta})
                        set_pipeline_state("summary", "done", "Persistent prompt applied.")
                        safe_event("summary", "info", "Persistent prompt applied.")
                        st.success("Updated.")
                    except Exception as e:
                        set_pipeline_state("summary", "error", str(e))
                        safe_event("summary", "err", f"Persistent prompt failed: {e}")
                        st.error(str(e))

            st.download_button("Download macro summary", data=s_text.encode("utf-8"), file_name="macro_summary.md", mime="text/markdown")

    # ---- Dynamic Skill Execution ----
    with tabs[2]:
        st.markdown("<div class='nordic-card'><span class='accent'>Dynamic Skill Execution</span><div class='muted'>Paste a skill → run against current summary → artifact output</div></div>", unsafe_allow_html=True)
        st.write("")

        sid = st.session_state.get("summary.artifact_id")
        if not sid:
            st.info("Generate a macro summary first.")
        else:
            desc = st.text_area(t("skill_desc"), value=st.session_state.get("skills.last_description", ""), height=160)
            st.session_state["skills.last_description"] = desc

            provider = st.selectbox("Provider (skill)", PROVIDERS, index=0, key="skill_provider")
            model = st.selectbox("Model (skill)", SUPPORTED_MODELS.get(provider, []), index=0, key="skill_model")
            max_tokens = st.number_input("max_tokens (skill)", min_value=256, max_value=32000, value=DEFAULT_MAX_TOKENS, step=256, key="skill_tokens")
            temperature = st.slider("temperature (skill)", 0.0, 1.0, 0.2, 0.05, key="skill_temp")

            st.caption("Preflight: requires summary artifact and provider key.")
            if st.button(t("run_skill")):
                if not desc.strip():
                    st.error("Skill description is empty.")
                else:
                    try:
                        set_pipeline_state("wow_ai", "running", "Executing skill...")
                        summary_text, _ = artifact_get_current(sid)
                        system_prompt = desc.strip()
                        user_prompt = "Apply the skill precisely to the provided summary. Output Markdown. Do not invent facts."
                        out, meta = llm_execute(provider, model, system_prompt, user_prompt, summary_text, int(max_tokens), float(temperature))
                        aid = create_artifact(out, fmt="markdown", metadata={"kind": "skill_output", **meta, "skill_hash": sha256_hex(desc)})
                        st.session_state["skills.outputs"].append(aid)
                        timeline_add_node("skill_output", "Dynamic Skill Output", aid, {"skill_hash": sha256_hex(desc), **meta})
                        set_pipeline_state("wow_ai", "done", "Skill executed.")
                        safe_event("skills", "info", "Dynamic skill executed.")
                        st.success("Skill executed.")
                    except Exception as e:
                        set_pipeline_state("wow_ai", "error", str(e))
                        safe_event("skills", "err", f"Skill failed: {e}")
                        st.error(str(e))

            if st.session_state.get("skills.outputs"):
                st.divider()
                st.markdown("### Skill Result Cards")
                for i, aid in enumerate(reversed(st.session_state["skills.outputs"][-5:]), start=1):
                    text, _ = artifact_get_current(aid)
                    with st.expander(f"Skill Output #{i}", expanded=False):
                        st.markdown(markdown_highlight_keywords(text, st.session_state.get("notes.keywords.palette", {})), unsafe_allow_html=True)
                        st.download_button(f"Download Skill Output #{i}", data=text.encode("utf-8"), file_name=f"skill_output_{i}.md", mime="text/markdown")

    # ---- WOW AI ----
    with tabs[3]:
        st.markdown("<div class='nordic-card'><span class='accent'>WOW AI</span><div class='muted'>Evidence • Consistency • Risk • RTA • Claims</div></div>", unsafe_allow_html=True)
        st.write("")

        sid = st.session_state.get("summary.artifact_id")
        consolidated = st.session_state.get("docs.consolidated_markdown", "") or ""
        if not sid:
            st.info("Generate a macro summary first.")
            return
        summary_text, _ = artifact_get_current(sid)

        wow_tabs = st.tabs([t("evidence_mapper"), t("consistency_guardian"), t("risk_radar"), t("rta_gatekeeper"), t("claims_inspector")])

        # Evidence Mapper
        with wow_tabs[0]:
            st.caption("Preflight: requires consolidated OCR anchors + target artifact.")
            target = st.selectbox("Map evidence for", ["macro_summary", "selected_agent_output"], index=0, key="evi_target")
            target_text = summary_text
            cfg = st.session_state.get("agents.yaml.validated")
            outs = st.session_state.get("agents.step.outputs", {}) or {}
            if target == "selected_agent_output":
                if cfg and outs:
                    aid_sel = st.selectbox("Agent output", list(outs.keys()), format_func=lambda x: next((a.name for a in cfg.agents if a.id == x), x), key="evi_agent_sel")
                    art_id = outs[aid_sel]
                    target_text, _ = artifact_get_current(art_id)
                else:
                    st.info("No agent outputs available; using macro summary.")

            if st.button("Map Evidence"):
                try:
                    set_pipeline_state("wow_ai", "running", "Evidence mapping...")
                    md, rows = evidence_mapper_run(target_text)
                    aid = create_artifact(md, fmt="markdown", metadata={"kind": "evidence_map", "rows": len(rows)})
                    st.session_state["wow.evidence.artifact_id"] = aid
                    st.session_state["wow.evidence.rows"] = rows
                    timeline_add_node("wow_evidence_map", "WOW Evidence Map", aid, {"rows": len(rows)})
                    set_pipeline_state("wow_ai", "done", "Evidence mapping complete.")
                    safe_event("wow_ai", "info", "Evidence mapping completed.")
                    st.success("Evidence mapping complete.")
                except Exception as e:
                    set_pipeline_state("wow_ai", "error", str(e))
                    safe_event("wow_ai", "err", f"Evidence mapping failed: {e}")
                    st.error(str(e))

            aid = st.session_state.get("wow.evidence.artifact_id")
            if aid:
                md, _ = artifact_get_current(aid)
                st.markdown(md, unsafe_allow_html=True)
                rows = st.session_state.get("wow.evidence.rows", [])
                if pd is not None and rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.download_button("Download evidence map", data=md.encode("utf-8"), file_name="evidence_map.md", mime="text/markdown")

        # Consistency Guardian
        with wow_tabs[1]:
            if st.button("Run Consistency Check"):
                try:
                    set_pipeline_state("wow_ai", "running", "Consistency checking...")
                    md = consistency_guardian_run(summary_text)
                    aid = create_artifact(md, fmt="markdown", metadata={"kind": "consistency_report"})
                    st.session_state["wow.consistency.artifact_id"] = aid
                    timeline_add_node("wow_consistency", "WOW Consistency Report", aid, {})
                    set_pipeline_state("wow_ai", "done", "Consistency check complete.")
                    safe_event("wow_ai", "info", "Consistency check completed.")
                    st.success("Consistency check complete.")
                except Exception as e:
                    set_pipeline_state("wow_ai", "error", str(e))
                    safe_event("wow_ai", "err", f"Consistency check failed: {e}")
                    st.error(str(e))

            aid = st.session_state.get("wow.consistency.artifact_id")
            if aid:
                md, _ = artifact_get_current(aid)
                st.markdown(md, unsafe_allow_html=True)
                st.download_button("Download consistency report", data=md.encode("utf-8"), file_name="consistency_report.md", mime="text/markdown")

        # Risk Radar
        with wow_tabs[2]:
            evidence_rows = st.session_state.get("wow.evidence.rows")
            if st.button("Generate Risk Radar"):
                try:
                    set_pipeline_state("wow_ai", "running", "Generating risk radar...")
                    domains, md = risk_radar_run(summary_text, evidence_results=evidence_rows)
                    aid = create_artifact(md, fmt="markdown", metadata={"kind": "risk_radar"})
                    st.session_state["wow.risk.artifact_id"] = aid
                    st.session_state["wow.risk.domains"] = domains
                    timeline_add_node("wow_risk_radar", "WOW Risk Radar", aid, {"domains": domains})
                    set_pipeline_state("wow_ai", "done", "Risk radar complete.")
                    safe_event("wow_ai", "info", "Risk radar generated.")
                    st.success("Risk radar complete.")
                except Exception as e:
                    set_pipeline_state("wow_ai", "error", str(e))
                    safe_event("wow_ai", "err", f"Risk radar failed: {e}")
                    st.error(str(e))

            aid = st.session_state.get("wow.risk.artifact_id")
            if aid:
                md, _ = artifact_get_current(aid)
                domains = st.session_state.get("wow.risk.domains", {})
                if domains:
                    plot_radar(domains)
                st.markdown(md, unsafe_allow_html=True)
                st.download_button("Download risk radar", data=md.encode("utf-8"), file_name="risk_radar.md", mime="text/markdown")

        # RTA Gatekeeper (new)
        with wow_tabs[3]:
            if st.button("Run RTA Gatekeeper"):
                try:
                    set_pipeline_state("wow_ai", "running", "Running RTA gatekeeper...")
                    score, md = rta_gatekeeper_run(summary_text)
                    aid = create_artifact(md, fmt="markdown", metadata={"kind": "rta_gatekeeper", "score": score})
                    st.session_state["wow.rta.artifact_id"] = aid
                    st.session_state["wow.rta.score"] = score
                    timeline_add_node("wow_rta_gatekeeper", "WOW RTA Gatekeeper", aid, {"score": score})
                    set_pipeline_state("wow_ai", "done", "RTA gatekeeper complete.")
                    safe_event("wow_ai", "info", "RTA gatekeeper completed.")
                    st.success(f"RTA Gatekeeper complete. Score: {score}/100")
                except Exception as e:
                    set_pipeline_state("wow_ai", "error", str(e))
                    safe_event("wow_ai", "err", f"RTA gatekeeper failed: {e}")
                    st.error(str(e))

            aid = st.session_state.get("wow.rta.artifact_id")
            if aid:
                md, _ = artifact_get_current(aid)
                st.markdown(md, unsafe_allow_html=True)
                st.download_button("Download RTA report", data=md.encode("utf-8"), file_name="rta_gatekeeper.md", mime="text/markdown")

        # Labeling & Claims Inspector (new)
        with wow_tabs[4]:
            st.caption("Preflight: requires consolidated OCR (best for labeling extraction).")
            if st.button("Run Claims Inspector"):
                try:
                    set_pipeline_state("wow_ai", "running", "Running claims inspector...")
                    evidence_rows = st.session_state.get("wow.evidence.rows")
                    md, rows = labeling_claims_inspector_run(consolidated, summary_text, evidence_rows=evidence_rows)
                    aid = create_artifact(md, fmt="markdown", metadata={"kind": "claims_inspector", "rows": len(rows)})
                    st.session_state["wow.claims.artifact_id"] = aid
                    st.session_state["wow.claims.rows"] = rows
                    timeline_add_node("wow_claims_inspector", "WOW Claims Inspector", aid, {"rows": len(rows)})
                    set_pipeline_state("wow_ai", "done", "Claims inspector complete.")
                    safe_event("wow_ai", "info", "Claims inspector completed.")
                    st.success("Claims inspector complete.")
                except Exception as e:
                    set_pipeline_state("wow_ai", "error", str(e))
                    safe_event("wow_ai", "err", f"Claims inspector failed: {e}")
                    st.error(str(e))

            aid = st.session_state.get("wow.claims.artifact_id")
            if aid:
                md, _ = artifact_get_current(aid)
                st.markdown(md, unsafe_allow_html=True)
                rows = st.session_state.get("wow.claims.rows", [])
                if pd is not None and rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.download_button("Download claims report", data=md.encode("utf-8"), file_name="claims_inspector.md", mime="text/markdown")

    # ---- Search ----
    with tabs[4]:
        st.markdown("<div class='nordic-card'><span class='accent'>Search + Device Context</span><div class='muted'>Embedded datasets (510k/MDR/GUDID/Recall) with graceful empty states</div></div>", unsafe_allow_html=True)
        st.write("")

        if not st.session_state.get("data.loaded"):
            if st.button("Load datasets"):
                load_datasets_best_effort()
                st.success("Dataset load attempted. See counts below.")

        counts = st.session_state.get("data.counts", {})
        st.caption(f"Dataset counts: {counts}")

        query = st.text_input("Query", value=st.session_state.get("data.last_query", ""))
        if st.button("Search"):
            st.session_state["data.last_query"] = query
            res = fuzzy_search_all(query)
            st.session_state["data.last_results"] = res
            safe_event("search", "info", f"Search executed: '{query}'")
            st.success("Search complete.")

        res = st.session_state.get("data.last_results", {}) or {}
        if pd is not None and res:
            for name, df in res.items():
                st.markdown(f"### {name.upper()} results")
                if df is None:
                    st.info("No data.")
                elif getattr(df, "empty", True):
                    st.info("No matches.")
                else:
                    st.dataframe(df.head(25), use_container_width=True)
        elif query.strip():
            st.info("No results available (datasets may be missing or empty).")

        # Minimal 360° device view placeholder
        st.markdown("### 360° Device View (minimal placeholder)")
        dv = st.session_state.get("data.device_view", {}) or {}
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("MDR count", dv.get("mdr_count", 0))
        with c2:
            st.metric("Max Recall Class", dv.get("recall_max_class", 0))
        with c3:
            st.metric("GUDID flags", dv.get("gudid_flags", 0))
        st.caption("Integrate this with your dataset schema to compute real KPIs (K-number/product code linkage).")

    # ---- Dashboards ----
    with tabs[5]:
        dash_tabs = st.tabs([t("mission_control"), t("intel_board"), t("timeline"), t("logs"), t("export")])

        with dash_tabs[0]:
            st.markdown("<div class='nordic-card'><span class='accent'>Mission Control</span><div class='muted'>Pipeline state • Provider telemetry • Resource guardrails</div></div>", unsafe_allow_html=True)
            st.write("")
            ps = st.session_state.get("obs.pipeline_state", {})
            if pd is not None:
                rows = [{"node": k, "status": v.get("status"), "last_update": v.get("last_update"), "detail": v.get("detail")} for k, v in ps.items()]
                st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(columns=["node", "status", "last_update", "detail"]),
                             use_container_width=True, hide_index=True)
            else:
                st.write(ps)

            m = st.session_state.get("obs.metrics", {})
            st.markdown("#### Provider Telemetry (session)")
            calls = {p: int(m.get(f"{p}.calls", 0)) for p in PROVIDERS}
            st.write("Calls:", calls)
            st.write("Latency ms total:", {p: int(m.get(f"{p}.latency_ms_total", 0)) for p in PROVIDERS})
            st.write("Approx memory:", human_size(mem_estimate_bytes()))

        with dash_tabs[1]:
            st.markdown("<div class='nordic-card'><span class='accent'>Regulatory Intelligence Board</span><div class='muted'>Risk • RTA • Claims • Device context (summary)</div></div>", unsafe_allow_html=True)
            st.write("")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Risk Radar ready", "Yes" if st.session_state.get("wow.risk.artifact_id") else "No")
            with c2:
                score = st.session_state.get("wow.rta.score")
                st.metric("RTA Score", score if score is not None else "—")
            with c3:
                rows = st.session_state.get("wow.claims.rows") or []
                st.metric("Claims flagged", len(rows) if rows else "—")
            with c4:
                evi = st.session_state.get("wow.evidence.rows") or []
                mapped = sum(1 for r in evi if r.get("anchor_id")) if evi else 0
                st.metric("Evidence coverage", f"{mapped}/{len(evi)}" if evi else "—")

            domains = st.session_state.get("wow.risk.domains")
            if domains:
                st.markdown("#### Risk Radar (preview)")
                plot_radar(domains)

            # quick access outputs
            st.markdown("#### Latest WOW AI Outputs")
            for key, label in [
                ("wow.evidence.artifact_id", "Evidence Map"),
                ("wow.consistency.artifact_id", "Consistency Report"),
                ("wow.risk.artifact_id", "Risk Radar"),
                ("wow.rta.artifact_id", "RTA Gatekeeper"),
                ("wow.claims.artifact_id", "Claims Inspector"),
            ]:
                aid = st.session_state.get(key)
                if aid:
                    text, _ = artifact_get_current(aid)
                    with st.expander(label, expanded=False):
                        st.markdown(text, unsafe_allow_html=True)

        with dash_tabs[2]:
            st.markdown("<div class='nordic-card'><span class='accent'>Timeline / DAG</span><div class='muted'>Run traceability • nodes + edges • versioned artifacts</div></div>", unsafe_allow_html=True)
            st.write("")
            tl = st.session_state.get("agents.timeline", {"nodes": [], "edges": []})
            if pd is not None:
                st.markdown("#### Nodes")
                st.dataframe(pd.DataFrame(tl["nodes"]), use_container_width=True, hide_index=True)
                st.markdown("#### Edges")
                st.dataframe(pd.DataFrame(tl["edges"]), use_container_width=True, hide_index=True)
            else:
                st.write(tl)

        with dash_tabs[3]:
            st.markdown("<div class='nordic-card'><span class='accent'>Session Logs</span><div class='muted'>Redacted events • filters • export</div></div>", unsafe_allow_html=True)
            st.write("")
            events = st.session_state.get("obs.events", [])
            if pd is not None and events:
                df = pd.DataFrame(events)
                sev = st.multiselect("Severity filter", ["info", "warn", "err"], default=["info", "warn", "err"])
                comp = st.text_input("Component contains", value="")
                df2 = df[df["severity"].isin(sev)]
                if comp.strip():
                    df2 = df2[df2["component"].astype(str).str.contains(comp.strip(), case=False, na=False)]
                st.dataframe(df2, use_container_width=True, hide_index=True)
                st.download_button("Download logs (json)", data=json.dumps(events, ensure_ascii=False, indent=2).encode("utf-8"),
                                   file_name="session_logs.json", mime="application/json")
            else:
                st.write(events or "No logs yet.")

        with dash_tabs[4]:
            st.markdown("<div class='nordic-card'><span class='accent'>Export</span><div class='muted'>Build an audit-friendly bundle (session-scoped)</div></div>", unsafe_allow_html=True)
            st.write("")
            if st.button("Build export bundle"):
                bundle = {}
                caid = st.session_state.get("consolidated.artifact_id")
                if caid:
                    ctext, _ = artifact_get_current(caid)
                    bundle["consolidated_ocr.md"] = ctext

                sid = st.session_state.get("summary.artifact_id")
                if sid:
                    stext, _ = artifact_get_current(sid)
                    bundle["macro_summary.md"] = stext

                for k, fname in [
                    ("wow.evidence.artifact_id", "evidence_map.md"),
                    ("wow.consistency.artifact_id", "consistency_report.md"),
                    ("wow.risk.artifact_id", "risk_radar.md"),
                    ("wow.rta.artifact_id", "rta_gatekeeper.md"),
                    ("wow.claims.artifact_id", "claims_inspector.md"),
                ]:
                    aid = st.session_state.get(k)
                    if aid:
                        text, _ = artifact_get_current(aid)
                        bundle[fname] = text

                bundle["agents.yaml"] = st.session_state.get("agents.yaml.raw", "")
                bundle["session_logs.json"] = json.dumps(st.session_state.get("obs.events", []), ensure_ascii=False, indent=2)

                st.session_state["obs.export.ready"] = {"built_at": now_taipei_str(), "files": list(bundle.keys())}
                st.success(f"Bundle built with {len(bundle)} files.")
                for fn, content in bundle.items():
                    mime = "text/markdown" if fn.endswith(".md") else ("text/yaml" if fn.endswith(".yaml") else "application/json")
                    st.download_button(f"Download {fn}", data=(content.encode("utf-8") if isinstance(content, str) else content),
                                       file_name=fn, mime=mime)


# -----------------------------
# 16) Note Keeper (kept)
# -----------------------------
def render_note_keeper():
    st.markdown("<div class='nordic-card'><span class='accent'>AI Note Keeper</span><div class='muted'>Paste → organize → edit → AI magics + keyword coloring</div></div>", unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.session_state["notes.input_raw"] = st.text_area("Paste note (text/markdown)", value=st.session_state.get("notes.input_raw", ""), height=220)
        st.session_state["notes.prompt"] = st.text_area("Note transform prompt", value=st.session_state.get("notes.prompt", ""), height=110)

        prov = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(st.session_state.get("notes.model_provider", "openai")))
        st.session_state["notes.model_provider"] = prov
        model = st.selectbox("Model", SUPPORTED_MODELS.get(prov, []), index=0)
        st.session_state["notes.model"] = model

        max_tokens = st.number_input("max_tokens", min_value=256, max_value=32000, value=6000, step=256)
        temperature = st.slider("temperature", 0.0, 1.0, 0.2, 0.05)

        if st.button("Transform note to organized Markdown"):
            try:
                inp = st.session_state.get("notes.input_raw", "")
                if not inp.strip():
                    st.error("Empty note.")
                else:
                    sys_p = "You are an expert note organizer. Output clean Markdown. Do not invent facts."
                    usr_p = st.session_state.get("notes.prompt", "")
                    out, meta = llm_execute(prov, model, sys_p, usr_p, inp, int(max_tokens), float(temperature))
                    meta["kind"] = "note_transform"
                    if not st.session_state.get("notes.output_artifact_id"):
                        aid = create_artifact(out, fmt="markdown", metadata=meta)
                        st.session_state["notes.output_artifact_id"] = aid
                    else:
                        aid = st.session_state["notes.output_artifact_id"]
                        cur, curm = artifact_get_current(aid)
                        artifact_add_version(aid, out, created_by="note_transform", metadata=meta, parent_version_id=curm.get("version_id"))
                    st.session_state["notes.magics.history"].append({"magic": "transform", "ts": now_taipei_str(), "provider": prov, "model": model})
                    safe_event("note_keeper", "info", "Note transformed.")
                    st.success("Transformed.")
            except Exception as e:
                safe_event("note_keeper", "err", f"Note transform failed: {e}")
                st.error(str(e))

    with c2:
        st.markdown("### AI Magics")
        magics = [
            ("AI Formatting", "Rewrite into clearer Markdown structure with consistent headings."),
            ("AI Action Items", "Extract action items with owner and due date if present."),
            ("AI Compliance Checklist", "Generate a compliance checklist derived from the note."),
            ("AI Deficiency Finder", "Find missing information and potential regulatory gaps."),
            ("AI Keywords (Colored)", "Extract key terms and suggest colored keyword palette."),
            ("WOW Bullet-to-Brief", "Convert long notes into a 1-page executive brief with key bullets."),
            ("WOW Meeting-to-SOP", "Convert discussion into draft SOP steps (if applicable)."),
            ("WOW Risk Flags", "Flag potential risk statements and categorize severity."),
        ]
        magic = st.selectbox("Select magic", [m[0] for m in magics])
        st.caption(next((m[1] for m in magics if m[0] == magic), ""))

        if st.button("Run Magic"):
            aid = st.session_state.get("notes.output_artifact_id")
            if not aid:
                st.warning("Transform a note first.")
            else:
                try:
                    text, curm = artifact_get_current(aid)
                    prov = st.session_state.get("notes.model_provider", "openai")
                    model = st.session_state.get("notes.model", "gpt-4o-mini")
                    sys_p = "You are a helpful assistant. Output Markdown. Do not invent facts."
                    usr_p = f"Magic: {magic}\n\nApply this transformation to the provided note."
                    out, meta = llm_execute(prov, model, sys_p, usr_p, text, 6000, 0.2)
                    artifact_add_version(aid, out, created_by=f"magic:{magic}", metadata={"kind": "note_magic", "magic": magic, **meta}, parent_version_id=curm.get("version_id"))
                    st.session_state["notes.magics.history"].append({"magic": magic, "ts": now_taipei_str(), "provider": prov, "model": model})
                    safe_event("note_keeper", "info", f"Magic executed: {magic}")
                    st.success("Magic applied (new version created).")
                except Exception as e:
                    safe_event("note_keeper", "err", f"Magic failed: {e}")
                    st.error(str(e))

        st.markdown("### Keyword Coloring")
        palette = st.session_state.get("notes.keywords.palette", {})
        if pd is not None:
            dfp = pd.DataFrame([{"keyword": k, "color": v} for k, v in palette.items()])
            edited = st.data_editor(dfp, num_rows="dynamic", use_container_width=True, hide_index=True)
            new_palette = {}
            for _, row in edited.iterrows():
                kw = str(row.get("keyword", "")).strip()
                col = str(row.get("color", "")).strip()
                if kw and col:
                    new_palette[kw] = col
            st.session_state["notes.keywords.palette"] = new_palette
        else:
            st.json(palette)

    st.divider()
    aid = st.session_state.get("notes.output_artifact_id")
    if aid:
        st.markdown("## Note Output")
        tabs = st.tabs(["Text", "Markdown", "Diff", "Versions", "History"])
        text, meta = artifact_get_current(aid)

        with tabs[0]:
            edited = st.text_area("Edit note output", value=text, height=260)
            if st.button("Save note edit"):
                artifact_add_version(aid, edited, created_by="user_edit", metadata={"type": "note_edit"}, parent_version_id=meta.get("version_id"))
                safe_event("note_keeper", "info", "Note edited.")
                st.success("Saved.")
        with tabs[1]:
            st.markdown(markdown_highlight_keywords(text, st.session_state.get("notes.keywords.palette", {})), unsafe_allow_html=True)
        with tabs[2]:
            versions = artifact_versions(aid)
            if len(versions) >= 2:
                st.markdown(simple_diff(versions[-2]["content_text"], text), unsafe_allow_html=True)
            else:
                st.info("Need at least 2 versions for diff.")
        with tabs[3]:
            versions = artifact_versions(aid)
            for v in reversed(versions[-10:]):
                st.write(f"- {v['created_at']} | {v['created_by']} | {v['version_id'][:8]}")
            sel_vid = st.selectbox("Restore version (note)", [v["version_id"] for v in versions][::-1], key="restore_note")
            if st.button("Restore selected (note)"):
                st.session_state["artifacts"][aid]["current_version_id"] = sel_vid
                safe_event("note_keeper", "warn", f"Restored note version {sel_vid[:8]}.")
                st.success("Restored.")
        with tabs[4]:
            st.json(st.session_state.get("notes.magics.history", []))

        st.download_button("Download note markdown", data=text.encode("utf-8"), file_name="note.md", mime="text/markdown")
    else:
        st.info("No note output yet.")


# -----------------------------
# 17) Sidebar danger zone
# -----------------------------
def render_sidebar_danger_zone():
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### {t('danger_zone')}")
    st.sidebar.caption("Clear session docs, outputs, logs, and session-entered keys.")
    if st.sidebar.button(t("total_purge")):
        total_purge()
        st.rerun()


# -----------------------------
# 18) Main
# -----------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()
    inject_nordic_css()

    render_key_section()
    render_sidebar_danger_zone()

    render_header()
    render_status_strip()

    if st.session_state.get("ui.mode") == "note_keeper":
        render_note_keeper()
        return

    left, right = st.columns([1.06, 1.24], gap="large")
    with left:
        render_left_pane()
    with right:
        render_agents_and_intelligence()


if __name__ == "__main__":
    main()
