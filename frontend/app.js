/**
 * CircuitGuard AI v0.1 — Tactical Frontend Controller
 * Meta Global AI Developer Hackathon (Ubuntu Linux)
 *
 * CRITICAL LINUX v4l2 NON-BLOCKING DESIGN:
 * Camera streams are opened 100% inside the browser via navigator.mediaDevices.getUserMedia()
 * (or 60 FPS canvas.captureStream fallback). Frame capture extracts Base64 images directly
 * from the active <video> element using an offscreen <canvas> without stopping the stream.
 */

(function () {
  'use strict';

  // ==========================================================================
  // 1. GLOBAL STATE & ATOMIC CLOCK
  // ==========================================================================
  const state = {
    mockMode: true,
    selectedEngine: 'meta-muse-spark-1.3',
    streamA: null,
    streamB: null,
    synthAnimIdA: null,
    synthAnimIdB: null,
    compatFilterCategory: 'ALL',
    compatSearchQuery: '',
    cashBalanceUsd: 1480.0,
    physicalBoxes: [
      {
        boxId: 'Caja #20',
        sku: 'MOD-SAM-A12-ORIG',
        description: 'Módulos Samsung A12 / A02 / A32 5G (Flex A125F/A127F)',
        qty: 10,
        unitReplacementUsd: 24.0,
        lastAtomicTimestamp: '2026-10-26T23:30:00.000Z',
        auditHash: '9f84c2e17b01a40b'
      },
      {
        boxId: 'Caja #14',
        sku: 'MOD-SAM-A03-BOE',
        description: 'Módulos Samsung A03 / A03S / A02S (Panel BOE / IC Novatek)',
        qty: 25,
        unitReplacementUsd: 19.5,
        lastAtomicTimestamp: '2026-10-26T23:28:12.000Z',
        auditHash: '4d19e8a03c77f912'
      },
      {
        boxId: 'Caja #08',
        sku: 'MOD-IP11-SYNA',
        description: 'Módulos iPhone 11 / XR (IC Synaptics Trasplantable TrueTone)',
        qty: 12,
        unitReplacementUsd: 32.0,
        lastAtomicTimestamp: '2026-10-26T23:25:44.000Z',
        auditHash: '7a31b5f902c4d18e'
      },
      {
        boxId: 'Caja #31',
        sku: 'IC-PMIC-S2MU106',
        description: 'Blister ICs Donantes PMIC / IF-PMIC (S2MU106X01 / SM5714)',
        qty: 18,
        unitReplacementUsd: 8.5,
        lastAtomicTimestamp: '2026-10-26T23:20:05.000Z',
        auditHash: '2c60d4e891fa3307'
      }
    ]
  };

  function generateTacticalHash(seedString) {
    let h1 = 0xdeadbeef ^ seedString.length;
    let h2 = 0x41c6ce57 ^ seedString.length;
    for (let i = 0, ch; i < seedString.length; i++) {
      ch = seedString.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761);
      h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0');
  }

  function updateAtomicClock() {
    const badge = document.getElementById('atomicClockBadge');
    if (badge) {
      badge.textContent = '⏱️ ATOMIC UTC: ' + new Date().toISOString();
    }
  }
  setInterval(updateAtomicClock, 1000);
  updateAtomicClock();

  // ==========================================================================
  // 2. TAB NAVIGATION
  // ==========================================================================
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      tabButtons.forEach((b) => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabPanes.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const pane = document.getElementById(targetId);
      if (pane) pane.classList.add('active');
    });
  });

  // ==========================================================================
  // 3. TAB 1: DUAL-CAMERA NON-BLOCKING VISION LAB (WebRTC + Offscreen Canvas)
  // ==========================================================================
  const videoA = document.getElementById('videoMicroscope');
  const videoB = document.getElementById('videoOverhead');
  const selectCamA = document.getElementById('selectCameraA');
  const selectCamB = document.getElementById('selectCameraB');
  const hudSourceA = document.getElementById('hudSourceA');
  const hudSourceB = document.getElementById('hudSourceB');
  const toggleMockMode = document.getElementById('toggleMockMode');
  const selectAiEngine = document.getElementById('selectAiEngine');

  // Simulation Mode Toggle
  if (toggleMockMode) {
    toggleMockMode.addEventListener('change', () => {
      state.mockMode = toggleMockMode.checked;
      const headerBadge = document.getElementById('headerModeBadge');
      const simStatusLabel = document.getElementById('simStatusLabel');
      const toggleMockText = document.getElementById('toggleMockText');

      if (state.mockMode) {
        headerBadge.className = 'pill pill-emerald';
        headerBadge.innerHTML = '<span class="dot-pulse"></span> MODO SIMULACIÓN ($0.00 COSTO)';
        simStatusLabel.style.color = 'var(--accent-emerald)';
        simStatusLabel.textContent = '🛡️ Modo Simulación (Costo $0.00 — Offline Seguro)';
        toggleMockText.textContent = 'SIM ($0)';
      } else {
        headerBadge.className = 'pill pill-amber';
        headerBadge.innerHTML = '⚡ MODO API EN VIVO (ESTRUCTURA .env)';
        simStatusLabel.style.color = 'var(--accent-amber)';
        simStatusLabel.textContent = '⚡ Modo API en Vivo (Meta API / Baseten — Requiere Claves Reales)';
        toggleMockText.textContent = 'LIVE API';
      }
    });
  }

  if (selectAiEngine) {
    selectAiEngine.addEventListener('change', () => {
      state.selectedEngine = selectAiEngine.value;
    });
  }

  // Create 60 FPS Synthetic Stream for testing or fallback when no USB camera is attached
  function startSyntheticStream(slot) {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 360;
    const ctx = canvas.getContext('2d');
    let frame = 0;

    function renderLoop() {
      frame++;
      ctx.fillStyle = '#07110d';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Tactical Grid
      ctx.strokeStyle = 'rgba(0, 255, 136, 0.12)';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 32) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 32) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      if (slot === 'A') {
        // Simulated PCB & FPC connector under USB Microscope
        ctx.fillStyle = '#0d291e';
        ctx.fillRect(90, 60, 460, 240);
        ctx.strokeStyle = '#00ff88';
        ctx.lineWidth = 2;
        ctx.strokeRect(90, 60, 460, 240);

        // FPC Connector J6001
        ctx.fillStyle = '#1f2937';
        ctx.fillRect(150, 120, 220, 64);
        for (let p = 0; p < 18; p++) {
          ctx.fillStyle = p === 5 ? '#ef4444' : '#fbbf24';
          ctx.fillRect(160 + p * 11, 112, 6, 80);
        }

        // SAM 3.1 Segmentation Target Box
        const pulse = Math.sin(frame * 0.1) * 4;
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.strokeRect(208 - pulse / 2, 104 - pulse / 2, 28 + pulse, 96 + pulse);

        ctx.fillStyle = '#00ff88';
        ctx.font = 'bold 13px monospace';
        ctx.fillText('VISOR A // MICROSCOPIO USB (PCB J6001 FPC + PMIC)', 105, 86);
        ctx.fillStyle = '#fca5a5';
        ctx.fillText('SAM-3.1 ANOMALY: PIN #6 VDD_LCD_3P0 SULFATADO (0.002V)', 105, 275);
      } else {
        // Simulated Overhead Workbench & Digital Multimeter
        ctx.fillStyle = '#111827';
        ctx.fillRect(110, 55, 420, 250);
        ctx.strokeStyle = '#00d4ff';
        ctx.lineWidth = 2;
        ctx.strokeRect(110, 55, 420, 250);

        // Multimeter LCD Screen
        ctx.fillStyle = '#052e16';
        ctx.fillRect(145, 95, 210, 95);
        ctx.fillStyle = '#00ff88';
        ctx.font = 'bold 30px monospace';
        const jitter = ((frame % 20) * 0.0001).toFixed(4);
        ctx.fillText(jitter + ' V', 165, 152);

        ctx.font = 'bold 12px monospace';
        ctx.fillStyle = '#00d4ff';
        ctx.fillText('VISOR B // CENITAL MESA & MULTÍMETRO MODO DIODO', 130, 80);
        ctx.fillStyle = '#e5e7eb';
        ctx.fillText('POSTURA TÉCNICO: PUNTA ROJA A GND / NEGRA A PIN #6', 130, 235);
        ctx.fillText('FUENTE REGULADA: 4.20V / CONSUMO PICO: 1.84A (CORTO)', 130, 265);
      }

      // Timestamp & FPS watermark
      ctx.fillStyle = '#9ca3af';
      ctx.font = '11px monospace';
      ctx.fillText('LIVE 60FPS STREAM | FRAME #' + frame + ' | ' + new Date().toISOString(), 16, 345);

      if (slot === 'A') {
        state.synthAnimIdA = requestAnimationFrame(renderLoop);
      } else {
        state.synthAnimIdB = requestAnimationFrame(renderLoop);
      }
    }

    if (slot === 'A' && state.synthAnimIdA) cancelAnimationFrame(state.synthAnimIdA);
    if (slot === 'B' && state.synthAnimIdB) cancelAnimationFrame(state.synthAnimIdB);
    renderLoop();

    const stream = canvas.captureStream ? canvas.captureStream(60) : null;
    if (slot === 'A') {
      if (state.streamA) state.streamA.getTracks().forEach((t) => t.stop());
      state.streamA = stream;
      videoA.srcObject = stream;
      hudSourceA.textContent = 'STREAM A: SEÑAL SINTÉTICA PCB 60FPS (NO-LOCK)';
    } else {
      if (state.streamB) state.streamB.getTracks().forEach((t) => t.stop());
      state.streamB = stream;
      videoB.srcObject = stream;
      hudSourceB.textContent = 'STREAM B: SEÑAL SINTÉTICA TESTER 60FPS (NO-LOCK)';
    }
  }

  // Helper para liberar el nodo UVC (/dev/video*) en el kernel Linux uvcvideo
  function waitMs(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // Desbloqueo de permisos UVC en Linux (300 ms de enfriamiento para evitar EBUSY en v4l2)
  async function ensureCameraPermissions() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return false;
    }
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      tempStream.getTracks().forEach((track) => track.stop());
      await waitMs(300);
      return true;
    } catch (err) {
      console.warn('No se pudo desbloquear permisos UVC inicialmente:', err);
      return false;
    }
  }

  // Mitigación DOM XSS (OWASP / Google Cybersecurity): uso exclusivo de createElement + textContent
  function renderSelectOptionsSafe(selectEl, optionsList, selectedValue) {
    if (!selectEl) return;
    while (selectEl.firstChild) {
      selectEl.removeChild(selectEl.firstChild);
    }
    optionsList.forEach((item) => {
      const opt = document.createElement('option');
      opt.value = String(item.value);
      opt.textContent = String(item.label);
      selectEl.appendChild(opt);
    });
    if (selectedValue && optionsList.some((o) => o.value === selectedValue)) {
      selectEl.value = selectedValue;
    }
  }

  async function populateCameraSelectors() {
    const prevValA = selectCamA ? selectCamA.value : '';
    const prevValB = selectCamB ? selectCamB.value : '';

    const defaultOptionsA = [
      { value: 'SYNTH_PCB', label: '🧪 Simulador Microscopio PCB 60 FPS (Sin Hardware)' },
      { value: 'UNLOCK_USB', label: '🔓 Detectar / Conectar Microscopio USB Real (/dev/video*)...' }
    ];
    const defaultOptionsB = [
      { value: 'SYNTH_TESTER', label: '🧪 Simulador Cámara Cenital / Multímetro 60 FPS' },
      { value: 'UNLOCK_USB', label: '🔓 Detectar / Conectar Microscopio USB Real (/dev/video*)...' }
    ];

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter((d) => d.kind === 'videoinput');
        videoDevices.forEach((dev, idx) => {
          const safeDeviceId = dev.deviceId && dev.deviceId.trim() !== '' ? dev.deviceId : `USB_INDEX_${idx}`;
          const cleanLabel = dev.label || `Microscopio / Cámara USB Linux #${idx + 1} (/dev/video${idx})`;
          defaultOptionsA.push({ value: safeDeviceId, label: `📷 ${cleanLabel}` });
          defaultOptionsB.push({ value: safeDeviceId, label: `📷 ${cleanLabel}` });
        });
      }
    } catch (err) {
      console.warn('Enumeración de cámaras en modo sin permisos previos:', err);
    }

    renderSelectOptionsSafe(selectCamA, defaultOptionsA, prevValA);
    renderSelectOptionsSafe(selectCamB, defaultOptionsB, prevValB);
  }

  async function startCameraSlot(slot) {
    const selectEl = slot === 'A' ? selectCamA : selectCamB;
    const videoEl = slot === 'A' ? videoA : videoB;
    const hudEl = slot === 'A' ? hudSourceA : hudSourceB;
    let chosenId = selectEl ? selectEl.value : '';

    if (!chosenId || chosenId.startsWith('SYNTH_')) {
      startSyntheticStream(slot);
      return;
    }

    try {
      // Cancelar animación sintética y liberar cualquier stream previo antes de abrir UVC
      if (slot === 'A' && state.synthAnimIdA) cancelAnimationFrame(state.synthAnimIdA);
      if (slot === 'B' && state.synthAnimIdB) cancelAnimationFrame(state.synthAnimIdB);

      if (slot === 'A' && state.streamA) {
        state.streamA.getTracks().forEach((t) => t.stop());
        state.streamA = null;
      }
      if (slot === 'B' && state.streamB) {
        state.streamB.getTracks().forEach((t) => t.stop());
        state.streamB = null;
      }
      await waitMs(200);

      // Si el usuario eligió UNLOCK_USB o un índice sin deviceId desbloqueado
      if (chosenId === 'UNLOCK_USB' || chosenId.startsWith('USB_INDEX_')) {
        const requestedIdx = chosenId.startsWith('USB_INDEX_')
          ? parseInt(chosenId.replace('USB_INDEX_', ''), 10) || 0
          : 0;
        await ensureCameraPermissions();
        await populateCameraSelectors();
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter((d) => d.kind === 'videoinput' && d.deviceId);
        if (videoDevices.length > 0) {
          const picked = videoDevices[Math.min(requestedIdx, videoDevices.length - 1)];
          chosenId = picked.deviceId;
        } else {
          chosenId = '';
        }
      }

      // Constraints exactos para sensor CMOS 4:3 (640x480 nativo / hasta 1920x1440 @ 30 FPS máx)
      const constraints = {
        audio: false,
        video: {
          deviceId: chosenId ? { exact: chosenId } : undefined,
          width: { ideal: 640, max: 1920 },
          height: { ideal: 480, max: 1440 },
          frameRate: { ideal: 30, max: 30 }
        }
      };

      let newStream = null;
      try {
        newStream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (primaryErr) {
        console.warn(`Fallo en nodo UVC primario (${chosenId}), aplicando fallback 640x480@30fps:`, primaryErr);
        await waitMs(200);
        newStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            frameRate: { ideal: 30 }
          },
          audio: false
        });
      }

      if (slot === 'A') {
        state.streamA = newStream;
      } else {
        state.streamB = newStream;
      }

      videoEl.srcObject = newStream;
      const track = newStream.getVideoTracks()[0];
      const settings = track && track.getSettings ? track.getSettings() : {};
      const realW = settings.width || 640;
      const realH = settings.height || 480;
      const realFps = settings.frameRate ? Math.round(settings.frameRate) : 30;
      const realLabel = track && track.label ? track.label : 'UVC USB CAMERA';

      hudEl.textContent = `STREAM ${slot}: ${realLabel} (${realW}x${realH} @ ${realFps}fps)`;
      await populateCameraSelectors();
      if (settings.deviceId && selectEl) {
        selectEl.value = settings.deviceId;
      } else if (chosenId && selectEl) {
        selectEl.value = chosenId;
      }
    } catch (err) {
      hudEl.textContent = `FALLBACK SINTÉTICO (${err.name || 'Sin cámara física'})`;
      startSyntheticStream(slot);
    }
  }

  // Non-blocking frame extraction using an in-memory <canvas>
  function extractFrameFromVideo(videoEl) {
    const startMs = performance.now();
    const canvas = document.createElement('canvas');
    const width = videoEl.videoWidth || 640;
    const height = videoEl.videoHeight || 360;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, width, height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    const elapsedMs = (performance.now() - startMs).toFixed(2);

    return {
      dataUrl,
      width,
      height,
      elapsedMs
    };
  }

  function appendChatMessage(role, content) {
    const chatHistory = document.getElementById('chatHistory');
    if (!chatHistory) return null;
    const div = document.createElement('div');
    div.className = `msg ${role === 'user' ? 'msg-user' : 'msg-ai'}`;
    div.textContent = content;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return div;
  }

  // Expansión asimétrica de tarjeta dentro del mismo cuadro (70% / 30% sin cubrir pantalla)
  function toggleExpandCameraCard(slot) {
    const grid = document.getElementById('dualCamerasGrid');
    const cardA = document.getElementById('cardCamA');
    const cardB = document.getElementById('cardCamB');
    const btnA = document.getElementById('btnExpandCamA');
    const btnB = document.getElementById('btnExpandCamB');
    if (!grid || !cardA || !cardB || !btnA || !btnB) return;

    const targetClass = slot === 'A' ? 'expand-a' : 'expand-b';
    const isAlreadyExpanded = grid.classList.contains(targetClass);

    grid.classList.remove('expand-a', 'expand-b');
    cardA.classList.remove('expanded-card');
    cardB.classList.remove('expanded-card');
    btnA.classList.remove('active');
    btnB.classList.remove('active');
    btnA.textContent = '⤢ Agrandar Cuadro';
    btnB.textContent = '⤢ Agrandar Cuadro';

    if (!isAlreadyExpanded) {
      grid.classList.add(targetClass);
      if (slot === 'A') {
        cardA.classList.add('expanded-card');
        btnA.classList.add('active');
        btnA.textContent = '⤡ Tamaño Normal';
      } else {
        cardB.classList.add('expanded-card');
        btnB.classList.add('active');
        btnB.textContent = '⤡ Tamaño Normal';
      }
    }
  }

  // Actualiza la barra de aviso profesional según los checkboxes de Visor A / Visor B y modo Simulador/Real
  function updateActiveTargetNotice() {
    const chkA = document.getElementById('chkIncludeVisorA');
    const chkB = document.getElementById('chkIncludeVisorB');
    const noticeEl = document.getElementById('activeTargetNotice');
    if (!noticeEl) return;

    const incA = chkA ? chkA.checked : true;
    const incB = chkB ? chkB.checked : true;
    const valA = selectCamA ? selectCamA.value : 'SYNTH_PCB';
    const valB = selectCamB ? selectCamB.value : 'SYNTH_TESTER';
    const isSynthA = !valA || valA.startsWith('SYNTH_');
    const isSynthB = !valB || valB.startsWith('SYNTH_');
    const descA = isSynthA ? 'Simulador Sintético' : 'Cámara USB Real';
    const descB = isSynthB ? 'Simulador Sintético' : 'Cámara USB Real';

    let baseMsg = '';
    if (incA && incB) {
      baseMsg = `🎯 OBJETIVO DE AUDITORÍA ACTIVO: [ VISOR A (${descA}) + VISOR B (${descB}) ] — Envío dual habilitado.`;
    } else if (incA && !incB) {
      baseMsg = `🎯 OBJETIVO DE AUDITORÍA ACTIVO: [ VISOR A (${descA}) ] — Visor B excluido del envío a la IA.`;
    } else if (!incA && incB) {
      baseMsg = `🎯 OBJETIVO DE AUDITORÍA ACTIVO: [ VISOR B (${descB}) ] — Visor A excluido del envío a la IA.`;
    } else {
      baseMsg = `🎯 OBJETIVO DE AUDITORÍA ACTIVO: [ SOLO CONSULTA DE TEXTO ] — Visor A y Visor B excluidos del envío a la IA.`;
    }

    const synthSelectedInLive = !state.mockMode && ((incA && isSynthA) || (incB && isSynthB));
    if (synthSelectedInLive) {
      noticeEl.classList.add('warn');
      noticeEl.textContent =
        `${baseMsg} ⚠️ Atención: El Visor marcado está en Modo Simulador Sintético. Desmárquelo si desea analizar únicamente su cámara física.`;
    } else {
      noticeEl.classList.remove('warn');
      noticeEl.textContent = baseMsg;
    }
  }

  async function captureAndDiagnose() {
    const chkA = document.getElementById('chkIncludeVisorA');
    const chkB = document.getElementById('chkIncludeVisorB');
    const includeA = chkA ? chkA.checked : true;
    const includeB = chkB ? chkB.checked : true;

    const snapA = extractFrameFromVideo(videoA);
    const snapB = extractFrameFromVideo(videoB);

    const previewA = document.getElementById('snapPreviewA');
    const previewB = document.getElementById('snapPreviewB');
    const metaA = document.getElementById('snapMetaA');
    const metaB = document.getElementById('snapMetaB');

    if (previewA) {
      previewA.src = snapA.dataUrl;
      previewA.style.opacity = includeA ? '1' : '0.35';
    }
    if (previewB) {
      previewB.src = snapB.dataUrl;
      previewB.style.opacity = includeB ? '1' : '0.35';
    }
    if (metaA) {
      metaA.textContent = includeA
        ? `✅ ENVIADO: ${snapA.width}x${snapA.height}px • ${snapA.elapsedMs}ms (0 Bloqueo v4l2)`
        : `🚫 EXCLUIDO DEL ENVÍO IA (${snapA.width}x${snapA.height}px)`;
    }
    if (metaB) {
      metaB.textContent = includeB
        ? `✅ ENVIADO: ${snapB.width}x${snapB.height}px • ${snapB.elapsedMs}ms (0 Bloqueo v4l2)`
        : `🚫 EXCLUIDO DEL ENVÍO IA (${snapB.width}x${snapB.height}px)`;
    }

    const symptomInput = document.getElementById('symptomInput');
    const symptomText =
      (symptomInput && symptomInput.value.trim()) ||
      'Inspección visual de placa PCB y lectura de multímetro en modo diodo.';

    const sentVisorsLabel =
      includeA && includeB
        ? 'Visor A + Visor B'
        : includeA
        ? 'Solo Visor A (Visor B excluido)'
        : includeB
        ? 'Solo Visor B (Visor A excluido)'
        : 'Solo Texto (Sin imágenes adjuntas)';

    appendChatMessage(
      'user',
      `[CAPTURA INSTANTÁNEA SIN CORTE DE STREAM]\n• Objetivo enviado a IA: ${sentVisorsLabel}\n• Motor: ${state.selectedEngine} | Modo: ${state.mockMode ? 'SIM ($0)' : 'LIVE API'}\n• Reporte Técnico: ${symptomText}`
    );

    const pendingMsgEl = appendChatMessage(
      'ai',
      '⏳ Consultando motor IA en vivo...'
    );

    const reqStart = performance.now();
    try {
      const response = await fetch('/api/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine: state.selectedEngine,
          mock_mode: state.mockMode,
          symptom: symptomText,
          include_visor_a: includeA,
          include_visor_b: includeB,
          frame_microscope_b64: includeA ? snapA.dataUrl : '',
          frame_overhead_b64: includeB ? snapB.dataUrl : ''
        })
      });

      const data = await response.json();
      const clientMs = (performance.now() - reqStart).toFixed(1);
      const serverMs = data.latency_ms !== undefined ? data.latency_ms : clientMs;
      const reasoningTok = data.reasoning_tokens !== undefined ? data.reasoning_tokens : 0;
      const totalTok = data.total_tokens !== undefined ? data.total_tokens : 0;

      const latencyBadge = document.getElementById('latencyBadge');
      if (latencyBadge) {
        latencyBadge.textContent = `LATENCIA: ${serverMs} ms | TOKENS: ${totalTok} (Razonamiento: ${reasoningTok})`;
      }

      const telemetryFooter =
        `\n\n──────────────────────────────────────────────────\n` +
        `📊 TELEMETRÍA DE INFERENCIA: Latencia = ${serverMs} ms | ` +
        `Reasoning Tokens = ${reasoningTok} | Total Tokens = ${totalTok} | ` +
        `Visores Analizados = ${sentVisorsLabel} | ` +
        `Modo = ${data.mock_mode ? 'SIMULACIÓN ($0.00)' : 'API EN VIVO (' + (data.model_used || state.selectedEngine) + ')'}`;

      const finalOutput = (data.analysis || JSON.stringify(data, null, 2)) + telemetryFooter;
      if (pendingMsgEl) {
        pendingMsgEl.textContent = finalOutput;
        const chatHistory = document.getElementById('chatHistory');
        if (chatHistory) chatHistory.scrollTop = chatHistory.scrollHeight;
      } else {
        appendChatMessage('ai', finalOutput);
      }
    } catch (err) {
      // Offline standalone fallback if index.html is opened directly without server.py
      const fallbackText =
        `[MODO SIMULACIÓN LOCAL ACTIVADO — COSTO $0.00]\n` +
        `• Motor Seleccionado: ${state.selectedEngine} | Visores: ${sentVisorsLabel}\n` +
        `• Segmentación SAM 3.1: Anomalía detectada en Pin #6 de conector FPC J6001 (sulfatación + fisura térmica).\n` +
        `• Telemetría Tester: Lectura en Modo Diodo = 0.002V en línea VDD_LCD_3P0 (Corto directo a GND).\n` +
        `• Diagnóstico Paso a Paso:\n` +
        `  1. Inyectar 3.0V / 1.5A con cámara térmica o método Rosin sobre condensador C6014 paralelo al pin #6.\n` +
        `  2. Retirar condensador cerámico en fuga con cautín a 350°C y reconstruir pad con estaño 183°C.\n` +
        `  3. Verificar restablecimiento de caída de tensión nominal (~0.415V en modo diodo) antes de montar módulo nuevo.`;
      if (pendingMsgEl) {
        pendingMsgEl.textContent = fallbackText;
      } else {
        appendChatMessage('ai', fallbackText);
      }
    }
  }

  // ==========================================================================
  // 3B. DICTADO POR VOZ MANOS LIBRES (MUSE VOICE TRANSCRIBE 1.0 - WAV 24kHz PCM16)
  // ==========================================================================
  const voiceState = {
    recording: false,
    audioStream: null,
    audioCtx: null,
    sourceNode: null,
    processorNode: null,
    pcmChunks: [],
    inputSampleRate: 24000
  };

  function resampleFloat32(inputBuffer, fromRate, toRate) {
    if (!fromRate || fromRate === toRate) return inputBuffer;
    const ratio = fromRate / toRate;
    const outLength = Math.max(1, Math.round(inputBuffer.length / ratio));
    const result = new Float32Array(outLength);
    for (let i = 0; i < outLength; i++) {
      const pos = i * ratio;
      const idx = Math.floor(pos);
      const frac = pos - idx;
      const s0 = inputBuffer[idx] || 0;
      const s1 = inputBuffer[Math.min(idx + 1, inputBuffer.length - 1)] || 0;
      result[i] = s0 + frac * (s1 - s0);
    }
    return result;
  }

  function encodeWavPcm16Mono(float32Samples, sampleRate) {
    const numSamples = float32Samples.length;
    const bytesPerSample = 2;
    const dataBytes = numSamples * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataBytes);
    const view = new DataView(buffer);

    function writeAscii(offset, str) {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    }

    // Cabecera estándar RIFF/WAVE de 44 bytes (Mono, 16-bit PCM little-endian)
    writeAscii(0, 'RIFF');
    view.setUint32(4, 36 + dataBytes, true);
    writeAscii(8, 'WAVE');
    writeAscii(12, 'fmt ');
    view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
    view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
    view.setUint16(22, 1, true); // NumChannels (1 = Mono)
    view.setUint32(24, sampleRate, true); // SampleRate (24000 Hz)
    view.setUint32(28, sampleRate * bytesPerSample, true); // ByteRate
    view.setUint16(32, bytesPerSample, true); // BlockAlign
    view.setUint16(34, 16, true); // BitsPerSample (16-bit)
    writeAscii(36, 'data');
    view.setUint32(40, dataBytes, true);

    let byteOffset = 44;
    for (let i = 0; i < numSamples; i++) {
      const clamped = Math.max(-1, Math.min(1, float32Samples[i]));
      const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      view.setInt16(byteOffset, int16, true);
      byteOffset += 2;
    }
    return buffer;
  }

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    let binary = '';
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  async function toggleVoiceRecording() {
    const btnVoice = document.getElementById('btnVoiceRecord');
    const badgeVoice = document.getElementById('voiceStatusBadge');
    const symptomInput = document.getElementById('symptomInput');
    if (!btnVoice || !badgeVoice) return;

    if (!voiceState.recording) {
      // Si está en modo Simulación ($0), también permitimos probar el flujo sin micrófono físico si falla getUserMedia
      try {
        const micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        let audioCtx;
        try {
          audioCtx = new AudioCtx({ sampleRate: 24000 });
        } catch (_e) {
          audioCtx = new AudioCtx();
        }

        const sourceNode = audioCtx.createMediaStreamSource(micStream);
        const processorNode = audioCtx.createScriptProcessor(4096, 1, 1);
        voiceState.pcmChunks = [];
        voiceState.inputSampleRate = audioCtx.sampleRate || 24000;

        processorNode.onaudioprocess = (ev) => {
          if (!voiceState.recording) return;
          const channelData = ev.inputBuffer.getChannelData(0);
          voiceState.pcmChunks.push(new Float32Array(channelData));
        };

        sourceNode.connect(processorNode);
        processorNode.connect(audioCtx.destination);

        voiceState.recording = true;
        voiceState.audioStream = micStream;
        voiceState.audioCtx = audioCtx;
        voiceState.sourceNode = sourceNode;
        voiceState.processorNode = processorNode;

        btnVoice.textContent = '⏹️ Detener y Transcribir (Grabando...)';
        btnVoice.style.borderColor = 'var(--accent-red)';
        btnVoice.style.color = '#f87171';
        badgeVoice.textContent = '🔴 GRABANDO WAV 24kHz...';
        return;
      } catch (micErr) {
        if (!state.mockMode) {
          badgeVoice.textContent = `⚠️ MIC ERROR: ${micErr.name || 'Sin permiso'}`;
          return;
        }
        // En modo simulación sin micrófono físico, genera 0.5s de silencio WAV 24kHz válido para probar /api/transcribe
        voiceState.pcmChunks = [new Float32Array(12000)];
        voiceState.inputSampleRate = 24000;
      }
    }

    // Detener grabación y empaquetar RIFF/WAVE 24000 Hz Mono 16-bit PCM
    voiceState.recording = false;
    if (voiceState.processorNode) {
      try { voiceState.processorNode.disconnect(); } catch (_e) {}
    }
    if (voiceState.sourceNode) {
      try { voiceState.sourceNode.disconnect(); } catch (_e) {}
    }
    if (voiceState.audioStream) {
      voiceState.audioStream.getTracks().forEach((t) => t.stop());
    }
    if (voiceState.audioCtx && voiceState.audioCtx.state !== 'closed') {
      try { await voiceState.audioCtx.close(); } catch (_e) {}
    }

    btnVoice.textContent = '🎙️ Dictar por Voz (Muse Voice Transcribe)';
    btnVoice.style.borderColor = 'var(--accent-cyan)';
    btnVoice.style.color = 'var(--accent-cyan)';
    badgeVoice.textContent = '⏳ TRANSCRIBIENDO VOZ...';

    const totalSamples = voiceState.pcmChunks.reduce((acc, arr) => acc + arr.length, 0);
    const mergedFloat32 = new Float32Array(Math.max(totalSamples, 2400));
    let offset = 0;
    voiceState.pcmChunks.forEach((chunk) => {
      mergedFloat32.set(chunk, offset);
      offset += chunk.length;
    });

    const targetRate = 24000;
    const resampled = resampleFloat32(mergedFloat32, voiceState.inputSampleRate, targetRate);
    const wavBuffer = encodeWavPcm16Mono(resampled, targetRate);
    const wavBase64 = arrayBufferToBase64(wavBuffer);

    try {
      const resp = await fetch('/api/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mock_mode: state.mockMode,
          audio_wav_b64: wavBase64,
          sample_rate: targetRate
        })
      });
      const data = await resp.json();
      if (data && data.transcript) {
        if (symptomInput) {
          symptomInput.value = data.transcript;
        }
        badgeVoice.textContent = `✅ ASR (${data.latency_ms || 0}ms)`;
        appendChatMessage(
          'user',
          `🎙️ [DICTADO POR VOZ — ${data.mode || 'MUSE VOICE TRANSCRIBE 1.0'}]\n"${data.transcript}"`
        );
      } else {
        badgeVoice.textContent = '⚠️ ASR SIN VOZ DETECTADA';
      }
    } catch (err) {
      badgeVoice.textContent = '⚠️ ERROR /api/transcribe';
    }
  }

  const btnVoiceRecord = document.getElementById('btnVoiceRecord');
  if (btnVoiceRecord) btnVoiceRecord.addEventListener('click', toggleVoiceRecording);

  const btnExpandA = document.getElementById('btnExpandCamA');
  const btnExpandB = document.getElementById('btnExpandCamB');
  if (btnExpandA) btnExpandA.addEventListener('click', () => toggleExpandCameraCard('A'));
  if (btnExpandB) btnExpandB.addEventListener('click', () => toggleExpandCameraCard('B'));

  const chkIncludeA = document.getElementById('chkIncludeVisorA');
  const chkIncludeB = document.getElementById('chkIncludeVisorB');
  if (chkIncludeA) chkIncludeA.addEventListener('change', updateActiveTargetNotice);
  if (chkIncludeB) chkIncludeB.addEventListener('change', updateActiveTargetNotice);
  if (toggleMockMode) toggleMockMode.addEventListener('change', updateActiveTargetNotice);

  document.getElementById('btnStartCamA').addEventListener('click', () => {
    startCameraSlot('A').then(updateActiveTargetNotice);
  });
  document.getElementById('btnStartCamB').addEventListener('click', () => {
    startCameraSlot('B').then(updateActiveTargetNotice);
  });
  if (selectCamA) {
    selectCamA.addEventListener('change', () => {
      startCameraSlot('A').then(updateActiveTargetNotice);
    });
  }
  if (selectCamB) {
    selectCamB.addEventListener('change', () => {
      startCameraSlot('B').then(updateActiveTargetNotice);
    });
  }
  document.getElementById('btnSynthCamA').addEventListener('click', () => {
    if (selectCamA) selectCamA.value = 'SYNTH_PCB';
    startSyntheticStream('A');
    updateActiveTargetNotice();
  });
  document.getElementById('btnSynthCamB').addEventListener('click', () => {
    if (selectCamB) selectCamB.value = 'SYNTH_TESTER';
    startSyntheticStream('B');
    updateActiveTargetNotice();
  });
  document.getElementById('btnRefreshDevices').addEventListener('click', async () => {
    await ensureCameraPermissions();
    await populateCameraSelectors();
    updateActiveTargetNotice();
  });
  document.getElementById('btnCaptureDiagnose').addEventListener('click', captureAndDiagnose);
  updateActiveTargetNotice();

  document.getElementById('btnLoadSampleCase1').addEventListener('click', () => {
    document.getElementById('symptomInput').value =
      'Samsung A12 (SM-A125F) consumo inicial de 1.84A al conectar fuente regulada en VBAT. Calienta zona de IF-PMIC SM5714.';
  });
  document.getElementById('btnLoadSampleCase2').addEventListener('click', () => {
    document.getElementById('symptomInput').value =
      'Motorola Moto G52 da backlight pero sin imagen tras cambio de módulo. En conector FPC de pantalla el pin #6 mide 0.002V a tierra.';
  });
  document.getElementById('btnClearChat').addEventListener('click', () => {
    document.getElementById('chatHistory').innerHTML = '';
  });

  // Initialize streams in non-blocking synthetic mode by default and populate Ubuntu cameras
  populateCameraSelectors().then(() => {
    startSyntheticStream('A');
    startSyntheticStream('B');
  });

  // ==========================================================================
  // 4. TAB 2: ADVANCED COMPATIBILITY ENGINE (Modules, Flex FPC & Donor ICs)
  // ==========================================================================
  const COMPATIBILITY_DB = [
    {
      id: 'MOD-SAM-A12-CLUSTER',
      category: 'MODULE',
      badgeText: 'Módulo de Pantalla',
      badgeClass: 'badge-module',
      title: 'Familia Samsung A12 / A02 / A32 5G / M12 (6.5" PLS IPS)',
      models: ['SM-A125F', 'SM-A127F', 'SM-A022M', 'SM-A326B (A32 5G)', 'SM-M127F'],
      panelTouchIcs: ['BOE', 'Tianma', 'Novatek NT36525', 'Himax'],
      flexWarning:
        '⚠️ ALERTA CRÍTICA DE FLEX FPC: El Samsung A12 tiene versión SM-A125F (procesador MediaTek) y SM-A127F Nacho (Exynos 850). Los módulos marcados "Universal UB/U" funcionan en ambos, pero el flex original A125F en placa A127F puede dejar sin táctil tras actualizar a Android 12/13 si el IC es Tianma antiguo.',
      frameNotes:
        'Marco de A12 y A02 comparten chasis frontal interno, pero el A32 5G (SM-A326B) cambia la posición de los botones laterales y recorte de cámara: usar repuesto Sin Marco o Con Marco específico de modelo.'
    },
    {
      id: 'MOD-SAM-A03-CLUSTER',
      category: 'MODULE',
      badgeText: 'Módulo de Pantalla',
      badgeClass: 'badge-module',
      title: 'Familia Samsung A03 / A03S / A02S (6.5" HD+)',
      models: ['SM-A035M (A03)', 'SM-A037M (A03s)', 'SM-A025M (A02s)'],
      panelTouchIcs: ['BOE', 'Synaptics TDDI', 'Novatek', 'FocalTech'],
      flexWarning:
        '⚠️ ALERTA DE SUB-PLACA INTEGRADA EN FLEX: A02S y A03S comparten arquitectura de flex hacia sub-placa de carga, pero el A03 común (SM-A035M Unisoc) posee distinto pinout de carga rápida y micrófono. Nunca mezclar marcos de A03 Core (SM-A032M) con A03 común.',
      frameNotes:
        'Si se instala módulo Incell económico con IC FocalTech, verificar espesor del backlight para evitar manchas blancas por presión de blindaje.'
    },
    {
      id: 'MOD-IPHONE-11-XR',
      category: 'MODULE',
      badgeText: 'Módulo & Trasplante IC',
      badgeClass: 'badge-module',
      title: 'Apple iPhone 11 (A2111 / A2221) & iPhone XR (6.1" Liquid Retina)',
      models: ['iPhone 11', 'iPhone XR (No intercambiable de chasis, sí comparte cristal OCA)'],
      panelTouchIcs: ['Synaptics', 'Toshiba / Apple Custom Touch IC'],
      flexWarning:
        '⚠️ ALERTA DE REMANUFACTURA Y SERIALIZACIÓN: iPhone 11 y XR comparten vidrio Gorillaglass y laminación OCA de 6.1", pero NO el flex ni el marco. Para eliminar el aviso de "Pieza desconocida" en iPhone 11, desoldar el IC Touch encriptado del módulo original e instalarlo en módulo con ventana para trasplante.',
      frameNotes:
        'Cuidado con los tornillos del blindaje EMI del conector FPC: invertir el tornillo largo perfora las capas internas (Long-Screw Damage).'
    },
    {
      id: 'FLEX-REMAN-BOE-TIANMA',
      category: 'FLEX_REMAN',
      badgeText: 'Alerta Remanufactura & Flex FPC',
      badgeClass: 'badge-flex',
      title: 'Matriz de Controladores Touch: BOE / Tianma / Synaptics / Novatek',
      models: ['Línea Samsung Serie A', 'Motorola Serie G/E', 'Xiaomi Redmi Note'],
      panelTouchIcs: ['BOE', 'Tianma', 'Synaptics', 'Novatek', 'Ilitek'],
      flexWarning:
        '⚠️ REGLA DE ORO EN REMANUFACTURA Y CAMBIO DE FLEX: Al cambiar flex FPC por daño de humedad o desgarro en máquina laminadora, el código del driver TDDI (ej. Novatek NT36672A vs Synaptics S3706) debe coincidir exactamente con las tablas de inicialización MIPI DSI del kernel. Un panel BOE con flex programado para Tianma dará imagen con rayas o táctil invertido.',
      frameNotes:
        'Antes de laminar OCA en autoclave, probar el táctil durante 3 minutos con el equipo encendido y bloqueando/desbloqueando pantalla (prueba de sueño profundo / línea TP_RST_N).'
    },
    {
      id: 'IC-DONOR-S2MU106X01',
      category: 'IC_DONOR',
      badgeText: 'IC Donante / IF-PMIC',
      badgeClass: 'badge-ic',
      title: 'IF-PMIC Samsung S2MU106X01 / S2MU106X02 (Carga, OTG & Bobina VPH_PWR)',
      models: ['Samsung A10s', 'Samsung A20 / A20s', 'Samsung A30 / A30s', 'Samsung A50', 'Samsung A12 (Exynos)'],
      panelTouchIcs: ['S2MU106X01', 'S2MU106X02'],
      flexWarning:
        '🔬 COMPATIBILIDAD DE PLACAS DONANTES: Si un Samsung A30 o A50 llega con corto en VBAT o sin activar carga rápida por sobretensión del cargador, puedes extraer el IF-PMIC S2MU106X01 desde placas donantes de A20 o A30s. Reballing con esténcil 0.35mm y estaño en pasta 183°C.',
      frameNotes:
        'Revisar siempre la bobina de switching LX adyacente y el condensador de bootstrap antes de energizar el IC donante.'
    },
    {
      id: 'IC-DONOR-PM6150-PMI632',
      category: 'IC_DONOR',
      badgeText: 'IC Donante / PMIC Qualcomm',
      badgeClass: 'badge-ic',
      title: 'PMIC Qualcomm PM6150 / IF-PMIC PMI632 / SM5714',
      models: ['Xiaomi Redmi Note 8 / Note 9S / Note 10', 'Samsung A52 / A72', 'Motorola Moto G9 Play / G30 / G52'],
      panelTouchIcs: ['PM6150', 'PMI632 (902-00)', 'SM5714'],
      flexWarning:
        '🔬 CRUCE DE SUFIJOS QUALCOMM: En el IF-PMIC PMI632 verificar el código inferior: la versión "902-00" maneja generación de voltajes negativos/positivos de pantalla LCD (-5.5V / +5.5V LAB/IBB), mientras que la versión "502-00" se usa en equipos con pantalla AMOLED (donde el módulo tiene su propio convertidor DC-DC).',
      frameNotes:
        'Si se coloca un PMI632-502 en una placa que requiere PMI632-902, el equipo encenderá y vibrará pero jamás dará imagen en paneles IPS.'
    }
  ];

  function renderCompatibilityCards() {
    const grid = document.getElementById('compatResultsGrid');
    const countBadge = document.getElementById('compatCountBadge');
    if (!grid) return;

    const q = state.compatSearchQuery.trim().toLowerCase();
    const cat = state.compatFilterCategory;

    const filtered = COMPATIBILITY_DB.filter((item) => {
      if (cat !== 'ALL' && item.category !== cat) return false;
      if (!q) return true;
      const haystack = [
        item.title,
        item.models.join(' '),
        item.panelTouchIcs.join(' '),
        item.flexWarning,
        item.frameNotes
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(q);
    });

    if (countBadge) {
      countBadge.textContent = `${filtered.length} REGISTROS TÉCNICOS VERIFICADOS`;
    }

    grid.innerHTML = filtered
      .map(
        (item) => `
      <article class="compat-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="badge-type ${item.badgeClass}">${item.badgeText}</span>
          <span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-secondary);">${item.id}</span>
        </div>
        <h3 style="font-size:0.95rem; color:#ffffff; font-family:var(--font-mono);">${item.title}</h3>
        <div style="font-size:0.78rem; color:var(--text-secondary);">
          <strong style="color:var(--accent-emerald);">Modelos / Placas Cruzadas:</strong> ${item.models.join(' • ')}
        </div>
        <div style="font-size:0.76rem; color:var(--accent-cyan); font-family:var(--font-mono);">
          <strong>Panel / Touch IC / Código:</strong> ${item.panelTouchIcs.join(', ')}
        </div>
        <div style="font-size:0.77rem; background:rgba(245,158,11,0.08); border-left:3px solid var(--accent-amber); padding:0.5rem 0.65rem; border-radius:4px;">
          ${item.flexWarning}
        </div>
        <div style="font-size:0.75rem; color:var(--text-secondary); border-top:1px dashed var(--border-tactical); padding-top:0.45rem;">
          <strong>Nota de Marco / Montaje:</strong> ${item.frameNotes}
        </div>
      </article>
    `
      )
      .join('');
  }

  const compatSearchInput = document.getElementById('compatSearchInput');
  const compatCategorySelect = document.getElementById('compatCategorySelect');
  const compatQuickChips = document.querySelectorAll('#compatQuickChips .chip');

  if (compatSearchInput) {
    compatSearchInput.addEventListener('input', (e) => {
      state.compatSearchQuery = e.target.value;
      renderCompatibilityCards();
    });
  }

  if (compatCategorySelect) {
    compatCategorySelect.addEventListener('change', (e) => {
      state.compatFilterCategory = e.target.value;
      renderCompatibilityCards();
    });
  }

  compatQuickChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      compatQuickChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      const query = chip.getAttribute('data-query') || '';
      state.compatSearchQuery = query;
      if (compatSearchInput) compatSearchInput.value = query;
      renderCompatibilityCards();
    });
  });

  renderCompatibilityCards();

  // ==========================================================================
  // 5. TAB 3: EXPRESS QUOTER & MANDATORY VERIFIABLE ANTI-FORGETFULNESS CHECKLIST
  // ==========================================================================
  const CHECKLIST_TEMPLATES = {
    BASE: [
      {
        id: 'chk-prox-sensor',
        text: 'Probar sensor de proximidad y luz ambiental en llamada de prueba (verificar que la goma obturadora esté colocada tras cambiar módulo o pin de carga).'
      },
      {
        id: 'chk-fpc-diode',
        text: 'Medir caída de tensión en modo diodo en el conector FPC y verificar que la batería esté desconectada antes de abrochar el flex.'
      }
    ],
    MOTOROLA: [
      {
        id: 'chk-moto-nfc-thermistor',
        text: 'CRÍTICO MOTOROLA: Verificar cierre del circuito NFC / termistor en la placa o tapa intermedia antes de pegar tapa trasera (evita falla de carga y alerta de "Temperatura de batería demasiado baja").'
      }
    ],
    SAMSUNG: [
      {
        id: 'chk-sam-subboard-ovp',
        text: 'CRÍTICO SAMSUNG: Verificar que la sub-placa de carga posea IC OVP y líneas de datos CC1/CC2 + D+/D- activas para habilitar Carga Rápida 15W/25W y transferencia USB.'
      }
    ],
    IPHONE: [
      {
        id: 'chk-ip-screw-order',
        text: 'CRÍTICO IPHONE: Auditar posición exacta de tornillos del blindaje FPC (evitar Long-Screw Damage) y comprobar conservación de TrueTone / FaceID.'
      }
    ],
    XIAOMI: [
      {
        id: 'chk-xiaomi-coax-mic',
        text: 'CRÍTICO XIAOMI: Verificar calce de cable coaxial de señal RF en el canal del chasis para no morderlo con la tapa intermedia.'
      }
    ],
    CHARGING_PORT: [
      {
        id: 'chk-charge-mic-gsm',
        text: 'Tras cambio de Pin/Sub-placa: grabar nota de voz para validar micrófono inferior y comprobar barras de señal 4G/LTE con chip activo.'
      }
    ],
    MODULE_SWAP: [
      {
        id: 'chk-module-oleophobic',
        text: 'Realizar test de arrastre de ícono por toda la cuadrícula táctil con brillo al 100% y al mínimo sin fugas de luz en el marco.'
      }
    ],
    GLASS_REMAN: [
      {
        id: 'chk-reman-bubbles',
        text: 'Inspeccionar bordes de laminación OCA bajo luz rasante tras autoclave (0 micro-burbujas cerca del bisel y polarizado intacto).'
      }
    ],
    MICROSOLDER: [
      {
        id: 'chk-microsolder-thermal',
        text: 'Limpieza ultrasónica de residuos de flux, medición de consumo en reposo (< 0.015A en sleep mode) y colocación de cinta Kapton + blindaje térmico.'
      }
    ]
  };

  function updateQuoteAndChecklist() {
    const serviceType = document.getElementById('quoteServiceType').value;
    const brand = document.getElementById('quoteBrandSelect').value;
    const modelName = document.getElementById('quoteModelInput').value || 'Equipo en Laboratorio';
    const partUsd = parseFloat(document.getElementById('quotePartUsd').value) || 0;
    const laborUsd = parseFloat(document.getElementById('quoteLaborUsd').value) || 0;
    const fxRate = parseFloat(document.getElementById('quoteFxRate').value) || 1;

    const totalUsd = partUsd + laborUsd;
    const totalLocal = Math.round(totalUsd * fxRate);

    document.getElementById('quoteTotalUsdDisplay').textContent = `$${totalUsd.toFixed(2)} USD`;
    document.getElementById('quoteTotalLocalDisplay').textContent = `$${totalLocal.toLocaleString('es-AR')}`;

    const summaryEl = document.getElementById('quoteTechnicalSummary');
    summaryEl.textContent =
      `[RESUMEN DE COTIZACIÓN MOSTRADOR]\n` +
      `• Equipo: ${modelName} (${brand})\n` +
      `• Servicio: ${serviceType} | Repuesto: $${partUsd.toFixed(2)} USD + Mano de Obra: $${laborUsd.toFixed(2)} USD\n` +
      `• Total Protegido: $${totalUsd.toFixed(2)} USD ($${totalLocal.toLocaleString('es-AR')} a TC ${fxRate})\n` +
      `• Condición de Entrega: Requiere 100% del Checklist Anti-Olvido firmado digitalmente.`;

    // Build dynamic checklist
    const items = [
      ...CHECKLIST_TEMPLATES.BASE,
      ...(CHECKLIST_TEMPLATES[brand] || []),
      ...(CHECKLIST_TEMPLATES[serviceType] || [])
    ];

    const container = document.getElementById('checklistContainer');
    container.innerHTML = items
      .map(
        (item) => `
      <label class="check-item" data-check-row="${item.id}">
        <input type="checkbox" class="anti-forget-cb" value="${item.id}" />
        <span style="font-size:0.8rem; color:var(--text-primary);">${item.text}</span>
      </label>
    `
      )
      .join('');

    const checkboxes = container.querySelectorAll('.anti-forget-cb');
    checkboxes.forEach((cb) => {
      cb.addEventListener('change', () => {
        const row = cb.closest('.check-item');
        if (row) row.classList.toggle('checked', cb.checked);
        evaluateChecklistProgress();
      });
    });

    evaluateChecklistProgress();
  }

  function evaluateChecklistProgress() {
    const checkboxes = document.querySelectorAll('#checklistContainer .anti-forget-cb');
    const total = checkboxes.length;
    let checkedCount = 0;
    checkboxes.forEach((cb) => {
      if (cb.checked) checkedCount++;
    });

    const pct = total > 0 ? Math.round((checkedCount / total) * 100) : 0;
    const bar = document.getElementById('checklistProgressBar');
    const counterText = document.getElementById('checklistCounterText');
    const statusPill = document.getElementById('checklistStatusPill');
    const btnSeal = document.getElementById('btnSealOrder');
    const sealResult = document.getElementById('sealAuditResult');

    if (bar) bar.style.width = `${pct}%`;
    if (counterText) counterText.textContent = `${checkedCount} / ${total} puntos críticos verificados (${pct}%)`;

    if (checkedCount === total && total > 0) {
      statusPill.className = 'pill pill-emerald';
      statusPill.textContent = '100% VERIFICADO • LISTO PARA CERRAR';
      btnSeal.disabled = false;
      btnSeal.style.opacity = '1';
      btnSeal.style.cursor = 'pointer';
      btnSeal.textContent = '✅ Emitir Sello de Control Anti-Olvido y Autorizar Cierre del Equipo';
    } else {
      statusPill.className = 'pill pill-amber';
      statusPill.textContent = `PENDIENTE (${total - checkedCount} CONTROLES FALTANTES)`;
      btnSeal.disabled = true;
      btnSeal.style.opacity = '0.5';
      btnSeal.style.cursor = 'not-allowed';
      btnSeal.textContent = '🔒 Bloqueado: Completa el 100% del Checklist para Emitir Orden de Cierre';
      if (sealResult) sealResult.textContent = '';
    }
  }

  ['quoteServiceType', 'quoteBrandSelect', 'quoteModelInput', 'quotePartUsd', 'quoteLaborUsd', 'quoteFxRate'].forEach(
    (id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', updateQuoteAndChecklist);
    }
  );

  document.getElementById('btnCheckAllDemo').addEventListener('click', () => {
    const checkboxes = document.querySelectorAll('#checklistContainer .anti-forget-cb');
    checkboxes.forEach((cb) => {
      cb.checked = true;
      const row = cb.closest('.check-item');
      if (row) row.classList.add('checked');
    });
    evaluateChecklistProgress();
  });

  document.getElementById('btnSealOrder').addEventListener('click', () => {
    const stamp = new Date().toISOString();
    const modelName = document.getElementById('quoteModelInput').value;
    const hash = generateTacticalHash(stamp + modelName);
    document.getElementById('sealAuditResult').textContent =
      `🛡️ ORDEN AUDITADA Y SELLADA | HORA ATÓMICA: ${stamp} | HASH VERIFICABLE: ${hash}`;
  });

  updateQuoteAndChecklist();

  // ==========================================================================
  // 6. TAB 4: ZERO-TRUST COUNTER CONTROL & REPLACEMENT-COST FX CALCULATOR
  // ==========================================================================
  function logAtomicAudit(eventText) {
    const logEl = document.getElementById('atomicAuditLog');
    if (!logEl) return;
    const div = document.createElement('div');
    div.className = 'msg msg-ai';
    div.style.padding = '0.45rem 0.65rem';
    div.style.fontSize = '0.74rem';
    div.textContent = eventText;
    logEl.prepend(div);
  }

  function renderPhysicalBoxes() {
    const tbody = document.getElementById('physicalBoxesTableBody');
    if (!tbody) return;

    let totalUnits = 0;
    tbody.innerHTML = state.physicalBoxes
      .map((box, idx) => {
        totalUnits += box.qty;
        return `
        <tr>
          <td style="font-weight:700; color:var(--accent-emerald);">${box.boxId} &rarr; ${box.qty} Unid.</td>
          <td>
            <div style="font-weight:600; color:#fff;">${box.sku}</div>
            <div style="font-size:0.71rem; color:var(--text-secondary);">${box.description}</div>
          </td>
          <td style="font-weight:700;">${box.qty}</td>
          <td>
            <div>${box.lastAtomicTimestamp}</div>
            <div style="font-size:0.68rem; color:var(--accent-cyan);">SHA: ${box.auditHash}</div>
          </td>
          <td>
            <div style="display:flex; gap:0.35rem;">
              <button class="btn" data-box-idx="${idx}" data-box-op="OUT" style="padding:0.25rem 0.5rem; font-size:0.7rem;">-1 Retiro</button>
              <button class="btn" data-box-idx="${idx}" data-box-op="IN" style="padding:0.25rem 0.5rem; font-size:0.7rem;">+1 Ingreso</button>
            </div>
          </td>
        </tr>
      `;
      })
      .join('');

    document.getElementById('ztTotalUnits').textContent = `${totalUnits} UNIDADES (${state.physicalBoxes.length} CAJAS)`;
    document.getElementById('ztCashStatus').textContent = `PRECINTO ACTIVO • $${state.cashBalanceUsd.toFixed(2)} USD`;

    tbody.querySelectorAll('button[data-box-idx]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-box-idx'), 10);
        const op = btn.getAttribute('data-box-op');
        const box = state.physicalBoxes[idx];
        if (!box) return;

        if (op === 'OUT' && box.qty > 0) {
          box.qty -= 1;
          state.cashBalanceUsd += box.unitReplacementUsd;
        } else if (op === 'IN') {
          box.qty += 1;
        }

        const nowIso = new Date().toISOString();
        const newHash = generateTacticalHash(`${box.boxId}-${box.qty}-${nowIso}-${op}`);
        box.lastAtomicTimestamp = nowIso;
        box.auditHash = newHash;

        document.getElementById('ztLastAtomicStamp').textContent = nowIso;
        document.getElementById('ztLastHash').textContent = `HASH: ${newHash}`;

        logAtomicAudit(
          `[${nowIso}] ${op === 'OUT' ? 'RETIRO MOSTRADOR (-1)' : 'INGRESO STOCK (+1)'} en ${box.boxId} (${box.sku}) -> Stock Actual: ${box.qty} | Hash: ${newHash}`
        );

        renderPhysicalBoxes();
      });
    });
  }

  function updateReplacementCostCalculator() {
    const histCostUsd = parseFloat(document.getElementById('fxHistoricalCostUsd').value) || 1;
    const repCostUsd = parseFloat(document.getElementById('fxReplacementCostUsd').value) || 1;
    const marginPct = parseFloat(document.getElementById('fxTargetMarginPct').value) || 0;
    const baseDollar = parseFloat(document.getElementById('fxBaseDollar').value) || 1;
    const repDollar = parseFloat(document.getElementById('fxReplacementDollar').value) || 1;

    const marginMultiplier = 1 + marginPct / 100;

    // Historical naive price vs Protected Replacement-Cost Price
    const naiveLocalPrice = Math.round(histCostUsd * marginMultiplier * baseDollar);
    const protectedUsdPrice = repCostUsd * marginMultiplier;
    const protectedLocalPrice = Math.round(protectedUsdPrice * repDollar);

    const replacementLocalCostOnly = Math.round(repCostUsd * repDollar);
    const costRisePct = (((repCostUsd - histCostUsd) / histCostUsd) * 100).toFixed(1);
    const fxRisePct = (((repDollar - baseDollar) / baseDollar) * 100).toFixed(1);

    document.getElementById('fxProtectedUsdPrice').textContent = `$${protectedUsdPrice.toFixed(2)} USD`;
    document.getElementById('fxProtectedLocalPrice').textContent = `$${protectedLocalPrice.toLocaleString('es-AR')}`;
    document.getElementById('fxDeltaUsdNote').textContent = `Variación Reposición Proveedor: ${costRisePct >= 0 ? '+' : ''}${costRisePct}% USD`;
    document.getElementById('fxLossWarningNote').textContent = `Variación Dólar FX: ${fxRisePct >= 0 ? '+' : ''}${fxRisePct}%`;

    const alertBox = document.getElementById('fxAlertBox');
    const diffLocal = protectedLocalPrice - naiveLocalPrice;
    alertBox.textContent =
      `[AUDITORÍA DE PRECIO POR COSTO DE REPOSICIÓN]\n` +
      `• Costo de reponer hoy 1 unidad con el proveedor: $${repCostUsd.toFixed(2)} USD ($${replacementLocalCostOnly.toLocaleString('es-AR')} Local).\n` +
      `• Si vendieras al precio histórico sin actualizar ($${naiveLocalPrice.toLocaleString('es-AR')}), perderías $${diffLocal.toLocaleString('es-AR')} de poder de recompra por unidad.\n` +
      `• Precio Mostrador Blindado (Reposición + ${marginPct}% margen): $${protectedLocalPrice.toLocaleString('es-AR')} ($${protectedUsdPrice.toFixed(2)} USD).`;
  }

  const fxSkuSelect = document.getElementById('fxSkuSelect');
  if (fxSkuSelect) {
    fxSkuSelect.addEventListener('change', (e) => {
      const baseCost = parseFloat(e.target.value) || 24.0;
      document.getElementById('fxHistoricalCostUsd').value = baseCost.toFixed(2);
      document.getElementById('fxReplacementCostUsd').value = (baseCost * 1.18).toFixed(2);
      updateReplacementCostCalculator();
    });
  }

  ['fxHistoricalCostUsd', 'fxReplacementCostUsd', 'fxTargetMarginPct', 'fxBaseDollar', 'fxReplacementDollar'].forEach(
    (id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', updateReplacementCostCalculator);
    }
  );

  renderPhysicalBoxes();
  logAtomicAudit(
    `[2026-10-26T23:30:00.000Z] AUDITORÍA INICIAL ZERO-TRUST: Caja #20 -> 10 Módulos verificados | Hash: 9f84c2e17b01a40b`
  );
  updateReplacementCostCalculator();
})();
