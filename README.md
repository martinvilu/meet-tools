# meet-tools

Sistema de control y monitoreo bidireccional para Google Meet desde dispositivos externos (apps móviles Android y hardware embebido Wi-Fi) mediante una extensión de navegador WebExtensions y un daemon concentrador local/LAN.

Basado en la especificación técnica [spec.md](spec.md) (Versión 1.1).

---

## 🏛️ Arquitectura General

```
┌──────────────────────────────────────────────┐
│ Dispositivo Externo (App Android / MCU Wi-Fi)│
│  - Primera fase: App Android                 │
│  - Segunda fase: ESP32 / RP2040W (Wi-Fi)     │
└──────────────────────┬───────────────────────┘
                       │
                       │ WebSocket / TCP (LAN: ws://<HOST_IP>:8765)
                       ▼
┌──────────────────────────────────────────────┐
│                 Daemon Local                 │
│  - Enrutamiento bidireccional LAN            │
│  - Control de concurrencia de pestañas       │
└──────────────────────┬───────────────────────┘
                       │
                       │ WebSocket Local (ws://127.0.0.1:8765)
                       ▼
┌──────────────────────────────────────────────┐
│           Extensión WebExtensions            │
│ (Firefox / Chromium - meet.google.com)       │
│  ├─ Content Script: Inspección/Control DOM   │
│  └─ UI Overlay: Inyección de alertas locales │
└──────────────────────────────────────────────┘
```

---

## 📦 Componentes del Repositorio

1. **`meet_tools.daemon`**:
   - Servidor WebSocket multicliente enlazado en `0.0.0.0:8765` para atender en simultáneo a la extensión local (`127.0.0.1`) y clientes en la red local.
   - Aplica la política **Single-Session Lock**: si detecta dos o más reuniones de Meet activas simultáneas en el navegador, entra en estado `LOCKED_AMBIGUOUS_TABS`, suspende la ejecución de comandos con el error `ERR_MULTIPLE_CALLS_ACTIVE` y envía la orden a las pestañas de desplegar una alerta visual.
   - Al quedar solo una llamada activa, se restablece el control automáticamente.

2. **`extension/` (WebExtensions MV3)**:
   - Compatible con Google Chrome, Chromium, Brave, Edge y Firefox.
   - Content script que inspecciona el DOM de `meet.google.com` con soporte estricto para **Español (ES/LATAM)** e **Inglés (US/UK)**.
   - Observador reactivo de mutaciones del DOM (`MutationObserver`) para telemetría en tiempo real de micrófono, cámara, mano levantada, participantes y sala de espera.
   - Inyector de alertas flotantes en el DOM (`overlay.css` y `content.js`):
     - Advertencia ante falta de permisos de anfitrión (`MUTE_ALL` / `ADMIT_ALL` con timeout de 300 ms).
     - Banner persistente de bloqueo por ambigüedad cuando hay múltiples reuniones abiertas.

3. **`meet_tools.cli` (`meet-tools`)**:
   - Herramienta de línea de comandos para administrar el daemon, consultar el estado en tiempo real, enviar comandos directos, monitorear telemetría continua o simular pestañas para pruebas sin navegador.

---

## 🚀 Instalación y Puesta en Marcha

### Requisitos

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) instalado en el sistema

### 1. Iniciar el Daemon Concentrador

```bash
cd /home/mrtin/dev/tools/meet-tools
uv sync
uv run meet-tools daemon
```

Opciones:
- `--host` / `-h`: IP de enlace (por defecto `0.0.0.0` para permitir acceso desde la LAN).
- `--port` / `-p`: Puerto TCP (por defecto `8765`).

### 2. Cargar la Extensión en el Navegador

#### Chromium / Google Chrome / Brave / Edge:
1. Abrí `chrome://extensions/`.
2. Activá el **Modo de desarrollador** (esquina superior derecha).
3. Hacé clic en **Cargar descomprimida** (Load unpacked).
4. Seleccioná la carpeta `/home/mrtin/dev/tools/meet-tools/extension`.

