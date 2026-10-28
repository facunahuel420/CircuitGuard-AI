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
import json
import os
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


def build_text_fallback_messages(
    symptom: str, frame_a: str, frame_b: str, extra_instruction: str = ""
) -> list:
    """Build enriched text-only messages if an endpoint rejects multimodal image_url blocks."""
    visors_desc = _describe_active_visors(frame_a, frame_b)
    text_body = (
        f"Reporte técnico del operador: {symptom}\n"
        f"Visores seleccionados por el operador: {visors_desc} "
        f"(Visor A={len(frame_a or '')} bytes Base64, Visor B={len(frame_b or '')} bytes Base64).\n"
        f"Brindá el diagnóstico estructurado en los 3 puntos solicitados."
    )
    if extra_instruction:
        text_body += f"\n{extra_instruction}"
    return [
        {"role": "system", "content": MUSE_SPARK_SYSTEM_PROMPT},
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
            "Modo Muse Wonder 1.0 Supervisor & Synthesis: priorizá el protocolo ejecutivo de microsoldadura, temperaturas seguras de estación de aire/cautín y síntesis verificable.",
        )
    if engine == "meta-agentic-pipeline":
        return (
            "muse-spark-1.3-contributor",
            "Ejecutá el Pipeline Agéntico Completo en 3 secciones explícitas: "
            "FASE 1 (SAM 3.1 - Segmentación Visual SMD/FPC), "
            "FASE 2 (Muse Spark 1.3 - Razonamiento Electrónico y Puntos a Medir en Modo Diodo), y "
            "FASE 3 (Muse Wonder 1.0 - Acción de Microsoldadura y Checklist Anti-Olvido).",
        )
    return ("muse-spark-1.3-contributor", "")


def build_meta_api_payload(
    symptom: str,
    frame_microscope_b64: str,
    frame_overhead_b64: str,
    multimodal: bool = True,
    target_model: str = "muse-spark-1.3-contributor",
    extra_instruction: str = "",
) -> dict:
    """
    Payload structure for Meta Model API (`https://api.meta.ai/v1/chat/completions`):
    - Supports muse-spark-1.3-contributor, sam-3.1, muse-wonder-1.0, and agentic pipeline
    - max_tokens: 1800
    """
    has_images = bool(
        (frame_microscope_b64 and frame_microscope_b64.startswith("data:image/"))
        or (frame_overhead_b64 and frame_overhead_b64.startswith("data:image/"))
    )
    use_mm = multimodal and has_images
    messages = (
        [
            {"role": "system", "content": MUSE_SPARK_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_multimodal_user_content(
                    symptom, frame_microscope_b64, frame_overhead_b64, extra_instruction
                ),
            },
        ]
        if use_mm
        else build_text_fallback_messages(
            symptom, frame_microscope_b64, frame_overhead_b64, extra_instruction
        )
    )
    return {
        "model": target_model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
        "messages": messages,
    }


