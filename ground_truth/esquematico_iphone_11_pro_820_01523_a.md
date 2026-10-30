# 🍎 Esquemático y Pinout Verificable — iPhone 11 Pro (Placa 820-01523-A)

> **Instrucción para el Técnico:** Podés pegar aquí tablas adicionales de caída de tensión (modo diodo), valores de resistencias/condensadores o notas de tu placa **iPhone 11 Pro (`820-01523-A`)**. El motor de CircuitGuard AI escaneará e inyectará este archivo automáticamente en tiempo real en cada consulta o cruce de pines (`cross_schematic`).

## 1. Conectores FPC Principales y Valores en Modo Diodo (Punta Roja a GND)

| Conector | Pin / Línea | Nombre en Esquemático | Valor Nominal (Modo Diodo) | Función / IC Asociado |
| :--- | :--- | :--- | :--- | :--- |
| **J6500 (Batería)** | Pin 1 / 2 | `PP_BATT_VCC` | `290 mV – 390 mV` | Línea positiva principal de batería hacia `U3300` (Tigris `SN2611A0`) |
| **J6500 (Batería)** | Pin Datos SDA | `I2C0_SMC_SDA_1V8` | `430 mV – 530 mV` | Comunicación SWI/I2C de batería (Gas Gauge) |
| **J6500 (Batería)** | Pin Datos SCL | `I2C0_SMC_SCL_1V8` | `430 mV – 530 mV` | Reloj I2C de batería |
| **J6500 (Batería)** | Anclajes Laterales | `GND` | `0 mV – 2 mV` | Tierra de chasis / referencia |
| **J6400 (Dock / Lightning)** | VBUS | `PP5V0_USB_CONN` | `420 mV – 540 mV` | Entrada de 5V/9V desde flex de carga hacia Tigris `U3300` |
| **J6400 (Dock / Lightning)** | USB Data P/N | `TRISTAR_BI_USB_FG_P/N` | `640 mV – 760 mV` | Líneas diferenciales USB hacia Hydra `U6300` (`CBTL1612A1`) |
| **J6400 (Dock / Lightning)** | CC1 / ACC1 | `HYDRA_CON_DETECT_L` | `510 mV – 650 mV` | Detección de accesorio / carga rápida USB-PD |

## 2. Notas Físicas de Laboratorio (Placa Cara A Separada)
- **Estado de la muestra:** Upper Logic Board `820-01523-A` con sándwich separado (Cara A individual) para inspección de SoC Apple A13 Bionic (`APL1W85`), PMIC `STB601A0 (U2700)` y huella BGA del interposer inferior.
- **Criterio de Falla:**
  - Lectura `< 50 mV` en líneas de alimentación o datos (excepto `GND`): **CORTO O FUGA SEVERA**.
  - Lectura `OL` (Open Loop) en líneas con valor nominal especificado: **PISTA ABIERTA / PAD FISURADO EN INTERPOSER**.
