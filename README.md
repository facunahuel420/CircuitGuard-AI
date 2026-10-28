# 🛡️🔬 CircuitGuard AI v0.2
**Multimodal AI Microsoldering Vision Lab, Hands-Free Voice Telemetry & Zero-Trust Distributor ERP**  
*Built for the **Meta Global AI Developer Hackathon** on Ubuntu 26 Linux*

---

## 🌐 English Documentation

### 1. Executive Overview
**CircuitGuard AI** is a high-precision, zero-blocking hardware diagnostics and repair ERP platform designed for smartphone microsoldering laboratories and parts distributors. Built with a security-first architecture (**NIST CSF 2.0 / OWASP API Security**), it eliminates Linux USB video device lockups (`v4l2: Device or resource busy`), orchestrates visual PCB inspections and hands-free voice queries across **Meta Model API** and **Baseten Open-Weights**, prevents technician re-assembly mistakes through mandatory verifiable checklists, and protects inventory margins using Atomic-Time Zero-Trust Physical Box Auditing and Replacement-Cost FX Pricing.

### 2. Core Architecture & Meta AI Stack

#### A. Dual-Camera Non-Blocking Vision Lab (100% Browser WebRTC, Zero `v4l2` Locks)
- **Zero Backend USB Lock**: Python (`backend/server.py`) never locks `/dev/video*`.
- **Hardware-Calibrated UVC Streams**: Supports simultaneous independent streams for **Viewer A (USB Digital Microscope CMOS 4:3 `640x480 @ 30fps`)** and **Viewer B (Overhead Camera — Workbench/Multimeter/Posture)** with in-place asymmetric `70/30` card expansion and selective per-visor AI target routing.
- **Instant `<canvas>` RAM Frame Extraction**: Captures lossless Base64 frames directly from active `<video>` elements in `<20ms` without dropping a single frame.

#### B. Frontier Multi-Model AI Routing (`https://api.meta.ai/v1` & Baseten)
1. **Meta Model API Native Integration**:
   - **`sam-3.1` (Segment Anything Model 3.1 — `POST /v1/responses` SSE)**: Native geometric segmentation of FPC connectors, SMD solder pads, jumper wires, and GND anchors on live PCB captures.
   - **`muse-spark-1.3-contributor` (`POST /v1/chat/completions`)**: Adaptive senior microelectronics engineering assistant for PCB section identification, diode-mode voltage drop analysis, and short-to-ground localization (`MAX_TOKENS=4096`).
   - **`muse-voice-transcribe-1.0` (`POST /v1/asr/transcribe`)**: Hands-free technician voice dictation capturing native browser `24kHz 16-bit Mono PCM RIFF/WAVE` audio with Spanish/English `languageBias` and custom microelectronics `keywords` (`FPC`, `PMIC`, `IF-PMIC`, `VBAT`, `VDD_MAIN`, `jumper`).
   - **`muse-wonder-1.0` (`POST /v1/chat/completions`)**: Executive repair synthesis and verifiable anti-forgetfulness quality assurance supervisor.
2. **Baseten Open-Weights Inference**:
   - **`meta-models/muse-spark-open-1026` (`https://inference.baseten.co/v1/chat/completions`)**: High-throughput multimodal open-weights inference.

#### C. Cybersecurity Hardening (Google Cybersecurity / OWASP Standards)
- **Zero-Key-Leak Memory Isolation**: API keys are loaded strictly from isolated environment memory (`~/.meta_env`, `chmod 600`) with `MOCK_MODE=True` safe offline simulation by default (`$0.00` cost).
- **DOM XSS & BadUSB Mitigation**: All USB hardware descriptors (`videoinput` labels) are sanitized via safe DOM node creation (`createElement` / `textContent`), preventing malicious USB descriptor injection.
- **HTTP & API Security Headers**: Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and a `10 MB` payload ceiling (`HTTP 413`) against DoS attacks.

---

## 🇪🇸 Documentación en Español

### 1. Resumen Ejecutivo
**CircuitGuard AI** es una estación agéntica multimodal para laboratorios de microelectrónica móvil y distribuidores de repuestos desarrollada en Ubuntu 26 Linux. Resuelve de raíz el bloqueo `v4l2` de microscopios USB en Linux, integra 5 modelos del ecosistema **Meta AI** y **Baseten**, incorpora dictado técnico manos libres mientras el operador suelda, estandariza controles de calidad anti-olvido y blinda el mostrador con auditoría Zero-Trust y precios dinámicos por costo de reposición.

### 2. Estructura del Proyecto
```text
CircuitGuard-AI/
├── .env.example                 # Plantilla segura (MOCK_MODE=True, MAX_TOKENS=4096)
├── .gitignore                   # Blindaje contra filtración de secretos y backups
├── README.md                    # Documentación arquitectónica bilingüe (EN/ES)
├── verify_setup.py              # Suite automatizada de 6 pruebas de seguridad y sintaxis
├── backend/
│   └── server.py                # Servidor HTTP (8090): /api/health, /api/diagnose, /api/transcribe
├── frontend/
│   ├── index.html               # Dashboard Cyber-Tactical (Expansión 70/30, Checkboxes de Visor, Voz)
│   └── app.js                   # Driver UVC 640x480@30fps, Grabador WAV 24kHz PCM, ERP Zero-Trust
└── n8n_workflows/
    └── circuitguard_zero_trust_erp.json # Flujo n8n para auditoría Zero-Trust y alertas FX