def build_baseten_payload(
    symptom: str, frame_microscope_b64: str, frame_overhead_b64: str, multimodal: bool = True
) -> dict:
    """
    Payload structure for Baseten Open-Weights Inference (`https://inference.baseten.co/v1/chat/completions`):
    - Model: meta-models/muse-spark-open-1026
    - max_tokens: 1800
    """
    has_images = bool(
        (frame_microscope_b64 and frame_microscope_b64.startswith("data:image/"))
        or (frame_overhead_b64 and frame_overhead_b64.startswith("data:image/"))
    )
    use_mm = multimodal and has_images
    messages = (
        [
            {"role": "system", "content": MUSE_SPARK_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_multimodal_user_content(
                    symptom, frame_microscope_b64, frame_overhead_b64
                ),
            },
        ]
        if use_mm
        else build_text_fallback_messages(symptom, frame_microscope_b64, frame_overhead_b64)
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

    # Determine concise English segmentation prompt(s) for SAM 3.1
    if 0 < len(clean_symptom) < 35 and "?" not in clean_symptom and "¿" not in clean_symptom:
        concepts = [clean_symptom]
    else:
        concepts = ["FPC connector", "solder pad"]

    collected_outputs = []
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
        collected_outputs.append(f"• Target '{concept}': {concept_out or '[Máscara procesada sin detecciones]'}")

    return {
        "endpoint": endpoint,
        "concepts": concepts,
        "sam_output": "\n".join(collected_outputs),
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
    engine: str, symptom: str, frame_a: str, frame_b: str, force_live: bool = False
) -> dict:
    """
    Real HTTPS client for:
    - Meta SAM 3.1 Native Responses API (`POST https://api.meta.ai/v1/responses` SSE)
    - Meta Chat Completions API (`POST https://api.meta.ai/v1/chat/completions`)
    - Baseten Open-Weights (`POST https://inference.baseten.co/v1/chat/completions`)
    """
    is_baseten = engine in ("baseten-muse-spark-open-1026", "baseten-muse-spark-open")
    if is_baseten:
        base_url = ENV_CONFIG.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = BASETEN_API_KEY
        default_model = "meta-models/muse-spark-open-1026"
        mm_payload = build_baseten_payload(symptom, frame_a, frame_b, multimodal=True)
        txt_payload = build_baseten_payload(symptom, frame_a, frame_b, multimodal=False)
        fallback_model_payload = None
    else:
        base_url = ENV_CONFIG.get("META_API_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = META_API_KEY
        target_model, extra_instr = resolve_meta_model_and_instruction(engine)
        default_model = target_model
        mm_payload = build_meta_api_payload(
            symptom, frame_a, frame_b, multimodal=True, target_model=target_model, extra_instruction=extra_instr
        )
        txt_payload = build_meta_api_payload(
            symptom, frame_a, frame_b, multimodal=False, target_model=target_model, extra_instruction=extra_instr
        )
        fallback_model_payload = (
            build_meta_api_payload(
                symptom,
                frame_a,
                frame_b,
                multimodal=True,
                target_model="muse-spark-1.3-contributor",
                extra_instruction=extra_instr,
            )
            if target_model != "muse-spark-1.3-contributor"
            else None
        )

    # Safety guard: if key is empty/dummy or neither force_live nor live mode is active
    if not api_key or "DUMMY_" in api_key or (MOCK_MODE and not force_live):
        return generate_simulated_diagnosis(
            engine, symptom, simulated_reason="SAFE_MOCK_GUARD", frame_a=frame_a, frame_b=frame_b
        )

    t0 = time.perf_counter()
    mode_tag = "MULTIMODAL_VISION"
    active_image = (
        frame_a
        if (frame_a and frame_a.startswith("data:image/"))
        else (frame_b if (frame_b and frame_b.startswith("data:image/")) else "")
    )

    try:
        sam_native_block = ""
        # Native SAM 3.1 execution via POST /v1/responses (SSE) when meta-sam-3.1 or meta-agentic-pipeline is selected
        if engine in ("meta-sam-3.1", "meta-agentic-pipeline") and active_image:
            try:
                sam_res = _call_sam_3_1_native(base_url, api_key, symptom, active_image)
                sam_native_block = (
                    f"🎯 [SEGMENTACIÓN GEOMÉTRICA NATIVA SAM 3.1 — POST /v1/responses SSE]\n"
                    f"{sam_res['sam_output']}\n\n"
                )
                mode_tag = "SAM_3.1_RESPONSES_SSE + MUSE_SPARK_1.3"
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

        now_iso = datetime.now(timezone.utc).isoformat()
        visors_desc = _describe_active_visors(frame_a, frame_b)
        display_model = (
            f"sam-3.1 + {model_used}"
            if sam_native_block and "sam-3.1" not in str(model_used)
            else model_used
        )
        header_banner = (
            f"⚡ [DIAGNÓSTICO EN VIVO — {display_model} ({mode_tag})]\n"
            f"• Endpoint: {endpoint} | Latencia Real: {latency_ms} ms\n"
            f"• Visores Analizados: {visors_desc}\n"
            f"• Tokens Razonamiento: {reasoning_tokens} | Tokens Totales: {total_tokens}\n\n"
        )

        return {
            "status": "ok",
            "mock_mode": False,
            "guard_state": "LIVE_API_SUCCESS",
            "engine": engine,
            "model_used": display_model,
            "mode_tag": mode_tag,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "timestamp_utc": now_iso,
            "analysis": header_banner + sam_native_block + content_text,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        sim_fallback = generate_simulated_diagnosis(
            engine,
            symptom,
            simulated_reason="LIVE_API_ERROR_FALLBACK",
            frame_a=frame_a,
            frame_b=frame_b,
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
) -> dict:
    """Returns an instant, zero-cost technical microsoldering analysis."""
    now_iso = datetime.now(timezone.utc).isoformat()
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

    analysis_text = (
        f"🛡️ [DIAGNÓSTICO TÁCTICO CIRCUITGUARD AI — MODO SIMULACIÓN $0.00]\n"
        f"• Timestamp Atómico: {now_iso}\n"
        f"• Enrutamiento: {model_header}\n"
        f"• Visores incluidos en la auditoría: {visors_desc}\n"
        f"• Estado Puerto USB Linux: 0 Bloqueos v4l2 (Captura desde <canvas> WebRTC en RAM)\n\n"
        f"1️⃣ DIAGNÓSTICO VISUAL / COMPONENTE BAJO SOSPECHA (SAM 3.1):\n"
        f"   - Se identifica sulfatación y micro-fisura térmica en el Pin #6 (VDD_LCD_3P0) del conector FPC J6001.\n"
        f"   - Condensador de desacoplo C6014 (0201) presenta cambio de coloración por estrés térmico.\n\n"
        f"2️⃣ PUNTOS O PINES A MEDIR CON EL TESTER (Muse Spark 1.3):\n"
        f"   - Síntoma analizado: \"{symptom}\"\n"
        f"   - Medir en modo diodo (punta roja a GND): Pin #6 del FPC J6001 registra 0.002V (corto franco a tierra; valor nominal esperado ~0.420V).\n\n"
        f"3️⃣ ACCIÓN DE MICROSOLDADURA RECOMENDADA (Muse Wonder 1.0):\n"
        f"   - Paso 1: Desconectar batería y aplicar humo de colofonia (Rosin) sobre línea VDD_LCD_3P0 e IF-PMIC.\n"
        f"   - Paso 2: Inyectar 3.0V limitado a 1.2A con fuente regulada; retirar C6014 en corto con cautín a 350°C.\n"
        f"   - Paso 3: Limpiar sulfato en Pin #6 del FPC con alcohol isopropílico al 99% y reconstruir pad con estaño 183°C.\n"
        f"   - Paso 4: Validar caída de tensión nominal (~0.420V en modo diodo) y completar el Checklist Anti-Olvido antes de cerrar."
    )

    return {
        "status": "ok",
        "mock_mode": True,
        "guard_state": simulated_reason,
        "engine": engine,
        "model_used": engine,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "latency_ms": 1.2,
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


class CircuitGuardRequestHandler(SimpleHTTPRequestHandler):
    """Serves static files from /frontend and handles POST /api/diagnose with NIST/OWASP hardening."""

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
            payload = {
                "service": "CircuitGuard AI v0.1",
                "mock_mode": MOCK_MODE,
                "port": PORT,
                "v4l2_backend_lock": False,
                "meta_key_configured": bool(META_API_KEY),
                "baseten_key_configured": bool(BASETEN_API_KEY),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        return super().do_GET()

    def do_POST(self):
        if self.path in ("/api/diagnose", "/api/transcribe"):
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

            if req_mock is False:
                result = dispatch_external_inference(
                    engine, symptom, frame_a, frame_b, force_live=True
                )
            elif MOCK_MODE or req_mock:
                result = generate_simulated_diagnosis(
                    engine, symptom, frame_a=frame_a, frame_b=frame_b
                )
            else:
                result = dispatch_external_inference(
                    engine, symptom, frame_a, frame_b, force_live=False
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
