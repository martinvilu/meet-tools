"""Daemon concentrador WebSocket para control de Google Meet y gestión de concurrencia."""

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, Optional, Set
import websockets
from websockets.asyncio.server import Server, serve

from meet_tools.discovery import (
    MdnsPublisher,
    build_pairing_uri,
    generate_qr_ascii,
    generate_qr_svg,
    get_local_ip,
)
from meet_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    Source,
    StateSyncPayload,
)

logger = logging.getLogger("meet_tools.daemon")


class TabSession:
    """Representa una pestaña de navegador con la extensión Meet conectada."""

    def __init__(self, tab_id: str, websocket: Any):
        self.tab_id = tab_id
        self.websocket = websocket
        self.in_call: bool = False
        self.tab_state: str = "lobby"  # lobby, in_call, ended
        self.latest_state: Optional[StateSyncPayload] = None

    def update_from_state(self, state: StateSyncPayload) -> None:
        self.latest_state = state
        self.in_call = state.inCall
        self.tab_state = "in_call" if state.inCall else "lobby"


class MeetDaemon:
    """Servidor concentrador y enrutador de comandos con bloqueo por ambigüedad de sesiones."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        command_timeout: float = 2.5,
        pin: Optional[str] = None,
        require_pin: bool = False,
        enable_mdns: bool = True,
    ):
        self.host = host
        self.port = port
        self.command_timeout = command_timeout
        self.require_pin = require_pin or bool(pin)
        self.pin = pin or (f"{random.randint(1000, 9999)}" if self.require_pin else None)
        self.enable_mdns = enable_mdns

        self.lan_ip = get_local_ip() if self.host in ("0.0.0.0", "") else self.host
        self.pairing_uri = build_pairing_uri("meet", self.lan_ip, self.port, str(self.pin or ""))
        self.qr_ascii = generate_qr_ascii(self.pairing_uri)
        self.qr_svg = generate_qr_svg(self.pairing_uri)

        self._mdns_publisher: Optional[MdnsPublisher] = None
        if self.enable_mdns and self.port > 0:
            self._mdns_publisher = MdnsPublisher(
                service_name=f"MeetBridge-{self.pin or 'open'}",
                service_type="_meet-bridge._tcp.local.",
                port=self.port,
                properties={
                    "service": "meet",
                    "version": "1.1.0",
                    "requires_pin": "1" if self.require_pin else "0",
                },
                host_ip=self.lan_ip,
            )

        self._server: Optional[Server] = None
        self._tabs: Dict[str, TabSession] = {}
        self._ws_to_tab_id: Dict[Any, str] = {}
        self._clients: Set[Any] = set()
        self._authenticated_sockets: Set[Any] = set()
        self._is_locked: bool = False
        self._pending_commands: Dict[str, asyncio.Future] = {}
        self._cmd_counter: int = 0
        self._failed_pin_attempts: Dict[str, list] = {}
        self._latest_consolidated_state: StateSyncPayload = StateSyncPayload(
            inCall=False,
            locked=False,
            pin=self.pin,
            pairingUri=self.pairing_uri,
            qrSvg=self.qr_svg,
        )

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    @property
    def active_tabs_count(self) -> int:
        return sum(1 for tab in self._tabs.values() if tab.in_call)

    @property
    def active_tab(self) -> Optional[TabSession]:
        active = [tab for tab in self._tabs.values() if tab.in_call]
        if len(active) == 1:
            return active[0]
        return None

    async def start(self) -> None:
        """Inicia el servidor WebSocket concentrador y mDNS."""
        pin_info = f" (PIN: {self.pin})" if self.pin else ""
        logger.info(f"Iniciando MeetDaemon en ws://{self.host}:{self.port}{pin_info}")
        self._server = await serve(self._handle_connection, self.host, self.port)
        if self._mdns_publisher:
            await self._mdns_publisher.start()

    async def stop(self) -> None:
        """Detiene el servidor, mDNS y cierra todas las conexiones activas."""
        logger.info("Deteniendo MeetDaemon...")
        if self._mdns_publisher:
            await self._mdns_publisher.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._tabs.clear()
        self._ws_to_tab_id.clear()
        self._clients.clear()

    async def _handle_connection(self, websocket: Any) -> None:
        """Punto de entrada de nuevas conexiones entrantes."""
        # Por defecto consideramos el socket como cliente inicial y enviamos el estado
        self._clients.add(websocket)
        await self._send_state_to_client(websocket)

        client_type: Optional[Source] = Source.CLIENT
        assigned_tab_id: Optional[str] = None

        try:
            async for raw_message in websocket:
                try:
                    msg = Message.from_json(raw_message)
                except Exception as e:
                    logger.warning(f"Mensaje malformado recibido: {e} - {raw_message[:100]}")
                    err = Message.error(f"Formato JSON inválido: {e}", ErrorCode.ERR_MALFORMED_MESSAGE)
                    await websocket.send(err.to_json())
                    continue

                if msg.source == Source.EXTENSION:
                    if client_type != Source.EXTENSION:
                        client_type = Source.EXTENSION
                        self._clients.discard(websocket)
                        assigned_tab_id = msg.payload.get("tabId") or f"tab_{id(websocket)}"
                        tab = TabSession(assigned_tab_id, websocket)
                        self._tabs[assigned_tab_id] = tab
                        self._ws_to_tab_id[websocket] = assigned_tab_id
                        logger.info(f"Extensión registrada [tabId: {assigned_tab_id}]")
                    await self._process_extension_message(websocket, msg, assigned_tab_id)
                else:
                    await self._process_client_message(websocket, msg)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._authenticated_sockets.discard(websocket)
            if client_type == Source.EXTENSION and assigned_tab_id in self._tabs:
                del self._tabs[assigned_tab_id]
                self._ws_to_tab_id.pop(websocket, None)
                logger.info(f"Extensión desconectada [tabId: {assigned_tab_id}]")
                await self._evaluate_concurrency_lock()
            else:
                self._clients.discard(websocket)

    async def _process_extension_message(self, websocket: Any, msg: Message, tab_id: Optional[str]) -> None:
        """Procesa mensajes emitidos desde las extensiones WebExtensions."""
        tab = self._tabs.get(tab_id) if tab_id else None

        if msg.action == Action.TAB_REGISTER.value:
            if self.require_pin:
                ext_pin = str(msg.payload.get("pin", "")).strip()
                if ext_pin != str(self.pin).strip():
                    logger.warning("Extensión rechazada: PIN inválido.")
                    err = Message.error("PIN de emparejamiento incorrecto para la extensión.", ErrorCode.ERR_INVALID_PIN)
                    await websocket.send(err.to_json())
                    return
                self._authenticated_sockets.add(websocket)

            new_tab_id = msg.payload.get("tabId", tab_id)
            tab_state = msg.payload.get("tabState", "lobby")
            in_call = tab_state == "in_call"
            if tab:
                tab.tab_id = new_tab_id
                tab.tab_state = tab_state
                tab.in_call = in_call
            await self._evaluate_concurrency_lock()
            return

        if self.require_pin and websocket not in self._authenticated_sockets:
            logger.warning("Mensaje de extensión rechazado: socket no autenticado mediante PIN.")
            err = Message.error("Extensión no autenticada mediante PIN.", ErrorCode.ERR_PAIRING_REQUIRED)
            await websocket.send(err.to_json())
            return

        if msg.action == Action.STATE_SYNC.value:
            incoming_payload = dict(msg.payload)
            incoming_payload["pin"] = self.pin
            incoming_payload["pairingUri"] = self.pairing_uri
            incoming_payload["qrSvg"] = self.qr_svg
            state_data = StateSyncPayload(**incoming_payload)
            if tab:
                tab.update_from_state(state_data)
            await self._evaluate_concurrency_lock()
            # Si esta pestaña es la activa y no hay bloqueo, retransmitir a clientes
            if not self._is_locked and tab and tab.in_call:
                self._latest_consolidated_state = state_data
                out_msg = Message.state_sync(state_data, source=Source.DAEMON)
                await self._broadcast_to_clients(out_msg)
            return

        if msg.type in (MessageType.ACK, MessageType.ERROR):
            req_id = msg.payload.get("requestId")
            if req_id and req_id in self._pending_commands:
                fut = self._pending_commands.pop(req_id)
                if not fut.done():
                    fut.set_result(msg)
            return

        if msg.action in (Action.PERMISSION_DENIED.value, Action.ADMISSION_REQUESTED.value):
            if not self._is_locked:
                out_msg = Message(
                    version=msg.version,
                    source=Source.DAEMON,
                    type=msg.type,
                    action=msg.action,
                    payload=msg.payload
                )
                await self._broadcast_to_clients(out_msg)

    async def _process_client_message(self, websocket: Any, msg: Message) -> None:
        """Procesa comandos enviados por clientes externos (Android, CLI, HW)."""
        if msg.action == Action.GET_STATE.value:
            await self._send_state_to_client(websocket)
            return

        if msg.action == Action.PAIR_REQUEST.value:
            remote_addr = getattr(websocket, "remote_address", None)
            client_ip = remote_addr[0] if (remote_addr and isinstance(remote_addr, (list, tuple))) else "127.0.0.1"

            now = time.time()
            attempts = [t for t in self._failed_pin_attempts.get(client_ip, []) if now - t < 60]
            self._failed_pin_attempts[client_ip] = attempts

            if len(attempts) >= 5:
                logger.warning(f"Intento de emparejamiento bloqueado por rate limit para {client_ip}")
                err = Message.error("Demasiados intentos fallidos de PIN. Intente nuevamente más tarde.", ErrorCode.ERR_INVALID_PIN)
                await websocket.send(err.to_json())
                return

            req_pin = str(msg.payload.get("pin", "")).strip()
            if not self.require_pin or req_pin == str(self.pin).strip():
                if client_ip in self._failed_pin_attempts:
                    del self._failed_pin_attempts[client_ip]
                self._authenticated_sockets.add(websocket)
                ack = Message(
                    source=Source.DAEMON,
                    type=MessageType.EVENT,
                    action=Action.PAIRING_SUCCESS.value,
                    payload={"status": "ok"}
                )
                await websocket.send(ack.to_json())
            else:
                self._failed_pin_attempts.setdefault(client_ip, []).append(now)
                await asyncio.sleep(1.0)
                err = Message.error("PIN de emparejamiento incorrecto.", ErrorCode.ERR_INVALID_PIN)
                await websocket.send(err.to_json())
            return

        if msg.type == MessageType.COMMAND:
            if self.require_pin and websocket not in self._authenticated_sockets:
                err = Message.error("Emparejamiento requerido mediante PIN.", ErrorCode.ERR_PAIRING_REQUIRED)
                await websocket.send(err.to_json())
                return

            # 1. Verificar bloqueo por múltiples llamadas
            if self._is_locked:
                err = Message.error(
                    "Control externo suspendido: múltiples reuniones activas abiertas.",
                    ErrorCode.ERR_MULTIPLE_CALLS_ACTIVE,
                    action=Action.COMMAND_REJECTED.value,
                    source=Source.DAEMON
                )
                await websocket.send(err.to_json())
                return

            # 2. Verificar existencia de pestaña activa
            active_tab = self.active_tab
            if not active_tab or not active_tab.in_call:
                err = Message.error(
                    "No hay ninguna reunión activa de Google Meet.",
                    ErrorCode.ERR_NO_ACTIVE_CALL,
                    action=Action.COMMAND_REJECTED.value,
                    source=Source.DAEMON
                )
                await websocket.send(err.to_json())
                return

            # 3. Enrutar comando hacia la extensión activa
            self._cmd_counter += 1
            req_id = f"cmd_{self._cmd_counter}"
            payload = dict(msg.payload)
            payload["requestId"] = req_id

            fwd_msg = Message.command(msg.action, payload, source=Source.DAEMON)
            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            self._pending_commands[req_id] = fut

            try:
                await active_tab.websocket.send(fwd_msg.to_json())
                resp = await asyncio.wait_for(fut, timeout=self.command_timeout)
                resp_to_client = Message(
                    version=resp.version,
                    source=Source.DAEMON,
                    type=resp.type,
                    action=resp.action,
                    payload=resp.payload
                )
                await websocket.send(resp_to_client.to_json())
            except asyncio.TimeoutError:
                self._pending_commands.pop(req_id, None)
                ack = Message.ack(msg.action, {"status": "dispatched", "note": "timeout_waiting_extension_ack"})
                await websocket.send(ack.to_json())
            except Exception as e:
                self._pending_commands.pop(req_id, None)
                err = Message.error(f"Fallo al comunicar con la extensión: {e}", ErrorCode.ERR_EXTENSION_DISCONNECTED)
                await websocket.send(err.to_json())

    async def _evaluate_concurrency_lock(self) -> None:
        """Aplica la política Single-Session Lock evaluando las pestañas con in_call=True."""
        active_count = self.active_tabs_count

        if active_count > 1 and not self._is_locked:
            self._is_locked = True
            logger.warning(f"LOCKED_AMBIGUOUS_TABS activado ({active_count} reuniones activas simultáneas).")

            alert_msg = Message.event(
                Action.SHOW_ALERT,
                {"message": "Control externo suspendido: múltiples reuniones activas abiertas.", "level": "warning"},
                source=Source.DAEMON
            )
            await self._broadcast_to_tabs(alert_msg)

            self._latest_consolidated_state.locked = True
            lock_msg = Message.event(
                Action.LOCKED_STATE,
                {"locked": True, "reason": "Control externo suspendido: múltiples reuniones activas abiertas."},
                source=Source.DAEMON
            )
            await self._broadcast_to_clients(lock_msg)

        elif active_count <= 1 and self._is_locked:
            self._is_locked = False
            logger.info("LOCKED_AMBIGUOUS_TABS levantado. Reanudando control normal.")

            dismiss_msg = Message.event(Action.DISMISS_ALERT, {}, source=Source.DAEMON)
            await self._broadcast_to_tabs(dismiss_msg)

            if active_count == 1:
                tab = self.active_tab
                if tab and tab.latest_state:
                    self._latest_consolidated_state = tab.latest_state
                    self._latest_consolidated_state.locked = False
                    self._latest_consolidated_state.pin = self.pin
                    self._latest_consolidated_state.pairingUri = self.pairing_uri
                    self._latest_consolidated_state.qrSvg = self.qr_svg
            else:
                self._latest_consolidated_state = StateSyncPayload(
                    inCall=False,
                    locked=False,
                    pin=self.pin,
                    pairingUri=self.pairing_uri,
                    qrSvg=self.qr_svg,
                )

            state_msg = Message.state_sync(self._latest_consolidated_state, source=Source.DAEMON)
            await self._broadcast_to_clients(state_msg)

    async def _send_state_to_client(self, websocket: Any) -> None:
        """Envía el estado consolidado a un cliente específico."""
        state = StateSyncPayload(**self._latest_consolidated_state.model_dump())
        state.locked = self._is_locked
        if not self._is_locked and self.active_tabs_count == 0:
            state.inCall = False
        state.pin = self.pin
        state.pairingUri = self.pairing_uri
        state.qrSvg = self.qr_svg
        msg = Message.state_sync(state, source=Source.DAEMON)
        try:
            await websocket.send(msg.to_json())
        except Exception:
            pass

    async def _broadcast_to_clients(self, message: Message) -> None:
        """Retransmite un mensaje a todos los clientes externos conectados."""
        if not self._clients:
            return
        raw = message.to_json()
        to_remove = set()
        for client in self._clients:
            try:
                await client.send(raw)
            except Exception:
                to_remove.add(client)
        self._clients.difference_update(to_remove)

    async def _broadcast_to_tabs(self, message: Message) -> None:
        """Retransmite un mensaje a todas las pestañas de navegador conectadas."""
        if not self._tabs:
            return
        raw = message.to_json()
        to_remove = set()
        for tab_id, tab in self._tabs.items():
            try:
                await tab.websocket.send(raw)
            except Exception:
                to_remove.add(tab_id)
        for tid in to_remove:
            self._tabs.pop(tid, None)
