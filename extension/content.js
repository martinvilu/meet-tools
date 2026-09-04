/**
 * Google Meet External Bridge - Content Script
 * Versión 1.1 - Protocolo JSON over WebSocket
 */

(function () {
  "use strict";

  let daemonHost = "127.0.0.1";
  let daemonPort = 8765;
  let daemonPin = "";
  const RECONNECT_INTERVAL_MS = 3000;
  const STATE_CHECK_INTERVAL_MS = 800;
  const PERMISSION_TIMEOUT_MS = 300;

  // Generar o recuperar identificador único y persistente para esta pestaña
  let tabId = sessionStorage.getItem("meet_bridge_tab_id");
  if (!tabId) {
    tabId = "tab_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
    sessionStorage.setItem("meet_bridge_tab_id", tabId);
  }

  let ws = null;
  let isConnected = false;
  let previousStateJson = "";
  let lockBannerElement = null;

  // Selectores DOM estrictamente en Español e Inglés (ES / EN)
  const SELECTORS = {
    mic: [
      'button[data-is-muted][aria-label*="micrófono" i]',
      'button[data-is-muted][aria-label*="microphone" i]',
      'button[aria-label*="micrófono" i]',
      'button[aria-label*="microphone" i]'
    ],
    cam: [
      'button[aria-label*="cámara" i]',
      'button[aria-label*="camera" i]'
    ],
    hand: [
      'button[aria-label*="mano" i]',
      'button[aria-label*="hand" i]'
    ],
    admitAll: [
      'button[aria-label*="Admitir a todos" i]',
      'button[aria-label*="Admit all" i]'
    ],
    peoplePanel: [
      'button[aria-label*="Personas" i]',
      'button[aria-label*="People" i]'
    ],
    muteAll: [
      'button[aria-label*="Silenciar a todos" i]',
      'button[aria-label*="Mute all" i]'
    ],
    muteConfirm: [
      'button[data-mdc-dialog-action="accept"]',
      'button[aria-label*="Silenciar" i]',
      'button[aria-label*="Mute" i]'
    ],
    leaveCall: [
      'button[aria-label*="Salir de la llamada" i]',
      'button[aria-label*="Leave call" i]'
    ]
  };

  function findElement(selectorArray) {
    for (const sel of selectorArray) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  // ---------------------------------------------------------------------------
  // Extracción de Telemetría y Estado de la Reunión
  // ---------------------------------------------------------------------------

  function isInCall() {
    // Si existe botón de colgar o control de micrófono, estamos dentro de la llamada
    const leaveBtn = findElement(SELECTORS.leaveCall);
    const micBtn = findElement(SELECTORS.mic);
    return Boolean(leaveBtn || micBtn);
  }

  function isMicMuted() {
    const btn = findElement(SELECTORS.mic);
    if (!btn) return false;
    const isMutedAttr = btn.getAttribute("data-is-muted");
    if (isMutedAttr !== null) return isMutedAttr === "true";
    const label = (btn.getAttribute("aria-label") || "").toLowerCase();
    return label.includes("activar") || label.includes("turn on");
  }

  function isCameraOff() {
    const btn = findElement(SELECTORS.cam);
    if (!btn) return true;
    const isMutedAttr = btn.getAttribute("data-is-muted");
    if (isMutedAttr !== null) return isMutedAttr === "true";
    const label = (btn.getAttribute("aria-label") || "").toLowerCase();
    return label.includes("activar") || label.includes("turn on");
  }

  function isHandRaised() {
    const btn = findElement(SELECTORS.hand);
    if (!btn) return false;
    const pressed = btn.getAttribute("aria-pressed");
    if (pressed !== null) return pressed === "true";
    const label = (btn.getAttribute("aria-label") || "").toLowerCase();
    return label.includes("bajar") || label.includes("lower");
  }

  function getParticipantCount() {
    const peopleBtn = findElement(SELECTORS.peoplePanel);
    if (peopleBtn) {
      const badge = peopleBtn.parentElement?.querySelector('[aria-hidden="true"], [class*="badge"], span');
      if (badge && /^\d+$/.test(badge.textContent.trim())) {
        return parseInt(badge.textContent.trim(), 10);
      }
      const label = peopleBtn.getAttribute("aria-label") || "";
      const match = label.match(/\d+/);
      if (match) return parseInt(match[0], 10);
    }
    return 1;
  }

  function getWaitingRoomCount() {
    const admitBtn = findElement(SELECTORS.admitAll);
    if (admitBtn) {
      const label = admitBtn.getAttribute("aria-label") || "";
      const match = label.match(/\d+/);
      return match ? parseInt(match[0], 10) : 1;
    }
    return 0;
  }

  function isHost() {
    // Si existen controles de anfitrión o botón de silenciar a todos
    const hostControls = document.querySelector('button[aria-label*="anfitrión" i], button[aria-label*="host" i]');
    const muteAllBtn = findElement(SELECTORS.muteAll);
    const admitBtn = findElement(SELECTORS.admitAll);
    return Boolean(hostControls || muteAllBtn || admitBtn);
  }

  function captureCurrentState() {
    return {
      inCall: isInCall(),
      micMuted: isMicMuted(),
      cameraOff: isCameraOff(),
      handRaised: isHandRaised(),
      participantCount: getParticipantCount(),
      waitingRoomCount: getWaitingRoomCount(),
      isHost: isHost(),
      tabId: tabId
    };
  }

  // ---------------------------------------------------------------------------
  // Inyección de Alertas Visuales en el DOM (UI Overlay)
  // ---------------------------------------------------------------------------

  function getOrCreateAlertContainer() {
    let container = document.getElementById("meet-bridge-alert-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "meet-bridge-alert-container";
      container.className = "meet-bridge-alert-container";
      document.body.appendChild(container);
    }
    return container;
  }

  function showOverlayAlert(message, level = "warning", autoDismissSeconds = 4) {
    const container = getOrCreateAlertContainer();
    const alert = document.createElement("div");
    alert.className = `meet-bridge-alert ${level}`;

    const icon = document.createElement("span");
    icon.className = "icon";
    icon.textContent = level === "error" || level === "locked" ? "🚫" : "⚠️";

    const msg = document.createElement("span");
    msg.className = "msg";
    msg.textContent = message;

    alert.appendChild(icon);
    alert.appendChild(msg);
    container.appendChild(alert);

    if (autoDismissSeconds > 0) {
      setTimeout(() => {
        alert.classList.add("meet-bridge-fadeout");
        setTimeout(() => alert.remove(), 300);
      }, autoDismissSeconds * 1000);
    }

    return alert;
  }

  function showLockBanner(message) {
    if (lockBannerElement) return;
    lockBannerElement = showOverlayAlert(message, "locked", 0);
  }

  function dismissLockBanner() {
    if (lockBannerElement) {
      lockBannerElement.classList.add("meet-bridge-fadeout");
      setTimeout(() => {
        if (lockBannerElement) {
          lockBannerElement.remove();
          lockBannerElement = null;
        }
      }, 300);
    }
  }

  let configPillElement = null;

  function renderConfigPill(connected = false, label = "Configurar PIN") {
    if (!document.body) return;
    if (!configPillElement) {
      configPillElement = document.createElement("div");
      configPillElement.id = "meet-bridge-config-pill";
      configPillElement.className = "meet-bridge-config-pill";
      configPillElement.title = "Hacé click para cambiar o configurar el PIN de Meet Bridge";
      configPillElement.onclick = showMeetPinModal;

      const icon = document.createElement("span");
      icon.className = "pill-icon";
      icon.textContent = "🎙️";

      const dot = document.createElement("span");
      dot.className = "pill-dot" + (connected ? " connected" : "");
      dot.id = "meet-bridge-pill-dot";

      const text = document.createElement("span");
      text.id = "meet-bridge-pill-text";
      text.textContent = `Meet Bridge: ${label}`;

      configPillElement.appendChild(icon);
      configPillElement.appendChild(dot);
      configPillElement.appendChild(text);
      document.body.appendChild(configPillElement);
    } else {
      const dot = document.getElementById("meet-bridge-pill-dot");
      if (dot) dot.className = "pill-dot" + (connected ? " connected" : "");
      const text = document.getElementById("meet-bridge-pill-text");
      if (text) text.textContent = `Meet Bridge: ${label}`;
    }
  }

  function showMeetPinModal() {
    let backdrop = document.getElementById("meet-bridge-pin-modal");
    if (backdrop) return;

    backdrop = document.createElement("div");
    backdrop.id = "meet-bridge-pin-modal";
    backdrop.className = "meet-bridge-modal-backdrop";

    const modal = document.createElement("div");
    modal.className = "meet-bridge-modal";

    const h3 = document.createElement("h3");
    h3.textContent = "Meet Bridge - Configurar PIN";

    const p = document.createElement("p");
    p.textContent = "Ingresá el PIN mostrado en la consola del daemon para habilitar el control externo de Google Meet.";

    const form = document.createElement("div");
    form.className = "meet-bridge-pin-form";

    const row = document.createElement("div");
    row.className = "meet-bridge-pin-input-row";

    const pinInput = document.createElement("input");
    pinInput.type = "text";
    pinInput.className = "meet-bridge-pin-input";
    pinInput.placeholder = "Ej: 1234";
    pinInput.maxLength = 12;
    pinInput.value = daemonPin || "";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "meet-bridge-save-pin-btn";
    saveBtn.textContent = "Guardar PIN";

    const statusMsg = document.createElement("div");
    statusMsg.className = "meet-bridge-pin-status";

    saveBtn.onclick = () => {
      const val = pinInput.value.trim();
      if (!val) {
        statusMsg.textContent = "El PIN no puede estar vacío";
        statusMsg.className = "meet-bridge-pin-status error";
        pinInput.focus();
        return;
      }

      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
        chrome.storage.sync.set({ daemonPin: val }, () => {
          daemonPin = val;
          statusMsg.textContent = "PIN guardado. Reconectando...";
          statusMsg.className = "meet-bridge-pin-status success";
          renderConfigPill(false, "Reconectando...");

          if (ws) {
            ws.close();
          } else {
            connectToDaemon();
          }

          setTimeout(() => {
            if (backdrop) backdrop.remove();
          }, 800);
        });
      } else {
        daemonPin = val;
        statusMsg.textContent = "PIN actualizado.";
        statusMsg.className = "meet-bridge-pin-status success";
        if (ws) ws.close(); else connectToDaemon();
        setTimeout(() => {
          if (backdrop) backdrop.remove();
        }, 800);
      }
    };

    row.appendChild(pinInput);
    row.appendChild(saveBtn);
    form.appendChild(row);
    form.appendChild(statusMsg);

    const closeBtn = document.createElement("button");
    closeBtn.className = "meet-bridge-close-btn";
    closeBtn.textContent = "Cerrar";
    closeBtn.onclick = () => backdrop.remove();

    modal.appendChild(h3);
    modal.appendChild(p);
    modal.appendChild(form);
    modal.appendChild(closeBtn);
    backdrop.appendChild(modal);

    document.body.appendChild(backdrop);
    pinInput.focus();
  }

  // ---------------------------------------------------------------------------
  // Acciones y Manejadores de Comandos
  // ---------------------------------------------------------------------------

  function triggerClick(element) {
    if (!element) return false;
    element.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    return true;
  }

  async function executeToggleMic() {
    const btn = findElement(SELECTORS.mic);
    if (btn && triggerClick(btn)) {
      await new Promise((r) => setTimeout(r, 150));
      return { status: "ok", micMuted: isMicMuted() };
    }
    throw new Error("Botón de micrófono no encontrado en el DOM");
  }

  async function executeToggleCam() {
    const btn = findElement(SELECTORS.cam);
    if (btn && triggerClick(btn)) {
      await new Promise((r) => setTimeout(r, 150));
      return { status: "ok", cameraOff: isCameraOff() };
    }
    throw new Error("Botón de cámara no encontrado en el DOM");
  }

  async function executeToggleHand() {
    const btn = findElement(SELECTORS.hand);
    if (btn && triggerClick(btn)) {
      await new Promise((r) => setTimeout(r, 150));
      return { status: "ok", handRaised: isHandRaised() };
    }
    throw new Error("Botón de levantar la mano no encontrado en el DOM");
  }

  async function executeMuteAll() {
    let muteAllBtn = findElement(SELECTORS.muteAll);

    // Si el botón no está visible, abrir panel de personas
    if (!muteAllBtn) {
      const peopleBtn = findElement(SELECTORS.peoplePanel);
      if (peopleBtn) {
        triggerClick(peopleBtn);
      }
      // Timeout prudencial de 300ms según especificación 4.2
      await new Promise((r) => setTimeout(r, PERMISSION_TIMEOUT_MS));
      muteAllBtn = findElement(SELECTORS.muteAll);
    }

    if (!muteAllBtn) {
      // Falta de privilegios de anfitrión
      showOverlayAlert("Control Externo: No tienes permisos de anfitrión para ejecutar esta acción.", "warning", 4);
      emitPermissionDenied("MUTE_ALL", "El botón 'Silenciar a todos' no está disponible en la interfaz.");
      throw new Error("Falta de privilegios de anfitrión");
    }

    triggerClick(muteAllBtn);

    // Confirmación en el modal
    await new Promise((r) => setTimeout(r, 200));
    const confirmBtn = findElement(SELECTORS.muteConfirm);
    if (confirmBtn) {
      triggerClick(confirmBtn);
    }

    return { status: "ok" };
  }

  async function executeAdmitAll() {
    let admitBtn = findElement(SELECTORS.admitAll);

    if (!admitBtn) {
      const peopleBtn = findElement(SELECTORS.peoplePanel);
      if (peopleBtn) {
        triggerClick(peopleBtn);
      }
      await new Promise((r) => setTimeout(r, PERMISSION_TIMEOUT_MS));
      admitBtn = findElement(SELECTORS.admitAll);
    }

    if (!admitBtn) {
      showOverlayAlert("Control Externo: No tienes permisos de anfitrión para admitir usuarios.", "warning", 4);
      emitPermissionDenied("ADMIT_ALL", "El botón 'Admitir a todos' no está disponible.");
      throw new Error("Falta de privilegios de anfitrión");
    }

    triggerClick(admitBtn);
    return { status: "ok" };
  }

  async function executeLeaveCall(endForAll = false) {
    const leaveBtn = findElement(SELECTORS.leaveCall);
    if (leaveBtn && triggerClick(leaveBtn)) {
      if (endForAll) {
        await new Promise((r) => setTimeout(r, 200));
        const endForAllBtn = document.querySelector('button[aria-label*="todos" i], button[aria-label*="everyone" i]');
        if (endForAllBtn) {
          triggerClick(endForAllBtn);
        }
      }
      return { status: "ok", left: true };
    }
    throw new Error("Botón de salir no encontrado");
  }

  // ---------------------------------------------------------------------------
  // Conexión WebSocket con Daemon Local
  // ---------------------------------------------------------------------------

  function emitPermissionDenied(action, detail) {
    if (!ws || !isConnected) return;
    const msg = {
      version: "1.1",
      source: "extension",
      type: "event",
      action: "PERMISSION_DENIED",
      payload: { action, detail }
    };
    ws.send(JSON.stringify(msg));
  }

  function emitStateSync(force = false) {
    if (!ws || !isConnected) return;
    const current = captureCurrentState();
    const currentJson = JSON.stringify(current);
    if (!force && currentJson === previousStateJson) {
      return;
    }
    previousStateJson = currentJson;

    const msg = {
      version: "1.1",
      source: "extension",
      type: "state_update",
      action: "STATE_SYNC",
      payload: current
    };
    ws.send(JSON.stringify(msg));
  }

  function handleDaemonMessage(raw) {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      console.warn("[MeetBridge] Error parseando mensaje del daemon:", e);
      return;
    }

    if (msg.type === "error" && (msg.payload?.code === "ERR_INVALID_PIN" || msg.payload?.code === "ERR_PAIRING_REQUIRED")) {
      showOverlayAlert("Meet Bridge: PIN incorrecto o no emparejado. Hacé click abajo para ingresar el PIN.", "error", 6);
      renderConfigPill(false, "PIN inválido");
      if (ws) ws.close();
      return;
    }

    if (msg.action === "SHOW_ALERT") {
      const alertMsg = msg.payload?.message || "Control externo suspendido: múltiples reuniones activas abiertas.";
      showLockBanner(alertMsg);
      return;
    }

    if (msg.action === "DISMISS_ALERT") {
      dismissLockBanner();
      return;
    }

    if (msg.type === "command") {
      const reqId = msg.payload?.requestId;
      const act = msg.action;

      let promise;
      switch (act) {
        case "TOGGLE_MIC":
          promise = executeToggleMic();
          break;
        case "TOGGLE_CAM":
          promise = executeToggleCam();
          break;
        case "TOGGLE_HAND":
          promise = executeToggleHand();
          break;
        case "MUTE_ALL":
          promise = executeMuteAll();
          break;
        case "ADMIT_ALL":
          promise = executeAdmitAll();
          break;
        case "LEAVE_CALL":
          promise = executeLeaveCall(Boolean(msg.payload?.endForAll));
          break;
        case "GET_STATE":
          emitStateSync(true);
          return;
        default:
          promise = Promise.reject(new Error(`Comando desconocido: ${act}`));
      }

      promise
        .then((result) => {
          if (ws && isConnected) {
            ws.send(JSON.stringify({
              version: "1.1",
              source: "extension",
              type: "ack",
              action: act,
              payload: Object.assign({ requestId: reqId }, result)
            }));
            emitStateSync(true);
          }
        })
        .catch((err) => {
          if (ws && isConnected) {
            ws.send(JSON.stringify({
              version: "1.1",
              source: "extension",
              type: "error",
              action: "COMMAND_REJECTED",
              payload: {
                requestId: reqId,
                reason: err.message || "Fallo en ejecución",
                code: err.message.includes("anfitrión") ? "ERR_PERMISSION_DENIED" : "ERR_EXECUTION_FAILED"
              }
            }));
          }
        });
    }
  }

  function connectToDaemon() {
    if (!daemonPin) {
      isConnected = false;
      console.log("[MeetBridge] Conexión en espera: PIN no configurado.");
      renderConfigPill(false, "Configurar PIN");
      return;
    }

    const wsUrl = `ws://${daemonHost}:${daemonPort}`;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      renderConfigPill(false, "Desconectado");
      setTimeout(connectToDaemon, RECONNECT_INTERVAL_MS);
      return;
    }

    ws.onopen = function () {
      isConnected = true;
      console.log("[MeetBridge] Conectado al daemon en", wsUrl);
      renderConfigPill(true, "Conectado");

      // Registrar pestaña
      const regMsg = {
        version: "1.1",
        source: "extension",
        type: "event",
        action: "TAB_REGISTER",
        payload: {
          tabId: tabId,
          tabState: isInCall() ? "in_call" : "lobby",
          url: window.location.href,
          pin: daemonPin
        }
      };
      ws.send(JSON.stringify(regMsg));
      emitStateSync(true);
    };

    ws.onmessage = function (event) {
      handleDaemonMessage(event.data);
    };

    ws.onclose = function () {
      isConnected = false;
      ws = null;
      renderConfigPill(false, daemonPin ? "Desconectado" : "Configurar PIN");
      if (daemonPin) {
        setTimeout(connectToDaemon, RECONNECT_INTERVAL_MS);
      }
    };

    ws.onerror = function () {
      if (ws) ws.close();
    };
  }

  function loadConfigAndConnect() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.get(["daemonHost", "daemonPort", "daemonPin"], (res) => {
        if (chrome.runtime.lastError || !res) {
          connectToDaemon();
          return;
        }
        if (res.daemonHost) daemonHost = res.daemonHost.trim();
        if (res.daemonPort) daemonPort = parseInt(res.daemonPort, 10);
        if (res.daemonPin !== undefined) daemonPin = String(res.daemonPin).trim();
        connectToDaemon();
      });
    } else {
      connectToDaemon();
    }
  }

  // Escucha de mensajes desde el popup de configuración
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg.type === "GET_STATUS") {
        sendResponse({
          isConnected: isConnected,
          host: daemonHost,
          port: daemonPort,
          pin: daemonPin,
          tabId: tabId,
          inCall: isInCall()
        });
        return true;
      }
      if (msg.type === "CONFIG_UPDATED") {
        daemonHost = msg.host || daemonHost;
        daemonPort = parseInt(msg.port, 10) || daemonPort;
        daemonPin = msg.pin !== undefined ? String(msg.pin).trim() : daemonPin;
        console.log("[MeetBridge] Nueva configuración recibida. Reconectando a", daemonHost, daemonPort);
        renderConfigPill(false, daemonPin ? "Reconectando..." : "Configurar PIN");
        if (ws) {
          ws.close();
        } else {
          connectToDaemon();
        }
        sendResponse({ status: "ok" });
        return true;
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Inicialización y Observadores del DOM
  // ---------------------------------------------------------------------------

  if (document.body) {
    renderConfigPill(false, "Configurar PIN");
  } else {
    window.addEventListener("DOMContentLoaded", () => {
      renderConfigPill(false, "Configurar PIN");
    });
  }

  loadConfigAndConnect();

  // Polling periódico de estado
  setInterval(() => {
    emitStateSync();
  }, STATE_CHECK_INTERVAL_MS);

  // MutationObserver para reaccionar a cambios inmediatos en controles
  const observer = new MutationObserver(() => {
    emitStateSync();
  });
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["data-is-muted", "aria-label", "aria-pressed"]
  });

  console.log("[MeetBridge] Content script inicializado para pestaña", tabId);
})();
