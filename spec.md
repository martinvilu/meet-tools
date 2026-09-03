# Documento de Especificación Técnica: Sistema de Control Externo para Google Meet

**Versión:** 1.1

**Objetivo:** Permitir el control y monitoreo bidireccional de sesiones activas de Google Meet desde aplicaciones externas (inicialmente una app Android y posteriormente hardware embebido con conectividad Wi-Fi) mediante una extensión de navegador WebExtensions y un daemon concentrador local/LAN.

## 1\. Arquitectura General del Sistema

El sistema implementa una arquitectura desacoplada centrada en red local (LAN/Loopback), permitiendo que dispositivos móviles y hardware embebido interactúen con la sesión de Meet sin requerir cables directos hacia la PC host.

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
│ (Servicio host en PC: Python / Go / Node.js) │
│  - Descubrimiento / Conexión LAN             │
│  - Enrutamiento y control de concurrencia    │
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

### Componentes:

1.  **Clientes Externos (Red Local):**
    
    *   **Fase 1 (App Android):** Interfaz táctil que envía comandos de moderación/medios y renderiza en tiempo real el estado de la llamada.
        
    *   **Fase 2 (Hardware Wi-Fi):** Microcontroladores (ej. ESP32, Raspberry Pi Pico W) con botones físicos y actuadores (LEDs/pantallas) conectados a la misma LAN.
        
2.  **Daemon Local / Servidor Concentrador:**
    
    *   Servidor WebSocket que enlaza en `0.0.0.0:8765` para aceptar simultáneamente la conexión de la extensión web (vía loopback `127.0.0.1`) y de los clientes externos vía LAN.
        
    *   Aplica la política de control de concurrencia de pestañas de Meet.
        
    *   Reenvía bidireccionalmente los comandos y la telemetría.
        
3.  **Extensión Web (Content Script & Overlay UI):**
    
    *   Se ejecuta en el contexto de `https://meet.google.com/*`.
        
    *   Monitorea e interactúa con el DOM.
        
    *   Inyecta notificaciones flotantes (toasts/overlays) dentro de la interfaz de Meet ante fallos de permisos o rechazos de comandos.
        

## 2\. Protocolo de Comunicación (JSON over WebSocket)

La comunicación se formaliza mediante paquetes JSON con la siguiente estructura base:

```
{
  "version": "1.1",
  "source": "client" | "daemon" | "extension",
  "type": "command" | "state_update" | "event" | "ack" | "error",
  "action": "string",
  "payload": {}
}
```

### 2.1. Comandos Entrantes (Cliente → Daemon → Extensión)

| 
`action`

 | 

Payload

 | 

Descripción

 |
| --- | --- | --- |
| 

`TOGGLE_MIC`

 | 

`{}`

 | 

Conmuta el estado del micrófono propio.

 |
| 

`TOGGLE_CAM`

 | 

`{}`

 | 

Conmuta el estado de la cámara propia.

 |
| 

`TOGGLE_HAND`

 | 

`{}`

 | 

Conmuta el estado de levantar/bajar la mano.

 |
| 

`ADMIT_ALL`

 | 

`{}`

 | 

Acciona "Admitir a todos" en la sala de espera.

 |
| 

`MUTE_ALL`

 | 

`{}`

 | 

Despliega panel y acciona "Silenciar a todos".

 |
| 

`LEAVE_CALL`

 | 

`{"endForAll": boolean}`

 | 

Abandona la reunión o la finaliza para todos.

 |
| 

`GET_STATE`

 | 

`{}`

 | 

Solicita volcado inmediato del estado de la sala.

 |

### 2.2. Eventos y Notificaciones (Extensión → Daemon → Cliente)

| 
`action`

 | 

Payload

 | 

Descripción

 |
| --- | --- | --- |
| 

`STATE_SYNC`

 | 

Ver esquema de estado

 | 

Envío consolidado del estado de controles y sala.

 |
| 

`ADMISSION_REQUESTED`

 | 

`{"count": number}`

 | 

Notifica la presencia de usuarios en sala de espera.

 |
| 

`COMMAND_REJECTED`

 | 

`{"reason": string, "code": string}`

 | 

Notifica fallo o rechazo por concurrencia.

 |
| 

`PERMISSION_DENIED`

 | 

`{"action": string, "detail": string}`

 | 

Notifica que el usuario carece de permisos de host.

 |

**Esquema de Payload en `STATE_SYNC`:**

```
{
  "inCall": true,
  "micMuted": false,
  "cameraOff": true,
  "handRaised": false,
  "participantCount": 18,
  "waitingRoomCount": 3,
  "isHost": true
}
```

## 3\. Política de Concurrencia de Pestañas (Single-Session Lock)

Para garantizar consistencia y evitar que una pulsación física o remota altere una reunión equivocada:

1.  **Detección de Múltiples Sesiones:**
    
    *   Cada pestaña con Meet activo reporta al daemon su estado (`lobby`, `in_call`, `ended`) y un `tabId` único.
        
    *   Si el daemon registra más de una pestaña con estado `in_call: true`:
        
        *   **El daemon entra en estado bloqueado (`LOCKED_AMBIGUOUS_TABS`).**
            
        *   Los comandos entrantes desde la app Android o hardware son **rechazados inmediatamente** con el error `ERR_MULTIPLE_CALLS_ACTIVE`.
            
