# 🛡️🔬 CircuitGuard AI v0.6 — Multimodal AI Microelectronics Diagnostics, Verifiable Ground-Truth Agent & Zero-Trust ERP
**Dual-Camera Non-Blocking Computer Vision, SAM 3.1 Geometric Overlay, Verifiable Hardware Ground Truth & Zero-Trust ERP**  
*Built for the **Meta Global AI Developer Hackathon** on Ubuntu Linux*

[![Ubuntu 26](https://img.shields.io/badge/Ubuntu-26_Linux-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/)
[![Meta Model API](https://img.shields.io/badge/Meta_AI-api.meta.ai-0081FB?logo=meta&logoColor=white)](https://api.meta.ai/)
[![SAM 3.1](https://img.shields.io/badge/Vision_Segmentation-SAM_3.1-00d4ff)](https://api.meta.ai/)
[![Muse Voice](https://img.shields.io/badge/ASR-Muse_Voice_Transcribe-00ff88)](https://api.meta.ai/)
[![Baseten](https://img.shields.io/badge/Inference-Baseten_Open--Weights-FF5500)](https://baseten.co/)
[![Oracle Cloud n8n](https://img.shields.io/badge/Automation-n8n_Oracle_Cloud-F80000?logo=oracle&logoColor=white)](https://cloud.oracle.com/)
[![Deterministic Verification](https://img.shields.io/badge/Meta_Agents_102-Deterministic_Auditor-7C3AED)](https://github.com/)

---

## 🌐 English Technical Documentation (Primary)

### 1. Executive Summary
**CircuitGuard AI v0.6** is a mission-critical, cyber-tactical multimodal AI workstation engineered specifically for smartphone microelectronics laboratories, advanced microsoldering technicians, and replacement parts distributors. 

Operating in workbench conditions where micro-soldering technicians have both hands occupied with fine-tip irons, tweezers, and multimeter probes, CircuitGuard AI delivers:
1. **Zero Linux v4l2 USB video device locks** via browser-native WebRTC streaming and memory canvas buffer extraction.
2. **Hands-free acoustic control and 24 kHz WAV dictation** powered by Meta's `muse-voice-transcribe-1.0`.
3. **Deterministic verification and Ground-Truth schematic auto-ingestion (Meta Agents 102 Workshop)** against official logic board schematics (`.json` and `.md`), enforcing strict tool profiles (fine-tip limed soldering iron + needle flux; absolute prohibition of hot-air guns over delicate plastic FPC connectors).
4. **SAM 3.1 morphological segmentation (`/v1/responses` SSE)** with real-time `<canvas>` bounding boxes and a 100% AI-populated pin/component session logger with Markdown (`.md`) export.
5. **Commercial donor-board scrap recovery analytics & Zero-Trust ERP** featuring retail vs wholesale pricing and cryptographically signed **HMAC-SHA256** synchronization to **n8n on Oracle Cloud**.

---

### 2. Core Architectural Pillars

#### 🔬 Section 1: Dual-Camera Non-Blocking WebRTC & Hands-Free Lab
- **The Linux v4l2 Concurrency Problem**: On Ubuntu Linux, attempting to capture video frames from Python OpenCV (`/dev/video*`) while the technician observes a real-time feed crashes the Video4Linux2 kernel driver with `VIDIOC_S_FMT: Device or resource busy`.
- **Architectural Solution**: Python (`backend/server.py`) **never touches `/dev/video*`**. Both video pipelines run entirely inside the client browser via WebRTC `navigator.mediaDevices.getUserMedia()`:
  - **Viewer A**: USB Physical Microscope (UVC `640x480 @ 30 FPS`, 4:3 CMOS sensor) inspecting SMD chips, FPC pins, and copper traces. Supports asymmetric 70/30 in-place grid expansion without covering the UI.
  - **Viewer B**: Overhead Workbench / Multimeter Camera (e.g., Samsung Galaxy A32 / UVC loopback on `/dev/video10` @ 30/60 FPS) capturing technician hand posture, probe placement, and digital multimeter readings.
- **Instant Offscreen Memory Extraction**: When a diagnosis is triggered, an offscreen `<canvas>` captures the current frame from active `<video>` buffers in RAM (<4 ms) without dropping a single frame of the live video stream.
- **Hands-Free Operation**:
  - **Acoustic Countdown Timer**: Web Audio API synthesized sine beeps (740 Hz ticks, 980 Hz warning, 1320 Hz dual capture tone) for 10-second and 20-second hands-free probe stabilization.
  - **Muse Voice Transcribe 1.0**: Captures raw audio, converts in-browser to standard 44-byte RIFF/WAVE mono 16-bit PCM at 24,000 Hz, and streams to `POST /v1/asr/transcribe` with specialized electronics vocabulary biases (`FPC`, `PMIC`, `IF-PMIC`, `VBAT`, `VDD_MAIN`, `jumper`, `modo diodo`).

---

#### 🧠 Section 2: Meta Workshop Agents 101 & 102 — Verifiable Ground Truth & Deterministic Audit
- **Dynamic Ground Truth Ingestion (`ground_truth/`)**: On every diagnosis request, `backend/server.py` auto-scans all `.json` specifications and `.md` schematic files located in `ground_truth/`, injecting authoritative electrical tolerances directly into the LLM system prompt:
  - **Apple iPhone 11 Pro** (`820-01523-A`, SoC A13 Bionic `APL1W85`): Cara A Upper Logic Board, Charger Tigris `SN2611A0 U3300`, USB Hydra `CBTL1612A1 U6300`, PMIC `STB601A0 U2700`. Conector `J6500` (`PP_BATT_VCC` 290–390 mV, `I2C0_SMC` 430–530 mV) and `J6400` (`PP5V0_USB_CONN` 420–540 mV).
  - **Samsung Galaxy A32** (`SM-A325M`): IF-PMIC `SM5714`, PMIC `MT6358VW`, Main-Sub/Display FPC `HDC6000` 78 pins (`VBUS_OVP_IN` 440–560 mV, `VBAT_SENSE` 310–400 mV, `USB_DP/DM` 580–710 mV).
  - **Samsung Galaxy A10s** (`SM-A107M`): PMIC `MT6357CRV`, IF-PMIC `S2MU005X03`, FPC `CON5001` 34 pins (`VBUS_5V_CON5001` 460–580 mV, `VBAT_MAIN` 320–410 mV).
- **Deterministic Tool Constraint Auditor**:
  - Automatically contrasts generated recommendations against `technician_tool_profile`.
  - **Strict Constraint**: Interventions must be performed **exclusively with fine-tip limed soldering iron, hypodermic needle-dispensed flux, and 183°C solder**.
  - Flagging engine blocks any suggestion of hot-air rework stations (`aire caliente` / `tobera`) near meltable plastic FPC connectors, ensuring compliance with the physical tooling capabilities of the technician.

---

#### 🎯 Section 3: SAM 3.1 Geometric Overlay & Universal AI Pin Logger
- **Native SAM 3.1 Streaming (`POST /v1/responses` SSE)**:
  - Directly interfaces with Meta Responses API using Server-Sent Events (`Accept: text/event-stream`).
  - Employs Meta's official regex parser:
    ```python
    re.compile(r"(\d+)<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>")
    ```
  - Coordinates are mapped onto `<canvas id="previewCanvasA">` with color-coded tactical bounding boxes and ID badges, inspectable via full-screen snapshot lightbox.
- **100% AI Pin-by-Pin Logger (Zero Manual Typing)**:
  - Eliminates manual technician text inputs.
  - Across all capture modes (`concise`, `pin_log`, `full_guide`), the AI multimodal reasoning model auto-extracts detected component type (`FPC`, `Capacitor SMD`, `Bobina / Inductor`, `Diodo SMD / TVS`, `IC / Línea Alimentación`), connector identifier, pin number, multimeter function (`Diodo (mV)`, `Voltaje (V)`, `Continuidad (Ω)`, `Corriente USB (A)`), and measured value.
  - Auto-populates the interactive session table with green visual highlight confirmation (`🤖 Cargado automáticamente por IA`).
  - Each row features an independent `🗑️ Borrar` button.
  - One-click cross-check against Ground Truth schematics (`cross_schematic` intent router) and downloadable Markdown export (`.md`).

---

#### 📦 Section 4: Retail, Donor-Board Compatibility & Zero-Trust n8n ERP
- **Donor Board Scrap Recovery vs New Parts**:
  - Interactive database identifying cross-compatible ICs across motherboards (e.g., `SM5714` shared between A32, A52, and A72; `MT6357CRV` shared across MediaTek A10s/A02/A12; `Tigris U3300` / `Hydra U6300` shared across iPhone 11 family).
  - Evaluates scrap board salvage profitability ($0 cost donor harvest vs purchasing new blister components).
- **Express Counter Quoter with Client Tiers**:
  - Dynamically calculates **Retail Counter Price (Minorista)** vs **Wholesale / Trade Price (Gremio / Taller Colega)**.
  - Combines replacement part costs (USD), labor/risk tier, and real-time FX rate (ARS/USD).
  - Locks repair closure behind a mandatory **Anti-Forgetfulness Checklist** (validating proximity sensor acoustic rubber, Motorola NFC/thermistor intermediate cover continuity, and Samsung OVP sub-boards).
- **Zero-Trust Physical Box Ledger & Oracle Cloud n8n Webhook Sync**:
  - Audits physical counter boxes (LCD assemblies, donor scrap boards, BGA ICs, 25W PD chargers, OEM batteries) against counter shrinkage ("robo hormiga") using atomic UTC timestamps and SHA-256 state hashes.
  - **Dynamic Replacement-Cost FX Calculator**: Protects purchasing power against inflation by dynamically recalculating selling prices based on current supplier replacement costs rather than depreciated historical purchase prices.
  - **HMAC-SHA256 Webhook Sync (`POST /api/n8n-erp-sync`)**:
    - Dispatches canonical stock and price audit payloads to **n8n on Oracle Cloud**.
    - Cryptographically signs payloads using standard library `hmac` + `hashlib` under the header:
      ```http
      X-CircuitGuard-Signature-256: sha256=<hex_digest>
      ```
    - Fully functional in offline simulation mode ($0.00 cost) and live enterprise deployment.

---

### 3. Five Supported Multi-Model Engines
The technician can switch between 5 inference engines via the tactile dropdown:
1. `meta-muse-spark-1.3`: **Meta Muse Spark 1.3 Contributor** (`muse-spark-1.3-contributor`, default reasoning model at `https://api.meta.ai/v1`, 4096 tokens).
2. `meta-sam-3.1`: **Meta SAM 3.1 Vision Segmentation** (`sam-3.1` via native `POST /v1/responses` SSE stream).
3. `meta-muse-wonder-1.0`: **Meta Muse Wonder 1.0 Supervisor** (`muse-wonder-1.0` executive repair protocol synthesizer).
4. `meta-agentic-pipeline`: **Meta Full Agentic Pipeline** (`sam-3.1` morphological segmentation &rarr; `muse-spark-1.3` electronic reasoning &rarr; `muse-wonder-1.0` synthesis).
5. `baseten-muse-spark-open`: **Baseten Open-Weights Dedicated Inference** (`meta-models/muse-spark-open-1026` hosted on `https://inference.baseten.co/v1`).

---

### 4. Repository Structure
```text
Circuit_Guardian_ia_v0.1/
├── .env.example                               # Safe configuration template (dummy keys, MOCK_MODE=True)
├── .gitignore                                 # Strict protection: .env, cache, *.bak*, and internal reports
├── README.md                                  # Complete bilingual technical documentation (v0.6)
├── verify_setup.py                            # Automated 6/6 architecture, AST syntax & Zero-Leak test suite
├── backend/
│   └── server.py                              # Hardened HTTP server (port 8090): /api/diagnose, /api/transcribe, /api/n8n-erp-sync
├── frontend/
│   ├── index.html                             # Cyber-Tactical Dashboard (4 operational tabs, 70/30 camera expansion, lightbox zoom)
│   └── app.js                                 # Non-blocking WebRTC driver, SAM 3.1 canvas overlay, AI table, n8n client
├── ground_truth/
│   ├── boards_ground_truth_bundle.json        # Verifiable Ground Truth specs for iPhone 11 Pro, Samsung A32, Samsung A10s
│   ├── esquematico_iphone_11_pro_820_01523_a.md # Dynamic Markdown schematic for iPhone 11 Pro (J6400, J6500)
│   └── esquematico_samsung_a32_sm_a325m.md    # Dynamic Markdown schematic for Samsung A32 (HDC6000 78p, SM5714)
└── n8n_workflows/
    └── circuitguard_zero_trust_erp.json       # n8n automated workflow definition for Oracle Cloud
```

---

### 5. Quickstart & Verification

```bash
# 1. Verify project integrity, Python AST, JS syntax, and mock mode simulation
PYTHONDONTWRITEBYTECODE=1 python3 verify_setup.py

# 2. Launch the CircuitGuard AI local tactical server
python3 backend/server.py

# 3. Access the dashboard from Ubuntu Linux:
# Open http://127.0.0.1:8090 in Chromium or Google Chrome
```

---

## 🇪🇸 Resumen Ejecutivo y Documentación Técnica (Español)

### 1. Visión General
**CircuitGuard AI v0.6** es una estación de trabajo táctica e inteligente para microelectrónica de smartphones y control de inventario mayorista/minorista, diseñada específicamente para el **Meta Global AI Developer Hackathon**. 

Resuelve de raíz los desafíos del banco de trabajo del técnico:
- **Cero Bloqueos USB en Linux**: Elimina el fallo del driver del kernel `v4l2` (`Device or resource busy`) delegando el streaming dual en vivo al navegador WebRTC. El backend Python jamás abre `/dev/video*`.
- **Manos Libres Acústico & Voz**: Permite al técnico estabilizar puntas del multímetro y cautín mediante temporizadores sonoros (Web Audio API) y dictado por voz 24 kHz WAV procesado por `muse-voice-transcribe-1.0`.
- **Agente Verificable Ground Truth (Meta Agentes 102)**: Auto-escaneo en caliente de esquemáticos en `ground_truth/` (`.json` y `.md`) para iPhone 11 Pro, Samsung A32 y Samsung A10s, con auditoría determinista de herramientas (solo cautín de punta fina limada y flux con aguja; prohibición de aire caliente sobre FPC).
- **Segmentación SAM 3.1 & Tabla 100% IA**: Detección geométrica en tiempo real sobre `<canvas>` y extracción automática de lecturas del tester (diodo mV, voltios, amperios, continuidad) a la tabla de sesión con exportación a Markdown (`.md`).
- **Control Comercial & Sincronización ERP n8n**: Cotizador para Cliente Mostrador (Minorista) y Gremio (Mayorista), checklist anti-olvido pre-sellado, matriz anti-robo hormiga de cajas físicas y webhook con firma criptográfica `HMAC-SHA256` hacia n8n en Oracle Cloud.

---

### 2. Estándares de Ciberseguridad y Confiabilidad Operativa
- **Política Zero-Key-Leak**: Ninguna clave real o variable de entorno se almacena en el repositorio. `MOCK_MODE = True` por defecto garantiza costo `$0.00` en pruebas.
- **Protección DoS / OWASP API4:2023**: Límite de carga útil estricto de 10 MB por request (`413 Payload Too Large`).
- **Cabeceras de Hardening HTTP (NIST CSF)**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store` para todos los endpoints `/api/*`.
- **Resiliencia Automática**: Ante desconexión o fallo en endpoints remotos, el enrutador conmuta transparentemente a contingencia local estructurada sin detener la operación del taller.
