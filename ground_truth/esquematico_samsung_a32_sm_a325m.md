# 📱 Esquemático y Pinout Verificable — Samsung Galaxy A32 4G (Placa SM-A325M)

> **Instrucción para el Técnico:** Podés pegar aquí tablas adicionales de caída de tensión (modo diodo), pinouts de conectores FPC o notas de tu placa **Samsung Galaxy A32 4G (`SM-A325M`)**. El motor de CircuitGuard AI escaneará e inyectará este archivo automáticamente en tiempo real en cada consulta o cruce de pines (`cross_schematic`).

## 1. Conector FPC Principal `HDC6000` (78 Pines — Main-Sub + Display)

| Conector | Pin / Línea | Nombre en Esquemático | Valor Nominal (Modo Diodo) | Función / IC Asociado |
| :--- | :--- | :--- | :--- | :--- |
| **HDC6000 (78p)** | Pines Extremos VBUS | `VBUS_OVP_IN` (5.0V / 9.0V) | `440 mV – 560 mV` | Entrada de carga desde sub-placa vía IC OVP hacia IF-PMIC `SM5714` |
| **HDC6000 (78p)** | Pines VBAT | `VBAT_SENSE` / `VBAT_MAIN` | `310 mV – 400 mV` | Alimentación principal de batería y sensado |
| **HDC6000 (78p)** | Datos USB | `USB_DP` / `USB_DM` | `580 mV – 710 mV` | Par diferencial USB 2.0 (Habilita carga rápida y datos) |
| **HDC6000 (78p)** | Líneas CC | `CC1` / `CC2` | `480 mV – 620 mV` | Detección de cable Tipo-C hacia `SM5714` |
| **HDC6000 (78p)** | Líneas Imagen OLED | `MIPI_DSI0_D0..D3` | `330 mV – 430 mV` | Pares diferenciales MIPI hacia SoC MediaTek Helio G80 (`MT6769V/CT`) |
| **HDC6000 (78p)** | Alimentación Display | `VDD_LCD_3P0` / `ELVDD` | `390 mV – 510 mV` | Alimentación de panel Super AMOLED |
| **HDC6000 (78p)** | Anclajes / Blindaje | `GND` | `0 mV – 2 mV` | Tierra de referencia |

## 2. Criterios de Diagnóstico Rápido en `SM-A325M`
- **PMIC Principal:** `MT6358VW` | **IF-PMIC / Charger:** `SM5714`.
- **Falla típica en `HDC6000`:** Fisura de soldadura o sulfatación en los pines de los extremos por torsión del flex interplaca. Resoldar pin por pin **exclusivamente con cautín de punta fina limada y flux con aguja** (prohibido usar aire caliente para no deformar el conector plástico de 78 pines).