#### Firefox:
1. Abrí `about:debugging#/runtime/this-firefox`.
2. Hacé clic en **Cargar complemento temporal** (Load Temporary Add-on).
3. Seleccioná el archivo `/home/mrtin/dev/tools/meet-tools/extension/manifest.json`.

---

## 💻 Uso de la CLI (`meet-tools`)

Una vez iniciado el daemon y abierta una reunión en Google Meet:

```bash
# Ver estado consolidado de la llamada
uv run meet-tools status

# Conmutar controles
uv run meet-tools mic        # Conmuta micrófono (TOGGLE_MIC)
uv run meet-tools cam        # Conmuta cámara (TOGGLE_CAM)
uv run meet-tools hand       # Conmuta mano levantada (TOGGLE_HAND)

# Acciones de moderación (requieren rol de anfitrión)
uv run meet-tools mute-all   # Silenciar a todos los participantes
uv run meet-tools admit-all  # Admitir a todos en la sala de espera

# Abandonar o finalizar reunión
uv run meet-tools leave            # Salir de la reunión
uv run meet-tools leave --all      # Finalizar reunión para todos

# Monitoreo reactivo de eventos en tiempo real
uv run meet-tools monitor

# Simulación de pestaña para pruebas sin navegador
uv run meet-tools mock-tab --in-call --host
```

---

## 🔗 Consumidores e integración con cyberdeck

**Estado real: especificación, no verificado contra un cliente.** El consumidor
declarado, `cyberdeck` (app Android), existe solo como especificación
(`cyberdeck/android-spec.md`, que lo lista contra `meet-tools (ws:8765)`); no hay
cliente implementado ni prueba de integración con este daemon. No se invoca a
ninguna otra herramienta del ecosistema desde aquí.

Lo que este repo sí garantiza (fijado en `tests/test_contrato_cyberdeck.py`):

- Puerto por defecto del daemon: `8765`.
- Servicio mDNS publicado: `_meet-bridge._tcp.local.` (propiedad `service=meet`). La spec
  de cyberdeck describe `_meet-bridge._sub._bridge-remote._tcp.local.`: **esa forma con
  subtipo no está implementada**; un cliente debe descubrir por el tipo plano.
- URI de emparejamiento `bridge://pair?v=1.3&host=…&port=8765&service=meet&pin=…&name=…`.
- Salida `--json` versionada (`schema_version`) en `status` y `monitor` para
  consumidores externos que no hablen WebSocket.

---

## 📡 Protocolo de Comunicación (JSON v1.1)

Todos los mensajes transmitidos sobre WebSocket respetan el siguiente esquema base:

```json
{
  "version": "1.1",
  "source": "client" | "daemon" | "extension",
  "type": "command" | "state_update" | "event" | "ack" | "error",
  "action": "string",
  "payload": {}
}
```

### Esquema de `STATE_SYNC`

```json
{
  "inCall": true,
  "micMuted": false,
  "cameraOff": true,
  "handRaised": false,
  "participantCount": 18,
  "waitingRoomCount": 3,
  "isHost": true,
  "locked": false
}
```

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite completa de pruebas unitarias y de integración asíncronas con `pytest-asyncio`:

```bash
uv run pytest -v
```

---

## 📦 Empaquetado para Chrome y Firefox

Para empaquetar la extensión lista para cargar o distribuir:

```bash
uv run meet-tools pack
```

Opciones:
- `--target` / `-t`: `both` (por defecto), `chrome` o `firefox`.
- `--out-dir` / `-o`: Directorio de salida (por defecto `dist/`).

Archivos generados en `dist/`:
- **`meet-bridge-chrome-v1.1.0.zip`**: Manifiesto optimizado para Chromium.
- **`meet-bridge-firefox-v1.1.0.xpi`**: Manifiesto adaptado para Firefox MV3 con `browser_specific_settings.gecko`.
