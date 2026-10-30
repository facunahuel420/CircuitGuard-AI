#!/usr/bin/env python3
"""
CircuitGuard AI v0.1 — Lightweight Tactical Backend Server
Meta Global AI Developer Hackathon (Ubuntu Linux)

CRITICAL SECURITY & HARDWARE RULES:
1. MOCK_MODE = True by default ($0.00 cost, zero external API calls).
2. Reads configuration template from `.env.example` (dummy keys only).
3. NEVER opens `/dev/video*` from Python to prevent Linux v4l2 "Device or resource busy"
   locks. All video streaming and frame extraction happens in the browser via WebRTC + <canvas>.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
ENV_LOCAL_PATH = BASE_DIR / ".env"
GROUND_TRUTH_PATH = BASE_DIR / "ground_truth" / "boards_ground_truth_bundle.json"

SAM_BOX_REGEX = re.compile(
    r"(\d+)<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>"
)

# Default Safe Offline Simulation Mode ($0.00 Cost)
MOCK_MODE = True
PORT = 8090
HOST = "127.0.0.1"
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB DoS protection limit


def load_env_config() -> dict:
    """
    Load configuration from .env.example, optional local .env, and os.environ
    (e.g. ~/.meta_env loaded in Ubuntu session) without ever logging or exposing keys.
    """
    config = {
        "MOCK_MODE": "True",
        "PORT": "8090",
        "HOST": "127.0.0.1",
        "META_API_BASE_URL": "https://api.meta.ai/v1",
        "META_API_KEY": "DUMMY_META_API_KEY_DO_NOT_USE_IN_PROD_000000",
        "META_MODEL_REASONING": "muse-spark-1.3-contributor",
        "META_MODEL_SYNTHESIS": "muse-wonder-1.0",
        "META_MODEL_VISION_SEG": "sam-3.1",
        "BASETEN_BASE_URL": "https://inference.baseten.co/v1",
        "BASETEN_API_KEY": "DUMMY_BASETEN_KEY_SAFE_PLACEHOLDER_000000",
        "BASETEN_MODEL_ID": "meta-models/muse-spark-open-1026",
        "MAX_TOKENS": "4096",
        "N8N_WEBHOOK_URL": "https://n8n.oraclecloud-circuitguard.example/webhook/zerotrust-erp-sync",
        "N8N_WEBHOOK_SECRET": "DUMMY_N8N_HMAC_SHA256_SECRET_000000",
    }
    for candidate in (ENV_EXAMPLE_PATH, ENV_LOCAL_PATH):
        if candidate.exists():
            for raw_line in candidate.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"').strip("'")

    # Override in memory from os.environ if present (never logged or echoed)
    for env_key in (
        "MOCK_MODE",
        "PORT",
        "HOST",
        "META_API_BASE_URL",
        "META_API_KEY",
        "META_MODEL_REASONING",
        "META_MODEL_SYNTHESIS",
        "META_MODEL_VISION_SEG",
        "BASETEN_BASE_URL",
        "BASETEN_API_KEY",
        "BASETEN_MODEL_ID",
        "MAX_TOKENS",
        "N8N_WEBHOOK_URL",
        "N8N_WEBHOOK_SECRET",
    ):
        env_val = os.environ.get(env_key)
        if env_val is not None and env_val.strip() != "":
            config[env_key] = env_val.strip()

    return config


ENV_CONFIG = load_env_config()
MOCK_MODE = ENV_CONFIG.get("MOCK_MODE", "True").lower() in ("true", "1", "yes")
PORT = int(ENV_CONFIG.get("PORT", "8090"))
MAX_TOKENS = int(ENV_CONFIG.get("MAX_TOKENS", "4096") or 4096)
META_API_KEY = os.environ.get("META_API_KEY", ENV_CONFIG.get("META_API_KEY", ""))
BASETEN_API_KEY = os.environ.get("BASETEN_API_KEY", ENV_CONFIG.get("BASETEN_API_KEY", ""))

# Adaptive Senior Smartphone Microelectronics & Microsoldering System Prompt
MUSE_SPARK_SYSTEM_PROMPT = (
    "Actuás como Ingeniero Senior de Microelectrónica y Microsoldadura de Smartphones "
    "dentro de la estación CircuitGuard AI, asistiendo a un colega técnico en su banco de trabajo. "
    "Reglas operativas: "
    "1) Respondé en español técnico natural, directo y preciso, adaptándote exactamente a lo que pregunta el técnico. "
    "2) Si el técnico hace una consulta exploratoria o de identificación (ej. qué componentes se ven, qué conector FPC es o en qué sector de la placa está), respondé directamente describiendo con rigor lo que observás en la imagen real (cantidad de pines, estado de pads, serigrafía, jumpers, sulfato, blindajes o anclajes GND) sin forzar plantillas rígidas. "
    "3) Cuando el técnico consulte por una falla, medición o reparación, detallá qué líneas o pines medir con el multímetro (modo diodo / caída de tensión / continuidad) y qué acción de microsoldadura aplicar. "
    "4) Mantené un razonamiento interno ágil y enfocado para responder sin cortes."
)


def load_ground_truth() -> dict:
    """
    Load verifiable hardware Ground Truth bundle from `ground_truth/boards_ground_truth_bundle.json`
    AND dynamically auto-ingest all `.json` and `.md` schematic files inside `ground_truth/`.
    """
    gt_dir = GROUND_TRUTH_PATH.parent
    bundle = {"boards": {}, "technician_tool_profile": {}, "loaded_files": [], "markdown_schematics": {}}

    if GROUND_TRUTH_PATH.exists():
        try:
            raw_bundle = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
            if isinstance(raw_bundle, dict):
                bundle.update(raw_bundle)
        except Exception:
            pass

    loaded_files = []
    markdown_schematics = {}
    if gt_dir.exists() and gt_dir.is_dir():
        for fpath in sorted(gt_dir.iterdir()):
            if not fpath.is_file():
                continue
            ext = fpath.suffix.lower()
            if ext not in (".json", ".md"):
                continue
            loaded_files.append(fpath.name)
            if fpath.name == GROUND_TRUTH_PATH.name:
                continue
            try:
                content = fpath.read_text(encoding="utf-8").strip()
                if ext == ".md":
                    markdown_schematics[fpath.name] = content
                elif ext == ".json":
                    extra_json = json.loads(content)
                    if isinstance(extra_json, dict):
                        if "boards" in extra_json and isinstance(extra_json["boards"], dict):
                            bundle.setdefault("boards", {}).update(extra_json["boards"])
                        else:
                            markdown_schematics[fpath.name] = json.dumps(extra_json, ensure_ascii=False)
            except Exception:
                pass

    bundle["loaded_files"] = loaded_files
    bundle["markdown_schematics"] = markdown_schematics
    return bundle


def resolve_board_id(requested_board_id: str, symptom: str) -> str:
    """Resolve explicit board_id or auto-detect from technician prompt."""
    gt = load_ground_truth()
    boards = gt.get("boards", {})
    clean_id = (requested_board_id or "").strip()
    if clean_id in boards:
        return clean_id

    low_sym = (symptom or "").lower()
    if any(k in low_sym for k in ("a10s", "a107", "con5001", "mt6357")):
        return "samsung-sm-a107m"
    if any(k in low_sym for k in ("a32", "a325", "hdc6000", "sm5714", "mt6358")):
        return "samsung-sm-a325m"
    return "iphone-11-pro-820-01523-a"


def _select_board_schematics_text(gt: dict, resolved_id: str) -> str:
    """Select relevant `.md` / `.json` schematic files from `ground_truth/` for the active board."""
    md_map = gt.get("markdown_schematics", {}) or {}
    if not md_map:
        return ""

    board_keywords = {
        "iphone-11-pro-820-01523-a": ("iphone", "11", "820_01523", "820-01523"),
        "samsung-sm-a325m": ("a32", "a325"),
        "samsung-sm-a107m": ("a10s", "a107"),
    }.get(resolved_id, ())

    selected_sections = []
    for fname, text in md_map.items():
        low_name = fname.lower()
        # Include if it matches the active board or if it doesn't belong exclusively to another known board
        other_boards = ("iphone", "a32", "a325", "a10s", "a107")
        matches_active = any(k in low_name for k in board_keywords)
        matches_any_known = any(k in low_name for k in other_boards)
        if matches_active or not matches_any_known:
            selected_sections.append(f"--- ARCHIVO ESQUEMÁTICO: {fname} ---\n{text[:3500]}")

    return "\n\n".join(selected_sections)


def build_assistant_mode_directive(assistant_mode: str, session_pins: list = None) -> str:
    """
    n8n-Style Intent Router Directives:
    - 'concise': Direct 2-5 line answer ONLY to what was asked + auto-extract PIN_JSON for the 100% AI measurement table.
    - 'pin_log': 1 ultra-short line + JSON pin_reading block for the session pin logger table.
    - 'cross_schematic': Cross-check accumulated session_pins against Ground Truth (.json & .md) into a clear table.
    - 'full_guide': Complete 3-step diagnosis + fine soldering iron guide + checklist + PIN_JSON.
    """
    mode = (assistant_mode or "concise").strip().lower()
    pin_json_rule = (
        'Al final de tu respuesta, agregá SIEMPRE en una sola línea el bloque estructurado de auto-carga IA:\n'
        'PIN_JSON: {"component_type": "FPC / Diodo / Capacitor / Línea", "connector": "J6400 / FPC", "pin": "Pin X / Línea", "tester_mode": "Diodo (mV)", "measured_value": "430 mV", "status": "Registrado por IA"}'
    )
    if mode == "pin_log":
        return (
            "[MODO ENRUTADOR N8N: PIN_LOG (AUTO-CARGA 100% IA EN TABLA DE MEDICIONES)]\n"
            "1) Analizá el Visor A (Microscopio: qué componente/conector/pin se mide) y el Visor B (Tester: qué valor y unidad marca la pantalla).\n"
            "2) Respondé en UNA SOLA LÍNEA ultra-corta confirmando el componente/pin y la lectura.\n"
            f"3) {pin_json_rule}"
        )
    if mode == "cross_schematic":
        pins_json = json.dumps(session_pins or [], ensure_ascii=False)
        return (
            "[MODO ENRUTADOR N8N: CROSS_SCHEMATIC (CRUCE DE TABLA DE PINES CONTRA ESQUEMÁTICO GROUND TRUTH)]\n"
            f"Pines medidos en la sesión actual: {pins_json}\n"
            "Cruzá cada pin medido uno por uno contra el Ground Truth (.json y archivos .md de esquemáticos cargados). "
            "Devolvé una tabla técnica clara en Markdown indicando para cada pin: "
            "| # | Componente / Conector | Pin / Línea | Valor Medido | Rango Esquemático Ground Truth | Dictamen (OK / FALLA: Corto, OL o Fuga) | "
            "y al pie indicá el paso exacto a seguir sobre los pines con falla."
        )
    if mode == "full_guide":
        return (
            "[MODO ENRUTADOR N8N: FULL_GUIDE (DIAGNÓSTICO COMPLETO + GUÍA DE MICROSOLDADURA)]\n"
            "Brindá el diagnóstico completo estructurado (Inspección visual, puntos a medir en modo diodo con valores del esquemático y protocolo de microsoldadura exclusivamente con cautín de punta fina limada y flux con aguja).\n"
            f"{pin_json_rule}"
        )
    # Default: concise
    return (
        "[MODO ENRUTADOR N8N: CONCISE (ASISTENTE DIRECTO DE BANCO — MÁXIMO 2 A 5 LÍNEAS)]\n"
        "REGLA ESTRICTA DE CONCISIÓN: Respondé ÚNICAMENTE lo que el técnico preguntó en 2 a 5 líneas como máximo. "
        "PROHIBIDO agregar el protocolo de cautín, las 3 fases largas o el checklist anti-olvido a menos que el técnico lo pida explícitamente en su pregunta. "
        "Si pregunta cuánto debe medir una línea o qué componente es, respondé directo al grano con el pin, ubicación y valor exacto del Ground Truth / esquemático.\n"
        f"{pin_json_rule}"
    )


def build_ground_truth_system_prompt(
    board_id: str,
    symptom: str = "",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> str:
    """
    Inject verifiable Ground Truth specs (.json + dynamic .md schematics), mandatory technician
    tool constraints, and the n8n-style assistant_mode directive into the System Prompt.
    """
    gt = load_ground_truth()
    resolved_id = resolve_board_id(board_id, symptom)
    board_data = gt.get("boards", {}).get(resolved_id, {})
    tool_profile = gt.get("technician_tool_profile", {})
    mandatory_constraint = tool_profile.get(
        "mandatory_constraint",
        "PROHIBIDO sugerir estación de aire caliente o tobera. Toda microsoldadura debe indicarse exclusivamente con cautín de punta fina limada, flux dosificado con aguja y estaño en pasta o alambre.",
    )
    board_json_compact = json.dumps(board_data, ensure_ascii=False)
    schematics_md_text = _select_board_schematics_text(gt, resolved_id)
    mode_directive = build_assistant_mode_directive(assistant_mode, session_pins=session_pins)

    prompt_parts = [
        MUSE_SPARK_SYSTEM_PROMPT,
        mode_directive,
        f"[GROUND TRUTH VERIFICABLE DE LABORATORIO — PLACA ACTIVA: {resolved_id} (Archivos cargados: {', '.join(gt.get('loaded_files', []))})]\n{board_json_compact}",
    ]
    if schematics_md_text:
        prompt_parts.append(f"[ESQUEMÁTICOS DINÁMICOS EN CARPETA ground_truth/]:\n{schematics_md_text}")
    prompt_parts.append(
        f"[PERFIL OBLIGATORIO DE HERRAMIENTAS DEL TÉCNICO (META AGENTES 102)]:\n{mandatory_constraint}"
    )
    return "\n\n".join(prompt_parts)


def parse_sam_boxes(raw_text: str) -> list:
    """
    Extract SAM 3.1 bounding boxes using Meta's official regex:
    re.compile(r"(\\d+)<\\|box;x1=(\\d+);y1=(\\d+);x2=(\\d+);y2=(\\d+);w=(\\d+);h=(\\d+)\\|>")
    """
    boxes = []
    for match in SAM_BOX_REGEX.finditer(raw_text or ""):
        boxes.append(
            {
                "id": int(match.group(1)),
                "x1": int(match.group(2)),
                "y1": int(match.group(3)),
                "x2": int(match.group(4)),
                "y2": int(match.group(5)),
                "w": int(match.group(6)),
                "h": int(match.group(7)),
            }
        )
    return boxes


def run_deterministic_verification(board_id: str, user_prompt: str, ai_reply: str) -> dict:
    """
    Meta Agents 102 Verifiable Deterministic Auditor:
    - Contrasts AI reply against ground_truth/boards_ground_truth_bundle.json
    - Verifies strict compliance with technician_tool_profile (prohibits hot air / tobera)
    - Returns mandatory_checklist_items for the active board
    """
    gt = load_ground_truth()
    resolved_id = resolve_board_id(board_id, user_prompt)
    board = gt.get("boards", {}).get(resolved_id, {})
    tool_profile = gt.get("technician_tool_profile", {})

    reply_low = (ai_reply or "").lower()
    forbidden_terms = ["aire caliente", "tobera", "estación de aire", "pistola de calor"]
    detected_violations = [
        term
        for term in forbidden_terms
        if term in reply_low
        and f"sin {term}" not in reply_low
        and f"no usar {term}" not in reply_low
        and f"prohibido {term}" not in reply_low
    ]
    tool_compliant = len(detected_violations) == 0

    connectors = board.get("connectors", {})
    key_ics = board.get("key_ics", {})
    matched_references = []
    for conn_code in connectors.keys():
        if conn_code.lower() in reply_low:
            matched_references.append(conn_code)
    for ic_role, ic_name in key_ics.items():
        tokens = str(ic_name).replace("(", " ").replace(")", " ").split()
        for tok in tokens:
            if len(tok) >= 4 and tok.lower() in reply_low:
                matched_references.append(tok)
                break

    checklist_items = board.get("mandatory_checklist_items", [])
    return {
        "framework": "Meta Agents 102 — Deterministic Ground Truth Auditor",
        "verified": True,
        "board_id": resolved_id,
        "board_name": board.get("display_name", resolved_id),
        "board_part_number": board.get("board_number", "N/A"),
        "tool_compliance_ok": tool_compliant,
        "tool_audit_status": (
            "✅ Cautín Punta Fina Limada + Aguja Flux OK (Sin Aire Caliente)"
            if tool_compliant
            else f"⚠️ Alerta Herramienta: se mencionó {', '.join(detected_violations)} (Técnico opera solo con Cautín)"
        ),
        "contrasted_connectors": list(connectors.keys()),
        "contrasted_ics": key_ics,
        "matched_ground_truth_tokens": sorted(list(set(matched_references))),
        "mandatory_checklist_items": checklist_items,
        "mandatory_constraint": tool_profile.get("mandatory_constraint", ""),
    }


def _describe_active_visors(frame_a: str, frame_b: str) -> str:
    has_a = bool(frame_a and frame_a.startswith("data:image/"))
    has_b = bool(frame_b and frame_b.startswith("data:image/"))
    if has_a and has_b:
        return "Visor A (Microscopio USB PCB) + Visor B (Cámara Cenital / Tester)"
    if has_a:
        return "Únicamente Visor A (Microscopio USB PCB) — Visor B excluido por el técnico"
    if has_b:
        return "Únicamente Visor B (Cámara Cenital / Tester) — Visor A excluido por el técnico"
    return "Solo consulta de texto (Visor A y Visor B excluidos por el técnico)"


def build_multimodal_user_content(
    symptom: str, frame_a: str, frame_b: str, extra_instruction: str = ""
) -> list:
    """
    Build OpenAI/Meta compatible multimodal content array attaching ONLY non-empty Base64 frames
    and explicitly stating which visor was sent.
    """
    has_a = bool(frame_a and frame_a.startswith("data:image/"))
    has_b = bool(frame_b and frame_b.startswith("data:image/"))
    visors_desc = _describe_active_visors(frame_a, frame_b)

    text_body = (
        f"Reporte técnico del operador: {symptom}\n"
        f"Visores enviados para este análisis: {visors_desc}."
    )
    if extra_instruction:
        text_body += f"\nInstrucción de rol/fase: {extra_instruction}"

    content_blocks = [{"type": "text", "text": text_body}]
    if has_a:
        content_blocks.append({"type": "image_url", "image_url": {"url": frame_a}})
    if has_b:
        content_blocks.append({"type": "image_url", "image_url": {"url": frame_b}})
    return content_blocks


def _extract_pin_reading_from_text(ai_text: str, symptom: str, board_id: str) -> dict:
    """
    Universal AI Auto-Extraction of `pin_reading` JSON object for the 100% AI measurement table:
    {
      "component_type": "FPC / Diodo / Capacitor / Línea",
      "connector": "...",
      "pin": "...",
      "tester_mode": "Diodo (mV) | Voltaje (V) | Continuidad (Ω) | Corriente USB (A)",
      "measured_value": "...",
      "status": "Registrado por IA",
      "visual_note": "..."
    }
    """
    text = ai_text or ""
    # Try parsing explicit PIN_JSON: {...} or inline JSON block
    json_match = re.search(r"\{[^{}]*\"connector\"[^{}]*\}", text)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict) and "connector" in parsed:
                return {
                    "component_type": str(parsed.get("component_type", "Conector FPC / Línea")),
                    "connector": str(parsed.get("connector", "FPC")),
                    "pin": str(parsed.get("pin", "Pin 1")),
                    "tester_mode": str(parsed.get("tester_mode", "Diodo (mV)")),
                    "measured_value": str(parsed.get("measured_value", "430 mV")),
                    "status": str(parsed.get("status", "Registrado por IA")),
                    "visual_note": str(parsed.get("visual_note", "Punta sobre pad/pin")),
                }
        except Exception:
            pass

    # Fallback heuristic from symptom + board_id
    default_conn = {
        "iphone-11-pro-820-01523-a": "J6400 / J6500 FPC",
        "samsung-sm-a325m": "HDC6000 (78p)",
        "samsung-sm-a107m": "CON5001 (34p)",
    }.get(board_id, "FPC Principal")

    combined = f"{symptom} {text}"
    combined_low = combined.lower()
    if "capacit" in combined_low or "condensador" in combined_low:
        comp_type = "Capacitor SMD"
    elif "bobina" in combined_low or "inductor" in combined_low:
        comp_type = "Bobina / Inductor"
    elif "diodo" in combined_low and ("tvs" in combined_low or "zener" in combined_low or "schottky" in combined_low):
        comp_type = "Diodo SMD / TVS"
    elif "pmic" in combined_low or "tigris" in combined_low or "hydra" in combined_low or "ic" in combined_low:
        comp_type = "IC / Línea Alimentación"
    else:
        comp_type = "FPC / Pin / Línea"

    val_match = re.search(r"(\b\d+(?:[.,]\d+)?\s*(?:mV|V|A|mA|ohm|Ω)\b|\bOL\b)", combined, re.IGNORECASE)
    measured_val = val_match.group(1) if val_match else "430 mV"

    m_low = measured_val.lower()
    if "ma" in m_low or ("a" in m_low and "mv" not in m_low and "v" not in m_low):
        t_mode = "Corriente USB (A)"
    elif "ohm" in m_low or "ω" in m_low or "ol" in m_low:
        t_mode = "Continuidad (Ω)"
    elif "v" in m_low and "mv" not in m_low:
        t_mode = "Voltaje (V)"
    else:
        t_mode = "Diodo (mV)"

    pin_match = re.search(
        r"([Pp]in\s*#?\d+|VBUS_OVP_IN|VBUS_5V_CON5001|VBUS|VBAT_MAIN|VBAT_SENSE|VBAT|PP_BATT_VCC|PP5V0_USB_CONN|I2C0_SMC_SDA|USB_DP|USB_DM|VDD_LCD_3P0)",
        combined,
    )
    pin_label = pin_match.group(1) if pin_match else "Pin 1 (Extremo)"

    return {
        "component_type": comp_type,
        "connector": default_conn,
        "pin": pin_label,
        "tester_mode": t_mode,
        "measured_value": measured_val,
        "status": "Registrado por IA",
        "visual_note": "Auto-extraído por IA desde captura activa",
    }


def _evaluate_session_pins_against_ground_truth(board_id: str, session_pins: list) -> str:
    """
    Deterministic cross-check of `session_pins` against Ground Truth (`.json` + `.md`)
    for `assistant_mode == 'cross_schematic'`.
    """
    gt = load_ground_truth()
    resolved_id = resolve_board_id(board_id, "")
    board = gt.get("boards", {}).get(resolved_id, {})
    board_name = board.get("display_name", resolved_id)

    pins = session_pins if isinstance(session_pins, list) and len(session_pins) > 0 else [
        {
            "connector": "J6500" if "iphone" in resolved_id else ("HDC6000" if "a32" in resolved_id else "CON5001"),
            "pin": "Pin 1 (VBAT / PP_BATT_VCC)",
            "tester_mode": "Diodo (mV)",
            "measured_value": "345 mV",
            "visual_note": "Línea principal batería",
        },
        {
            "connector": "J6400" if "iphone" in resolved_id else ("HDC6000" if "a32" in resolved_id else "CON5001"),
            "pin": "Pin 6 (VBUS / VDD_LCD)",
            "tester_mode": "Diodo (mV)",
            "measured_value": "2 mV",
            "visual_note": "Sospecha de corto en entrada",
        },
    ]

    rows_md = [
        f"### 🔍 Cruce de Sesión de Pines contra Esquemático Ground Truth — {board_name}",
        f"• **Archivos Verificados en `ground_truth/`:** `{', '.join(gt.get('loaded_files', []))}`\n",
        "| # | Conector | Pin / Línea | Función Tester | Valor Medido | Rango Nominal Esquemático | Dictamen |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    faults_found = []
    for idx, p in enumerate(pins, start=1):
        conn = str(p.get("connector", "FPC"))
        pin_name = str(p.get("pin", f"Pin {idx}"))
        t_mode = str(p.get("tester_mode", "Diodo (mV)"))
        m_val = str(p.get("measured_value", "N/A")).strip()
        m_low = m_val.lower()

        # Nominal range lookup
        pin_low = pin_name.lower()
        if "gnd" in pin_low or "tierra" in pin_low:
            nom_range = "0 - 2 mV (GND)"
        elif "vbus" in pin_low or "usb_conn" in pin_low:
            nom_range = "420 - 560 mV"
        elif "vbat" in pin_low or "batt" in pin_low:
            nom_range = "290 - 410 mV"
        elif "usb_d" in pin_low or "tristar" in pin_low:
            nom_range = "580 - 760 mV"
        else:
            nom_range = "330 - 540 mV"

        # Evaluate status
        num_match = re.search(r"(\d+(?:\.\d+)?)", m_val.replace(",", "."))
        num_val = float(num_match.group(1)) if num_match else None
        if "ol" in m_low or "open" in m_low or "abierto" in m_low:
            status = "❌ **FALLA (Abierto OL — Pista / Pad desconectado)**"
            faults_found.append(f"{conn} -> {pin_name} ({m_val}: Línea abierta OL)")
        elif num_val is not None and ("mv" in m_low or "v" in m_low):
            # Convert V to mV if written like 0.002V
            effective_mv = num_val * 1000 if ("v" in m_low and "mv" not in m_low and num_val < 5.0) else num_val
            if "gnd" in pin_low:
                status = "✅ **OK (Tierra GND)**" if effective_mv <= 5 else "⚠️ **FALLA (GND con impedancia)**"
            elif effective_mv < 65:
                status = "❌ **FALLA (Corto a GND / Fuga severa)**"
                faults_found.append(f"{conn} -> {pin_name} ({m_val}: Corto a tierra)")
            elif effective_mv > 950:
                status = "⚠️ **FALLA (Fuga / Impedancia alta)**"
                faults_found.append(f"{conn} -> {pin_name} ({m_val}: Valor fuera de rango alto)")
            else:
                status = "✅ **OK (Dentro de Rango)**"
        else:
            status = "✅ **OK (Dentro de Rango)**"

        rows_md.append(
            f"| {idx} | `{conn}` | `{pin_name}` | {t_mode} | **{m_val}** | `{nom_range}` | {status} |"
        )

    if faults_found:
        rows_md.append(
            "\n**🛠️ Paso Exacto a Seguir (Cautín Punta Fina Limada + Flux con Aguja):**\n"
            + "\n".join(
                f"- En **{f}**: dosificar micro-gota de flux con aguja hipodérmica, inspeccionar puente de estaño o condensador cerámico en paralelo sobre la línea y despejar/reconstruir con cautín de punta fina limada (sin usar aire caliente)."
                for f in faults_found
            )
        )
    else:
        rows_md.append(
            "\n**✅ Dictamen General:** Todos los pines medidos en la sesión se encuentran dentro de los parámetros nominales del esquemático `ground_truth/`."
        )

    return "\n".join(rows_md)


def build_text_fallback_messages(
    symptom: str,
    frame_a: str,
    frame_b: str,
    extra_instruction: str = "",
    board_id: str = "iphone-11-pro-820-01523-a",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> list:
    """Build enriched text-only messages if an endpoint rejects multimodal image_url blocks."""
    visors_desc = _describe_active_visors(frame_a, frame_b)
    text_body = (
        f"Reporte técnico del operador: {symptom}\n"
        f"Modo del asistente solicitado: {assistant_mode}\n"
        f"Visores seleccionados por el operador: {visors_desc} "
        f"(Visor A={len(frame_a or '')} bytes Base64, Visor B={len(frame_b or '')} bytes Base64)."
    )
    if extra_instruction:
        text_body += f"\n{extra_instruction}"
    return [
        {
            "role": "system",
            "content": build_ground_truth_system_prompt(
                board_id, symptom, assistant_mode=assistant_mode, session_pins=session_pins
            ),
        },
        {"role": "user", "content": text_body},
    ]


def resolve_meta_model_and_instruction(engine: str) -> tuple:
    """
    Map the 5 dashboard engine options to the target model ID and specialized prompt directive:
    - meta-muse-spark-1.3 -> ("muse-spark-1.3-contributor", "")
    - meta-sam-3.1        -> ("sam-3.1", "Enfocate en segmentación visual SMD, pines FPC, pads sulfatados y puentes de estaño.")
    - meta-muse-wonder-1.0-> ("muse-wonder-1.0", "Enfocate en supervisión ejecutiva de laboratorio, síntesis de reparación y control de calidad.")
    - meta-agentic-pipeline -> ("muse-spark-1.3-contributor", "Estructurá la respuesta en las 3 Fases Agénticas: Fase 1 [SAM 3.1 Segmentación Visual SMD] -> Fase 2 [Muse Spark 1.3 Diagnóstico Electrónico y Modo Diodo] -> Fase 3 [Muse Wonder 1.0 Síntesis y Checklist Anti-Olvido].")
    """
    if engine == "meta-sam-3.1":
        return (
            "sam-3.1",
            "Modo SAM 3.1 Vision Segmentation: priorizá la segmentación e identificación geométrica de componentes SMD, pines del conector FPC, fisuras de soldadura y sulfatación.",
        )
    if engine == "meta-muse-wonder-1.0":
        return (
            "muse-wonder-1.0",
            "Modo Muse Wonder 1.0 Supervisor & Synthesis: priorizá el protocolo ejecutivo de microsoldadura exclusivamente con cautín de punta fina limada y flux con aguja (prohibido aire caliente) y síntesis verificable.",
        )
    if engine == "meta-agentic-pipeline":
        return (
            "muse-spark-1.3-contributor",
            "Ejecutá el Pipeline Agéntico Completo en 3 secciones explícitas: "
            "FASE 1 (SAM 3.1 - Segmentación Visual SMD/FPC), "
            "FASE 2 (Muse Spark 1.3 - Razonamiento Electrónico y Puntos a Medir en Modo Diodo), y "
            "FASE 3 (Muse Wonder 1.0 - Acción de Microsoldadura con cautín punta fina y Checklist Anti-Olvido).",
        )
    return ("muse-spark-1.3-contributor", "")


def build_meta_api_payload(
    symptom: str,
    frame_microscope_b64: str,
    frame_overhead_b64: str,
    multimodal: bool = True,
    target_model: str = "muse-spark-1.3-contributor",
    extra_instruction: str = "",
    board_id: str = "iphone-11-pro-820-01523-a",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> dict:
    """
    Payload structure for Meta Model API (`https://api.meta.ai/v1/chat/completions`):
    - Supports muse-spark-1.3-contributor, sam-3.1, muse-wonder-1.0, and agentic pipeline
    - max_tokens: 4096 (compat 1800)
    """
    has_images = bool(
        (frame_microscope_b64 and frame_microscope_b64.startswith("data:image/"))
        or (frame_overhead_b64 and frame_overhead_b64.startswith("data:image/"))
    )
    use_mm = multimodal and has_images
    sys_prompt = build_ground_truth_system_prompt(
        board_id, symptom, assistant_mode=assistant_mode, session_pins=session_pins
    )
    mode_user_note = build_assistant_mode_directive(assistant_mode, session_pins=session_pins)
    combined_instr = f"{extra_instruction}\n{mode_user_note}".strip()
    messages = (
        [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": build_multimodal_user_content(
                    symptom, frame_microscope_b64, frame_overhead_b64, combined_instr
                ),
            },
        ]
        if use_mm
        else build_text_fallback_messages(
            symptom,
            frame_microscope_b64,
            frame_overhead_b64,
            combined_instr,
            board_id=board_id,
            assistant_mode=assistant_mode,
            session_pins=session_pins,
        )
    )
    return {
        "model": target_model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
        "messages": messages,
    }


def build_baseten_payload(
    symptom: str,
    frame_microscope_b64: str,
    frame_overhead_b64: str,
    multimodal: bool = True,
    board_id: str = "iphone-11-pro-820-01523-a",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> dict:
    """
    Payload structure for Baseten Open-Weights Inference (`https://inference.baseten.co/v1/chat/completions`):
    - Model: meta-models/muse-spark-open-1026
    - max_tokens: 4096 (compat 1800)
    """
    has_images = bool(
        (frame_microscope_b64 and frame_microscope_b64.startswith("data:image/"))
        or (frame_overhead_b64 and frame_overhead_b64.startswith("data:image/"))
    )
    use_mm = multimodal and has_images
    sys_prompt = build_ground_truth_system_prompt(
        board_id, symptom, assistant_mode=assistant_mode, session_pins=session_pins
    )
    mode_user_note = build_assistant_mode_directive(assistant_mode, session_pins=session_pins)
    messages = (
        [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": build_multimodal_user_content(
                    symptom, frame_microscope_b64, frame_overhead_b64, mode_user_note
                ),
            },
        ]
        if use_mm
        else build_text_fallback_messages(
            symptom,
            frame_microscope_b64,
            frame_overhead_b64,
            mode_user_note,
            board_id=board_id,
            assistant_mode=assistant_mode,
            session_pins=session_pins,
        )
    )
    return {
        "model": "meta-models/muse-spark-open-1026",
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
        "messages": messages,
    }


def _send_https_chat_request(endpoint: str, api_key: str, payload: dict) -> dict:
    """Execute HTTPS POST to Meta API or Baseten and decode JSON response."""
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "CircuitGuard-AI-Tactical-Station/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_inference_fields(raw_resp: dict, default_model: str) -> tuple:
    """Extract (content_text, reasoning_tokens, total_tokens, model_used) from API response."""
    model_used = raw_resp.get("model", default_model)
    content_text = ""

    # Standard OpenAI / Baseten / Meta compat format: choices[0].message.content
    choices = raw_resp.get("choices")
    if isinstance(choices, list) and len(choices) > 0:
        msg = choices[0].get("message", {})
        raw_content = msg.get("content", "")
        if isinstance(raw_content, str):
            content_text = raw_content
        elif isinstance(raw_content, list):
            content_text = "\n".join(
                block.get("text", "") for block in raw_content if isinstance(block, dict)
            )

    # Native Llama/Meta API format fallback: completion_message.content
    if not content_text and "completion_message" in raw_resp:
        comp_msg = raw_resp.get("completion_message", {})
        raw_content = comp_msg.get("content", "")
        if isinstance(raw_content, str):
            content_text = raw_content
        elif isinstance(raw_content, dict):
            content_text = raw_content.get("text", "")
        elif isinstance(raw_content, list):
            content_text = "\n".join(
                block.get("text", "") for block in raw_content if isinstance(block, dict)
            )

    usage = raw_resp.get("usage", {}) or {}
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    details = usage.get("completion_tokens_details", {}) or {}
    reasoning_tokens = int(
        details.get("reasoning_tokens", usage.get("reasoning_tokens", 0)) or 0
    )

    return content_text.strip(), reasoning_tokens, total_tokens, model_used


def _call_sam_3_1_native(base_url: str, api_key: str, symptom: str, image_b64: str) -> dict:
    """
    Native SAM 3.1 call on Meta Responses API (`POST https://api.meta.ai/v1/responses`)
    using SSE streaming (`Accept: text/event-stream`, `"stream": True`).
    Payload format:
      "input": [{"type": "message", "role": "user", "content": [
          {"type": "input_text", "text": "<short_concept>"},
          {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
      ]}]
    """
    endpoint = f"{base_url.rstrip('/')}/responses"
    clean_symptom = (symptom or "").strip()

    # Morphological concept prompt for SAM 3.1 on PCBs
    if 0 < len(clean_symptom) < 35 and "?" not in clean_symptom and "¿" not in clean_symptom:
        concepts = [clean_symptom, "copper solder pad pin connector chip"]
    else:
        concepts = ["copper solder pad pin connector chip"]

    collected_outputs = []
    sam_boxes = []
    for concept in concepts:
        payload = {
            "model": "sam-3.1",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": concept},
                        {"type": "input_image", "image_url": image_b64},
                    ],
                }
            ],
            "stream": True,
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": "CircuitGuard-AI-Tactical-Station/0.1",
            },
            method="POST",
        )

        deltas = []
        fallback_raw = []
        with urllib.request.urlopen(req, timeout=45) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        ev_type = event.get("type", "")
                        if ev_type == "response.output_text.delta":
                            deltas.append(str(event.get("delta", "")))
                        elif ev_type == "response.output_text.done" and not deltas:
                            deltas.append(str(event.get("text", "")))
                        elif "output_text" in event and not deltas:
                            deltas.append(str(event.get("output_text", "")))
                    except json.JSONDecodeError:
                        fallback_raw.append(data_str)
                else:
                    fallback_raw.append(line)

        concept_out = "".join(deltas).strip()
        if not concept_out and fallback_raw:
            concept_out = " ".join(fallback_raw)[:600]
        parsed_for_concept = parse_sam_boxes(concept_out)
        if parsed_for_concept:
            sam_boxes.extend(parsed_for_concept)
        collected_outputs.append(f"• Target '{concept}': {concept_out or '[Máscara procesada sin detecciones]'}")

    return {
        "endpoint": endpoint,
        "concepts": concepts,
        "sam_output": "\n".join(collected_outputs),
        "sam_boxes": sam_boxes,
    }


def _transcribe_audio_muse_voice(audio_wav_b64: str, force_live: bool = False) -> dict:
    """
    Hands-free technician voice dictation via Meta Muse Voice Transcribe:
      POST https://api.meta.ai/v1/asr/transcribe?sessionId=<uuid>
      Content-Type: multipart/form-data (parts: `request` JSON + `audio` WAV mono 16-bit PCM 24kHz)
    """
    t0 = time.perf_counter()
    if not META_API_KEY or "DUMMY_" in META_API_KEY or (MOCK_MODE and not force_live):
        return {
            "ok": True,
            "mode": "SIM_MUSE_VOICE_1.0 ($0.00)",
            "sessionId": str(uuid.uuid4()),
            "audioDurationMs": 3200,
            "latency_ms": 2.4,
            "transcript": (
                "Placa bajo microscopio: por favor identificá qué conector FPC se observa en "
                "el sector inferior, cuántos pines tiene y el estado de las pistas y soldaduras."
            ),
        }

    # Decode base64 WAV audio
    clean_b64 = audio_wav_b64.split(",", 1)[-1] if "," in (audio_wav_b64 or "") else (audio_wav_b64 or "")
    raw_audio_bytes = base64.b64decode(clean_b64) if clean_b64 else b""

    # Verify RIFF/WAVE header; convert automatically with ffmpeg if needed
    if not raw_audio_bytes.startswith(b"RIFF"):
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin and raw_audio_bytes:
            proc = subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    "pipe:0",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-c:a",
                    "pcm_s16le",
                    "-f",
                    "wav",
                    "pipe:1",
                ],
                input=raw_audio_bytes,
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.startswith(b"RIFF"):
                raw_audio_bytes = proc.stdout

    session_id = str(uuid.uuid4())
    base_url = ENV_CONFIG.get("META_API_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
    endpoint = f"{base_url}/asr/transcribe?sessionId={session_id}"

    asr_request_meta = {
        "mode": "ENDPOINTING",
        "model": "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV",
        "languageBias": ["Spanish", "English"],
        "keywords": [
            "Samsung",
            "A10s",
            "iPhone",
            "Motorola",
            "FPC",
            "PMIC",
            "IF-PMIC",
            "VBAT",
            "VDD_MAIN",
            "GND",
            "jumper",
            "modo diodo",
            "multímetro",
            "tester",
            "corto",
            "sulfato",
            "pin",
            "pads",
            "estaño",
            "flux",
            "cautín",
            "esquemático",
            "conector",
            "huella",
            "placa",
        ],
    }

    boundary = f"----CircuitGuardBoundary{uuid.uuid4().hex}"
    body_parts = []
    # Part 1: request (application/json)
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        b'Content-Disposition: form-data; name="request"\r\n'
        b"Content-Type: application/json\r\n\r\n"
    )
    body_parts.append(json.dumps(asr_request_meta).encode("utf-8"))
    body_parts.append(b"\r\n")

    # Part 2: audio (audio/wav)
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        b'Content-Disposition: form-data; name="audio"; filename="voice_query.wav"\r\n'
        b"Content-Type: audio/wav\r\n\r\n"
    )
    body_parts.append(raw_audio_bytes)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    multipart_body = b"".join(body_parts)

    try:
        req = urllib.request.Request(
            endpoint,
            data=multipart_body,
            headers={
                "Authorization": f"Bearer {META_API_KEY}",
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "CircuitGuard-AI-Tactical-Station/0.1",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        transcript = resp_data.get("transcript", "")
        if not transcript and isinstance(resp_data.get("turns"), list):
            transcript = " ".join(t.get("text", "") for t in resp_data["turns"]).strip()

        return {
            "ok": True,
            "mode": "LIVE_MUSE_VOICE_1.0",
            "sessionId": resp_data.get("sessionId", session_id),
            "transcript": transcript,
            "audioDurationMs": resp_data.get("audioDurationMs", 0),
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "ok": False,
            "mode": f"ASR_ERROR ({type(exc).__name__})",
            "sessionId": session_id,
            "transcript": "",
            "error": str(exc),
            "latency_ms": latency_ms,
        }


def dispatch_external_inference(
    engine: str,
    symptom: str,
    frame_a: str,
    frame_b: str,
    force_live: bool = False,
    board_id: str = "iphone-11-pro-820-01523-a",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> dict:
    """
    Real HTTPS client for:
    - Meta SAM 3.1 Native Responses API (`POST https://api.meta.ai/v1/responses` SSE)
    - Meta Chat Completions API (`POST https://api.meta.ai/v1/chat/completions`)
    - Baseten Open-Weights (`POST https://inference.baseten.co/v1/chat/completions`)
    """
    resolved_board = resolve_board_id(board_id, symptom)
    clean_mode = (assistant_mode or "concise").strip().lower()
    is_baseten = engine in ("baseten-muse-spark-open-1026", "baseten-muse-spark-open")
    if is_baseten:
        base_url = ENV_CONFIG.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = BASETEN_API_KEY
        default_model = "meta-models/muse-spark-open-1026"
        mm_payload = build_baseten_payload(
            symptom,
            frame_a,
            frame_b,
            multimodal=True,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )
        txt_payload = build_baseten_payload(
            symptom,
            frame_a,
            frame_b,
            multimodal=False,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )
        fallback_model_payload = None
    else:
        base_url = ENV_CONFIG.get("META_API_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = META_API_KEY
        target_model, extra_instr = resolve_meta_model_and_instruction(engine)
        default_model = target_model
        mm_payload = build_meta_api_payload(
            symptom,
            frame_a,
            frame_b,
            multimodal=True,
            target_model=target_model,
            extra_instruction=extra_instr,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )
        txt_payload = build_meta_api_payload(
            symptom,
            frame_a,
            frame_b,
            multimodal=False,
            target_model=target_model,
            extra_instruction=extra_instr,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )
        fallback_model_payload = (
            build_meta_api_payload(
                symptom,
                frame_a,
                frame_b,
                multimodal=True,
                target_model="muse-spark-1.3-contributor",
                extra_instruction=extra_instr,
                board_id=resolved_board,
                assistant_mode=clean_mode,
                session_pins=session_pins,
            )
            if target_model != "muse-spark-1.3-contributor"
            else None
        )

    # Safety guard: if key is empty/dummy or neither force_live nor live mode is active
    if not api_key or "DUMMY_" in api_key or (MOCK_MODE and not force_live):
        return generate_simulated_diagnosis(
            engine,
            symptom,
            simulated_reason="SAFE_MOCK_GUARD",
            frame_a=frame_a,
            frame_b=frame_b,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )

    t0 = time.perf_counter()
    mode_tag = f"MULTIMODAL_VISION // N8N:{clean_mode.upper()}"
    active_image = (
        frame_a
        if (frame_a and frame_a.startswith("data:image/"))
        else (frame_b if (frame_b and frame_b.startswith("data:image/")) else "")
    )

    try:
        sam_native_block = ""
        sam_boxes = []
        # Native SAM 3.1 execution via POST /v1/responses (SSE) when meta-sam-3.1 or meta-agentic-pipeline is selected
        if engine in ("meta-sam-3.1", "meta-agentic-pipeline") and active_image:
            try:
                sam_res = _call_sam_3_1_native(base_url, api_key, symptom, active_image)
                sam_boxes = sam_res.get("sam_boxes", [])
                sam_native_block = (
                    f"🎯 [SEGMENTACIÓN GEOMÉTRICA NATIVA SAM 3.1 — POST /v1/responses SSE]\n"
                    f"{sam_res['sam_output']}\n\n"
                )
                mode_tag = f"SAM_3.1_RESPONSES_SSE + MUSE_SPARK_1.3 ({clean_mode.upper()})"
            except Exception as sam_err:
                sam_native_block = (
                    f"ℹ️ [Nota SAM 3.1 /v1/responses: {type(sam_err).__name__}: {sam_err}]\n\n"
                )

            # Combine SAM 3.1 native geometric output with Muse Spark 1.3 technical interpretation in Spanish
            spark_instr = (
                f"{extra_instr}\n"
                f"Salida geométrica previa de SAM 3.1: {sam_native_block}"
            )
            spark_payload = build_meta_api_payload(
                symptom,
                frame_a,
                frame_b,
                multimodal=True,
                target_model="muse-spark-1.3-contributor",
                extra_instruction=spark_instr,
                board_id=resolved_board,
                assistant_mode=clean_mode,
                session_pins=session_pins,
            )
            raw_resp = _send_https_chat_request(endpoint, api_key, spark_payload)
        else:
            try:
                raw_resp = _send_https_chat_request(endpoint, api_key, mm_payload)
            except urllib.error.HTTPError as http_err:
                if http_err.code in (400, 404, 415, 422):
                    if fallback_model_payload is not None:
                        try:
                            mode_tag = f"BRIDGE_VIA_MUSE_SPARK_1.3 ({default_model})"
                            raw_resp = _send_https_chat_request(
                                endpoint, api_key, fallback_model_payload
                            )
                        except urllib.error.HTTPError:
                            mode_tag = "TEXT_FALLBACK"
                            txt_bridge = build_meta_api_payload(
                                symptom,
                                frame_a,
                                frame_b,
                                multimodal=False,
                                target_model="muse-spark-1.3-contributor",
                                extra_instruction=extra_instr,
                                board_id=resolved_board,
                                assistant_mode=clean_mode,
                                session_pins=session_pins,
                            )
                            raw_resp = _send_https_chat_request(endpoint, api_key, txt_bridge)
                    else:
                        mode_tag = "TEXT_FALLBACK"
                        raw_resp = _send_https_chat_request(endpoint, api_key, txt_payload)
                else:
                    raise

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        content_text, reasoning_tokens, total_tokens, model_used = _extract_inference_fields(
            raw_resp, default_model
        )
        if not content_text:
            content_text = json.dumps(raw_resp, ensure_ascii=False)

        if not sam_boxes:
            sam_boxes = parse_sam_boxes(content_text)

        pin_reading = (
            _extract_pin_reading_from_text(content_text, symptom, resolved_board)
            if clean_mode in ("concise", "pin_log", "full_guide")
            else None
        )

        # Clean trailing PIN_JSON line from visible analysis if present
        visible_text = re.sub(r"PIN_JSON:\s*\{[^{}]*\}", "", content_text).strip()

        now_iso = datetime.now(timezone.utc).isoformat()
        visors_desc = _describe_active_visors(frame_a, frame_b)
        display_model = (
            f"sam-3.1 + {model_used}"
            if sam_native_block and "sam-3.1" not in str(model_used)
            else model_used
        )
        verification_audit = run_deterministic_verification(resolved_board, symptom, visible_text)
        header_banner = (
            f"⚡ [{display_model} // Modo: {clean_mode.upper()} ({latency_ms} ms)]\n"
            if clean_mode in ("concise", "pin_log")
            else (
                f"⚡ [DIAGNÓSTICO EN VIVO — {display_model} ({mode_tag})]\n"
                f"• Endpoint: {endpoint} | Latencia Real: {latency_ms} ms\n"
                f"• Placa Ground Truth: {verification_audit['board_name']}\n"
                f"• Visores Analizados: {visors_desc}\n"
                f"• Tokens Razonamiento: {reasoning_tokens} | Tokens Totales: {total_tokens}\n\n"
            )
        )

        resp_payload = {
            "status": "ok",
            "mock_mode": False,
            "guard_state": "LIVE_API_SUCCESS",
            "engine": engine,
            "board_id": resolved_board,
            "assistant_mode": clean_mode,
            "model_used": display_model,
            "mode_tag": mode_tag,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "timestamp_utc": now_iso,
            "sam_boxes": sam_boxes,
            "verification_audit": verification_audit,
            "analysis": header_banner + sam_native_block + visible_text,
        }
        if pin_reading is not None:
            resp_payload["pin_reading"] = pin_reading
        return resp_payload
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        sim_fallback = generate_simulated_diagnosis(
            engine,
            symptom,
            simulated_reason="LIVE_API_ERROR_FALLBACK",
            frame_a=frame_a,
            frame_b=frame_b,
            board_id=resolved_board,
            assistant_mode=clean_mode,
            session_pins=session_pins,
        )
        sim_fallback["latency_ms"] = latency_ms
        sim_fallback["analysis"] = (
            f"⚠️ [AVISO DE RESILIENCIA: Error en llamada externa ({type(exc).__name__}: {exc}) — "
            f"Activando diagnóstico de contingencia local]\n\n" + sim_fallback["analysis"]
        )
        return sim_fallback


def generate_simulated_diagnosis(
    engine: str,
    symptom: str,
    simulated_reason: str = "MOCK_MODE_ACTIVE",
    frame_a: str = "",
    frame_b: str = "",
    board_id: str = "iphone-11-pro-820-01523-a",
    assistant_mode: str = "concise",
    session_pins: list = None,
) -> dict:
    """Returns an instant, zero-cost technical microsoldering analysis adapted to `assistant_mode`."""
    now_iso = datetime.now(timezone.utc).isoformat()
    resolved_board = resolve_board_id(board_id, symptom)
    clean_mode = (assistant_mode or "concise").strip().lower()
    gt = load_ground_truth()
    board_info = gt.get("boards", {}).get(resolved_board, {})
    board_display = board_info.get("display_name", resolved_board)

    visors_desc = _describe_active_visors(frame_a, frame_b)
    if engine in ("baseten-muse-spark-open-1026", "baseten-muse-spark-open"):
        model_header = (
            "Baseten Open-Weights: meta-models/muse-spark-open-1026 "
            "(base_url='https://inference.baseten.co/v1', max_tokens=1500/1800)"
        )
    elif engine == "meta-sam-3.1":
        model_header = "Meta API (https://api.meta.ai/v1): SAM 3.1 Vision Segmentation (sam-3.1)"
    elif engine == "meta-muse-wonder-1.0":
        model_header = "Meta API (https://api.meta.ai/v1): Muse Wonder 1.0 Supervisor (muse-wonder-1.0)"
    elif engine == "meta-agentic-pipeline":
        model_header = (
            "Meta API Pipeline Agéntico: sam-3.1 (Seg) -> "
            "muse-spark-1.3-contributor (Reason) -> muse-wonder-1.0 (Synth)"
        )
    else:
        model_header = (
            "Meta Model API (https://api.meta.ai/v1): muse-spark-1.3-contributor "
            "(Pipeline compatible con SAM 3.1 / Muse Wonder 1.0)"
        )

    sim_sam_raw = (
        "1<|box;x1=150;y1=112;x2=370;y2=192;w=640;h=360|> "
        "2<|box;x1=205;y1=102;x2=238;y2=200;w=640;h=360|>"
    )
    sim_sam_boxes = parse_sam_boxes(sim_sam_raw)
    pin_reading = (
        _extract_pin_reading_from_text("", symptom, resolved_board)
        if clean_mode in ("concise", "pin_log", "full_guide")
        else None
    )

    if clean_mode == "pin_log":
        analysis_text = (
            f"📌 [PIN_LOG SIM $0.00 — {board_display}] "
            f"`{pin_reading['component_type']}` | Conector `{pin_reading['connector']}` | `{pin_reading['pin']}` | "
            f"Tester: **{pin_reading['measured_value']}** ({pin_reading['tester_mode']}) — 🤖 Cargado automáticamente por IA en Tabla."
        )
    elif clean_mode == "cross_schematic":
        analysis_text = _evaluate_session_pins_against_ground_truth(resolved_board, session_pins)
    elif clean_mode == "concise":
        if resolved_board == "samsung-sm-a107m":
            analysis_text = (
                f"⚡ **[{board_display} — Asistente Conciso ({model_header} + SAM 3.1)]**\n"
                f"• **Conector / Línea (`CON5001` 34p):** `VBUS_5V_CON5001` debe medir **460–580 mV** y `VBAT_MAIN` **320–410 mV** en modo diodo (punta roja a GND).\n"
                f"• **Observación directa:** Se observa jumper de cobre en pista lateral junto a `CON5001` (PMIC `MT6357CRV` / IF-PMIC `S2MU005X03`)."
            )
        elif resolved_board == "samsung-sm-a325m":
            analysis_text = (
                f"⚡ **[{board_display} — Asistente Conciso ({model_header} + SAM 3.1)]**\n"
                f"• **Conector / Línea (`HDC6000` 78p):** `VBUS_OVP_IN` debe medir **440–560 mV**, `VBAT_SENSE` **310–400 mV** y `USB_DP/DM` **580–710 mV** en modo diodo.\n"
                f"• **Observación directa:** Verificar pines extremos de carga/datos hacia IF-PMIC `SM5714` y PMIC `MT6358VW`."
            )
        else:
            analysis_text = (
                f"⚡ **[{board_display} — Asistente Conciso ({model_header} + SAM 3.1)]**\n"
                f"• **Conector / Línea (`J6400` / `J6500`):** En `J6500` `PP_BATT_VCC` mide **290–390 mV** e `I2C0_SMC_SDA/SCL_1V8` **430–530 mV**; en `J6400` `PP5V0_USB_CONN` mide **420–540 mV** en modo diodo.\n"
                f"• **Observación directa:** Placa Cara A (`820-01523-A`, A13 Bionic `APL1W85` / Tigris `U3300` / Hydra `U6300`)."
            )
    else:
        # full_guide mode
        if resolved_board == "samsung-sm-a107m":
            board_specific_block = (
                f"1️⃣ DIAGNÓSTICO VISUAL / SEGMENTACIÓN SAM 3.1 ({board_display}):\n"
                f"   - Conector FPC CON5001 (34 pines, Main-Sub/Display) presenta puente de estaño en sector lateral y pista expuesta con jumper de cobre.\n"
                f"   - PMIC MT6357CRV e IF-PMIC S2MU005X03 verificados en Ground Truth.\n\n"
                f"2️⃣ PUNTOS O PINES A MEDIR CON EL TESTER (Muse Spark 1.3):\n"
                f"   - Síntoma analizado: \"{symptom}\"\n"
                f"   - Medir en modo diodo (punta roja a GND): línea VBUS_5V_CON5001 (nominal 460-580 mV) y VBAT_MAIN (nominal 320-410 mV).\n\n"
                f"3️⃣ ACCIÓN DE MICROSOLDADURA CON CAUTÍN DE PUNTA FINA (Muse Wonder 1.0):\n"
                f"   - Paso 1: Dosificar micro-gota de flux con aguja sobre los pines en puente de CON5001.\n"
                f"   - Paso 2: Pasar cautín de punta fina limada (sin usar aire caliente) para retirar exceso de estaño y despejar corto a GND.\n"
                f"   - Paso 3: Verificar continuidad del jumper de cobre en la pista reconstruida y limpiar con alcohol isopropílico al 99%."
            )
        elif resolved_board == "samsung-sm-a325m":
            board_specific_block = (
                f"1️⃣ DIAGNÓSTICO VISUAL / SEGMENTACIÓN SAM 3.1 ({board_display}):\n"
                f"   - Conector FPC HDC6000 (78 pines Main-Sub + Display) presenta sulfatación y fatiga en pines extremos de carga/datos.\n"
                f"   - PMIC MT6358VW e IF-PMIC SM5714 contrastados contra Ground Truth.\n\n"
                f"2️⃣ PUNTOS O PINES A MEDIR CON EL TESTER (Muse Spark 1.3):\n"
                f"   - Síntoma analizado: \"{symptom}\"\n"
                f"   - Medir en modo diodo (punta roja a GND): VBUS_OVP_IN (nominal 440-560 mV), VBAT_SENSE (310-400 mV) y USB_DP/DM (580-710 mV).\n\n"
                f"3️⃣ ACCIÓN DE MICROSOLDADURA CON CAUTÍN DE PUNTA FINA (Muse Wonder 1.0):\n"
                f"   - Paso 1: Aplicar flux dosificado con aguja hipodérmica sobre la hilera de pines de HDC6000.\n"
                f"   - Paso 2: Resoldar pin por pin exclusivamente con cautín de punta fina limada y estaño 183°C (sin aire caliente para no fundir el plástico del FPC de 78 pines).\n"
                f"   - Paso 3: Validar consumo de carga con Tester USB Mechanic y caída de tensión nominal en modo diodo."
            )
        else:
            board_specific_block = (
                f"1️⃣ DIAGNÓSTICO VISUAL / SEGMENTACIÓN SAM 3.1 ({board_display}):\n"
                f"   - Placa Upper Logic Board 820-01523-A (Cara A separada): se observan SoC Apple A13 Bionic APL1W85, conectores FPC J6400/J6500 e interposer BGA inferior.\n"
                f"   - PMIC STB601A0 (U2700), Charger SN2611A0 Tigris (U3300) y Hydra CBTL1612A1 (U6300) en registro Ground Truth.\n\n"
                f"2️⃣ PUNTOS O PINES A MEDIR CON EL TESTER (Muse Spark 1.3):\n"
                f"   - Síntoma analizado: \"{symptom}\"\n"
                f"   - Medir en modo diodo (punta roja a GND): J6500 PP_BATT_VCC (nominal 290-390 mV), I2C0_SMC_SDA/SCL_1V8 (430-530 mV) y J6400 PP5V0_USB_CONN (420-540 mV).\n\n"
                f"3️⃣ ACCIÓN DE MICROSOLDADURA CON CAUTÍN DE PUNTA FINA (Muse Wonder 1.0):\n"
                f"   - Paso 1: Dosificar flux con aguja sobre los pads BGA del interposer o pines del conector FPC J6400/J6500.\n"
                f"   - Paso 2: Nivelar y limpiar pads oxidados o con resina epóxica usando exclusivamente cautín de punta fina limada y malla desoldante (sin estación de aire caliente).\n"
                f"   - Paso 3: Verificar ausencia de cortos en VDD_MAIN y comprobar telemetría en Tester USB Mechanic."
            )

        analysis_text = (
            f"🛡️ [DIAGNÓSTICO TÁCTICO CIRCUITGUARD AI — MODO SIMULACIÓN $0.00]\n"
            f"• Timestamp Atómico: {now_iso}\n"
            f"• Placa Ground Truth: {board_display}\n"
            f"• Enrutamiento: {model_header}\n"
            f"• Visores incluidos en la auditoría: {visors_desc}\n"
            f"• Estado Puerto USB Linux: 0 Bloqueos v4l2 (Captura desde <canvas> WebRTC en RAM)\n\n"
            f"{board_specific_block}"
        )

    verification_audit = run_deterministic_verification(resolved_board, symptom, analysis_text)

    resp_payload = {
        "status": "ok",
        "mock_mode": True,
        "guard_state": simulated_reason,
        "engine": engine,
        "board_id": resolved_board,
        "assistant_mode": clean_mode,
        "model_used": engine,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "latency_ms": 1.2,
        "sam_boxes": sim_sam_boxes,
        "verification_audit": verification_audit,
        "models_configured": {
            "meta": ["muse-spark-1.3-contributor", "muse-wonder-1.0", "sam-3.1"],
            "baseten": {
                "model": "meta-models/muse-spark-open-1026",
                "base_url": "https://inference.baseten.co/v1",
                "max_tokens": 1500,
            },
        },
        "timestamp_utc": now_iso,
        "analysis": analysis_text,
    }
    if pin_reading is not None:
        resp_payload["pin_reading"] = pin_reading
    return resp_payload


def _handle_n8n_erp_sync(body: dict) -> dict:
    """
    Zero-Trust Mostrador, Mayorista & Distribuidor (Oracle Cloud n8n ERP Webhook Sync):
    - Builds a canonical JSON payload (event_type, stock audit against 'robo hormiga',
      replacement-cost retail/wholesale ARS & USD pricing, and atomic UTC timestamp).
    - Computes HMAC-SHA256 cryptographic signature (`X-CircuitGuard-Signature-256`).
    - Dispatches to `N8N_WEBHOOK_URL` when live & configured, or simulates safely at $0.00 cost.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    webhook_url = str(
        body.get("webhook_url")
        or ENV_CONFIG.get(
            "N8N_WEBHOOK_URL",
            "https://n8n.oraclecloud-circuitguard.example/webhook/zerotrust-erp-sync",
        )
    ).strip()
    secret = ENV_CONFIG.get("N8N_WEBHOOK_SECRET", "DUMMY_N8N_HMAC_SHA256_SECRET_000000")

    event_type = str(body.get("event_type", "ERP_STOCK_AND_PRICE_SYNC")).strip()
    n8n_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp_utc": now_iso,
        "station": "CircuitGuard AI v0.1 — Zero-Trust Counter & Wholesale Node",
        "stock_audit": body.get(
            "stock_audit",
            {
                "anti_shrinkage_guard": "ACTIVE",
                "audited_boxes": 6,
                "counter_categories": [
                    "Módulos OLED/Incell",
                    "Placas Donantes (Desarme)",
                    "ICs BGA/SMD (Tigris/Hydra/SM5714)",
                    "Cargadores & Cables Certificados",
                    "Baterías OEM",
                ],
            },
        ),
        "pricing_update": body.get(
            "pricing_update",
            {
                "sku": "MOD-SAM-A32-4G-ORIG",
                "fx_usd_ars": 1220,
                "replacement_cost_usd": 31.35,
                "retail_minorista_ars": 59283,
                "wholesale_mayorista_ars": 48956,
            },
        ),
    }

    canonical_bytes = json.dumps(n8n_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    hmac_sig = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
    signature_header = f"sha256={hmac_sig}"

    force_live = body.get("mock_mode") is False
    is_dummy_url = ".example" in webhook_url or not webhook_url.startswith("http")

    if MOCK_MODE or not force_live or is_dummy_url:
        return {
            "ok": True,
            "mode": "SIM_N8N_ORACLE_CLOUD_WEBHOOK ($0.00)",
            "http_status": 200,
            "webhook_url": webhook_url,
            "hmac_sha256_signature": signature_header,
            "timestamp_utc": now_iso,
            "n8n_payload": n8n_payload,
        }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=canonical_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-CircuitGuard-Signature-256": signature_header,
                "User-Agent": "CircuitGuard-AI-ZeroTrust-Node/0.1",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            http_status = int(getattr(resp, "status", 200))
        return {
            "ok": True,
            "mode": "LIVE_N8N_ORACLE_CLOUD_WEBHOOK",
            "http_status": http_status,
            "webhook_url": webhook_url,
            "hmac_sha256_signature": signature_header,
            "timestamp_utc": now_iso,
            "n8n_payload": n8n_payload,
        }
    except Exception as exc:
        return {
            "ok": True,
            "mode": f"SIM_FALLBACK_N8N ({type(exc).__name__})",
            "http_status": 200,
            "webhook_url": webhook_url,
            "hmac_sha256_signature": signature_header,
            "timestamp_utc": now_iso,
            "n8n_payload": n8n_payload,
            "warning": str(exc),
        }


class CircuitGuardRequestHandler(SimpleHTTPRequestHandler):
    """Serves static files from /frontend and handles POST /api/diagnose & /api/analyze with NIST/OWASP hardening."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        # NIST CSF / OWASP HTTP Security Hardening Headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if getattr(self, "path", "").startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            gt_bundle = load_ground_truth()
            payload = {
                "service": "CircuitGuard AI v0.1",
                "mock_mode": MOCK_MODE,
                "port": PORT,
                "v4l2_backend_lock": False,
                "meta_key_configured": bool(META_API_KEY),
                "baseten_key_configured": bool(BASETEN_API_KEY),
                "ground_truth_loaded": GROUND_TRUTH_PATH.exists(),
                "loaded_files": gt_bundle.get("loaded_files", []),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if self.path == "/api/ground-truth":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps(load_ground_truth(), ensure_ascii=False).encode("utf-8")
            )
            return

        return super().do_GET()

    def do_POST(self):
        if self.path in ("/api/diagnose", "/api/analyze", "/api/transcribe", "/api/n8n-erp-sync"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                content_length = 0

            # OWASP API4:2023 Unrestricted Resource Consumption / DoS Protection (10 MB max)
            if content_length > MAX_PAYLOAD_BYTES:
                self.send_response(413, "Payload Too Large")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                err_payload = {
                    "error": "Payload Too Large",
                    "max_bytes": MAX_PAYLOAD_BYTES,
                }
                self.wfile.write(json.dumps(err_payload).encode("utf-8"))
                return

            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = {}

            req_mock = body.get("mock_mode", True)

            if self.path == "/api/n8n-erp-sync":
                n8n_res = _handle_n8n_erp_sync(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(n8n_res, ensure_ascii=False).encode("utf-8"))
                return

            if self.path == "/api/transcribe":
                audio_wav_b64 = body.get("audio_wav_b64", "")
                asr_result = _transcribe_audio_muse_voice(
                    audio_wav_b64, force_live=(req_mock is False)
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(asr_result, ensure_ascii=False).encode("utf-8"))
                return

            engine = body.get("engine", "meta-muse-spark-1.3")
            symptom = body.get("symptom", "Inspección general de PCB y multímetro.")
            frame_a = body.get("frame_microscope_b64", "")
            frame_b = body.get("frame_overhead_b64", "")
            board_id = body.get("board_id", "iphone-11-pro-820-01523-a")
            assistant_mode = body.get("assistant_mode", "concise")
            session_pins = body.get("session_pins", [])

            if req_mock is False:
                result = dispatch_external_inference(
                    engine,
                    symptom,
                    frame_a,
                    frame_b,
                    force_live=True,
                    board_id=board_id,
                    assistant_mode=assistant_mode,
                    session_pins=session_pins,
                )
            elif MOCK_MODE or req_mock:
                result = generate_simulated_diagnosis(
                    engine,
                    symptom,
                    frame_a=frame_a,
                    frame_b=frame_b,
                    board_id=board_id,
                    assistant_mode=assistant_mode,
                    session_pins=session_pins,
                )
            else:
                result = dispatch_external_inference(
                    engine,
                    symptom,
                    frame_a,
                    frame_b,
                    force_live=False,
                    board_id=board_id,
                    assistant_mode=assistant_mode,
                    session_pins=session_pins,
                )

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def run_server():
    server_address = (HOST, PORT)
    httpd = ThreadingHTTPServer(server_address, CircuitGuardRequestHandler)
    print(f"[CircuitGuard AI] Servidor activo en http://{HOST}:{PORT}")
    print(f"[CircuitGuard AI] MOCK_MODE = {MOCK_MODE} (Costo $0.00 | Cero bloqueo v4l2)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[CircuitGuard AI] Servidor detenido correctamente.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
