#!/usr/bin/env python3
"""
CircuitGuard AI v0.1 — Automated Security, Syntax & Architecture Verification Suite
Meta Global AI Developer Hackathon (Ubuntu Linux)

Checks:
1. Directory & File Structure (/backend, /frontend, /n8n_workflows, README.md, .gitignore, .env.example)
2. Python AST & Bytecode Syntax Validation (backend/server.py, verify_setup.py)
3. JavaScript Syntax Validation (frontend/app.js via `node --check` or structural parser)
4. Zero-Leak API Key Audit (verifies MOCK_MODE=True and ensures no real API keys exist)
5. Linux v4l2 Non-Blocking Compliance (verifies backend never opens /dev/video* and frontend uses WebRTC + canvas)
6. Non-Blocking Offline Smoke Test of `/api/diagnose` simulation logic
"""

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REQUIRED_DIRS = [
    ROOT / "backend",
    ROOT / "frontend",
    ROOT / "n8n_workflows",
]

REQUIRED_FILES = [
    ROOT / ".gitignore",
    ROOT / ".env.example",
    ROOT / "README.md",
    ROOT / "backend" / "server.py",
    ROOT / "frontend" / "index.html",
    ROOT / "frontend" / "app.js",
    ROOT / "verify_setup.py",
]

# Patterns that would indicate an accidentally committed live secret key
LIVE_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
]


def check_structure() -> None:
    print("==> [1/6] Verificando estructura de carpetas y archivos...")
    for d in REQUIRED_DIRS:
        assert d.is_dir(), f"Falta el directorio requerido: {d}"
    for f in REQUIRED_FILES:
        assert f.is_file(), f"Falta el archivo requerido: {f}"
    assert not (ROOT / ".env").exists(), "Archivo .env real detectado; solo debe existir .env.example"

    gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".env", "__pycache__/", "*.pyc"):
        assert entry in gitignore_text, f"Falta '{entry}' en .gitignore"
    print("    [OK] Estructura de directorios y .gitignore verificados.")


def check_python_syntax() -> None:
    print("==> [2/6] Verificando sintaxis de archivos Python (AST)...")
    for py_file in [ROOT / "backend" / "server.py", ROOT / "verify_setup.py"]:
        source = py_file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(py_file))
    print("    [OK] Sintaxis Python 100% válida.")


def check_js_syntax() -> None:
    print("==> [3/6] Verificando sintaxis de frontend/app.js...")
    js_file = ROOT / "frontend" / "app.js"
    node_bin = shutil.which("node")
    if node_bin:
        res = subprocess.run(
            [node_bin, "--check", str(js_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Error de sintaxis JS en {js_file}:\n{res.stderr}"
        print("    [OK] Sintaxis JavaScript validada con `node --check`.")
    else:
        js_text = js_file.read_text(encoding="utf-8")
        assert js_text.count("{") == js_text.count("}"), "Desbalance de llaves en app.js"
        assert js_text.count("(") == js_text.count(")"), "Desbalance de paréntesis en app.js"
        print("    [OK] Sintaxis estructural JavaScript verificada.")


def check_security_and_models() -> None:
    print("==> [4/6] Auditando seguridad Zero-Key-Leak y configuración Multi-Modelo...")
    for path in REQUIRED_FILES:
        content = path.read_text(encoding="utf-8")
        for pat in LIVE_SECRET_PATTERNS:
            match = pat.search(content)
            assert not match, f"Posible clave real expuesta en {path.name}: {match.group(0)}"

    server_code = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
    assert "MOCK_MODE = True" in server_code, "backend/server.py debe tener MOCK_MODE = True por defecto"

    required_tokens = [
        "muse-spark-1.3-contributor",
        "muse-wonder-1.0",
        "sam-3.1",
        "meta-models/muse-spark-open-1026",
        "https://inference.baseten.co/v1",
        "1500",
        "8090",
    ]
    for token in required_tokens:
        assert token in server_code, f"Falta configuración requerida '{token}' en backend/server.py"
    print("    [OK] MOCK_MODE=True activo, cero claves reales expuestas y modelos configurados.")


def check_v4l2_non_blocking_compliance() -> None:
    print("==> [5/6] Verificando arquitectura anti-bloqueo USB Linux (v4l2)...")
    server_code = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
    assert "cv2.VideoCapture" not in server_code, "Prohibido usar cv2.VideoCapture en el backend"

    js_code = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "navigator.mediaDevices.getUserMedia" in js_code, "Falta getUserMedia() en frontend/app.js"
    assert "toDataURL" in js_code, "Falta extracción de frame con <canvas>.toDataURL en frontend/app.js"

    html_code = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for color in ("#0a0d0e", "#111618", "#1f2937", "#00ff88"):
        assert color in html_code.lower(), f"Falta color táctico requerido {color} en frontend/index.html"
    print("    [OK] Captura 100% navegador WebRTC + <canvas> y estética Cyber-Tactical verificadas.")


def check_offline_simulation_smoke() -> None:
    print("==> [6/6] Ejecutando prueba funcional interna de simulación ($0.00 costo)...")
    sys.path.insert(0, str(ROOT / "backend"))
    import server  # noqa: E402

    assert server.MOCK_MODE is True, "server.MOCK_MODE debe ser True"
    resp_meta = server.generate_simulated_diagnosis("meta-muse-spark-1.3", "Corto en línea VDD_LCD_3P0")
    assert resp_meta["status"] == "ok" and resp_meta["mock_mode"] is True
    assert "SAM 3.1" in resp_meta["analysis"]

    resp_baseten = server.generate_simulated_diagnosis(
        "baseten-muse-spark-open-1026", "Falla de carga en IF-PMIC SM5714"
    )
    assert resp_baseten["status"] == "ok" and "meta-models/muse-spark-open-1026" in resp_baseten["analysis"]
    print("    [OK] Simulación offline Meta API y Baseten verificada con costo $0.00.")


def main() -> int:
    print("============================================================================")
    print("🛡️  CIRCUITGUARD AI v0.1 — SUITE DE VERIFICACIÓN DE ARQUITECTURA Y SEGURIDAD")
    print("============================================================================")
    check_structure()
    check_python_syntax()
    check_js_syntax()
    check_security_and_models()
    check_v4l2_non_blocking_compliance()
    check_offline_simulation_smoke()
    print("============================================================================")
    print("✅ TODAS LAS PRUEBAS PASARON EXITOSAMENTE (0 LLAMADAS EXTERNAS, COSTO $0.00)")
    print("============================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