2.  **Feedback Visual:**
    
    *   El daemon envía a todas las pestañas abiertas de Meet una orden para desplegar una alerta visual indicando:
        
        _"Control externo suspendido: múltiples reuniones activas abiertas."_
        
    *   La app Android / HW recibe un evento de estado con `locked: true` para deshabilitar temporalmente los controles táctiles/físicos hasta que solo quede una pestaña activa.
        

## 4\. Manipulación del DOM, Detección y Manejo de Errores

### 4.1. Localización y Selectores (Español / Inglés)

Los selectores del content script se limitan estrictamente a los idiomas **Español (ES/LATAM)** e **Inglés (US/UK)** utilizando expresiones regulares sobre `aria-label` y validación de atributos semánticos:

*   **Micrófono:** `button[data-is-muted][aria-label*="micrófono" i], button[data-is-muted][aria-label*="microphone" i]`
    
*   **Cámara:** `button[aria-label*="cámara" i], button[aria-label*="camera" i]`
    
*   **Mano:** `button[aria-label*="mano" i], button[aria-label*="hand" i]`
    
*   **Admitir a todos:** `button[aria-label*="Admitir a todos" i], button[aria-label*="Admit all" i]`
    
*   **Abrir panel de personas:** `button[aria-label*="Personas" i], button[aria-label*="People" i]`
    
*   **Silenciar a todos:** `button[aria-label*="Silenciar a todos" i], button[aria-label*="Mute all" i]`
    
*   **Botón confirmación silenciar:** `button[data-mdc-dialog-action="accept"], button[aria-label*="Silenciar" i], button[aria-label*="Mute" i]`
    

### 4.2. Inyección de Alertas Visuales en la Sesión (UI Overlay)

Cuando se solicita una acción que requiere permisos de anfitrión/coanfitrión (ej. `MUTE_ALL` o `ADMIT_ALL`) y el usuario no cuenta con ellos, la extensión no se limitará a fallar silenciosamente:

1.  **Detección de Ausencia de Permisos:**
    
    Al intentar accionar el botón de moderación, el script evalúa si el elemento existe en el DOM tras abrir el panel correspondiente. Si tras un timeout prudencial (ej. 300 ms) el botón no está presente, se determina falta de privilegios.
    
2.  **Inyección en el DOM de Meet:**
    
    El content script crea un banner/toast flotante inyectado en la capa superior (`z-index: 10000`) de la ventana de Meet:
    
    ```
    <div class="meet-bridge-alert">
      <span class="icon">⚠️</span>
      <span class="msg">Control Externo: No tienes permisos de anfitrión para ejecutar esta acción.</span>
    </div>
    ```
    
    *   El banner posee autocierre a los 4 segundos y estilos compatibles con el tema de Meet.
        
3.  **Notificación al Cliente:**
    
    Simultáneamente, la extensión emite un evento `PERMISSION_DENIED` al daemon, permitiendo que la app Android muestre un mensaje equivalente (_Snackbar/Toast_) y que el hardware emita el patrón de fallo configurado.
    

## 5\. Decisiones de Implementación Consolidadas

| 
ID

 | 

Área

 | 

Decisión Adoptada

 |
| --- | --- | --- |
| 

**5.1**

 | 

**Canal de Transporte**

 | 

**WebSocket local y de red.** Se descarta Native Messaging en favor de un servidor WebSocket accesible en LAN (`0.0.0.0:8765`), facilitando la conexión tanto de la extensión como de clientes en red.

 |
| 

**5.2**

 | 

**Plataforma de Clientes**

 | 

**Enfoque en dos fases:**

  

1\. Aplicación móvil Android conectada por Wi-Fi mediante WebSocket.

  

2\. Hardware embebido dedicado (ESP32 / RP2040W) con pulsadores físicos y Wi-Fi nativo.

 |
| 

**5.3**

 | 

**Concurrencia de Pestañas**

 | 

**Rechazo por ambigüedad.** Si se detectan dos o más llamadas simultáneas en el navegador, el sistema bloquea la recepción de comandos y notifica el conflicto visualmente.

 |
| 

**5.4**

 | 

**Soporte de Idiomas**

 | 

**Español e Inglés exclusivamente.** Los motores de búsqueda ARIA y expresiones de filtrado se configuran únicamente para estos dos idiomas.

 |
| 

**5.5**

 | 

**Feedback Físico**

 | 

**Delegado a la capa de cliente.** La extensión provee la telemetría cruda en `STATE_SYNC`; el mapeo de colores, LEDs o vibración queda bajo control exclusivo del firmware o de la app Android.

 |
| 

**5.6**

 | 

**Manejo de Permisos**

 | 

**Alerta visual inyectada en Meet.** Si falla una acción de moderación por falta de privilegios de host, se inyecta un banner de advertencia en el DOM de la reunión y se emite `PERMISSION_DENIED` al cliente.

 |

## 6\. Próximos Pasos Técnicos

1.  **Desarrollo del Content Script de la Extensión:** Implementación de la máquina de estados, el WebSocket client, los selectores ES/EN y el inyector del banner de advertencia.
    
2.  **Desarrollo del Daemon Concentrador:** Implementación en Python o Go con soporte para WebSocket server multicliente y lógica de bloqueo por múltiples pestañas.
    
3.  **Prototipo de la App Android:** Aplicación cliente básica con Jetpack Compose / Flutter para probar latencia y envío de comandos sobre Wi-Fi.


