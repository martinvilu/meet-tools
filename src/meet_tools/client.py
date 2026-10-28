"""Cliente WebSocket para interactuar con el MeetDaemon."""

import asyncio
import os
from typing import Any, AsyncGenerator, Dict, Optional
import websockets
from websockets.asyncio.client import connect

from cast_tools_common.reconexion import con_reintentos

from meet_tools.protocol import Action, ErrorCode, Message, MessageType, Source, StateSyncPayload


class MeetClient:
    """Cliente para control y monitoreo externo de Google Meet."""

    def __init__(self, uri: str = "ws://127.0.0.1:8765", timeout: float = 3.0, reintentos: int = 3,
                 pin: Optional[str] = None):
        """`pin` (o la variable MEET_TOOLS_PIN) hace falta sólo contra un daemon de otro equipo: desde
        el mismo equipo la conexión es de confianza. Al emparejarse, el daemon devuelve un token que
        el cliente usa para reconectarse sin el PIN."""
        self.uri = uri
        self.timeout = timeout
        self.reintentos = reintentos
        self.pin = pin or os.environ.get("MEET_TOOLS_PIN") or None
        self.token: Optional[str] = None
        self._ws: Optional[Any] = None

    async def connect(self) -> None:
        """Conecta con el daemon concentrador local o LAN."""
        # Evitar interferencias con variables de entorno de proxy HTTP/HTTPS. Si la red del aula se cae
        # un momento, reintenta con espera exponencial (QoL #608): 0,5 s, 1 s, 2 s… hasta `reintentos`.
        self._ws = await con_reintentos(
            lambda: connect(self.uri, proxy=None, open_timeout=self.timeout),
            self.reintentos,
            errores=(OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException),
        )
        if self.pin or self.token:
            await self.pair()

    async def pair(self) -> None:
        """Se empareja con el token (si ya lo tiene) o con el PIN; guarda el token nuevo."""
        assert self._ws is not None
        credenciales = {"token": self.token} if self.token else {"pin": self.pin}
        await self._ws.send(Message.command(Action.PAIR_REQUEST, credenciales).to_json())
        while True:
            resp = Message.from_json(await asyncio.wait_for(self._ws.recv(), timeout=self.timeout + 1.5))
            if resp.action == Action.PAIRING_SUCCESS.value:
                self.token = resp.payload.get("token") or self.token
                return
            if resp.type == MessageType.ERROR:
                if self.token and self.pin:  # token vencido o daemon reiniciado: probar con el PIN
                    self.token = None
                    await self._ws.send(Message.command(Action.PAIR_REQUEST, {"pin": self.pin}).to_json())
                    continue
                raise RuntimeError(f"Emparejamiento rechazado ({resp.payload.get('code')}): {resp.payload.get('reason')}")

    async def close(self) -> None:
        """Cierra la conexión WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "MeetClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def get_state(self) -> StateSyncPayload:
        """Solicita y retorna el estado actual de la llamada."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        # Consumir el saludo inicial si está pendiente
        init_raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
        msg = Message.from_json(init_raw)
        if msg.action == Action.STATE_SYNC.value:
            return StateSyncPayload(**msg.payload)

        # O solicitar explícitamente GET_STATE
        await self._ws.send(Message.command(Action.GET_STATE).to_json())
        resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
        resp_msg = Message.from_json(resp_raw)
        return StateSyncPayload(**resp_msg.payload)

    async def send_command(self, action: Action | str, payload: Optional[Dict[str, Any]] = None) -> Message:
        """Envía un comando al daemon y espera la confirmación (ACK) o rechazo (ERROR)."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        cmd = Message.command(action, payload=payload or {}, source=Source.CLIENT)
        await self._ws.send(cmd.to_json())

        # El saludo, los STATE_SYNC y los eventos que llegan en el medio no son la respuesta.
        while True:
            resp = Message.from_json(await asyncio.wait_for(self._ws.recv(), timeout=self.timeout))
            if resp.type in (MessageType.ACK.value, MessageType.ERROR.value):
                return resp

    async def listen_events(self) -> AsyncGenerator[Message, None]:
        """Escucha eventos y actualizaciones de estado en tiempo real."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        async for raw in self._ws:
            try:
                yield Message.from_json(raw)
            except Exception:
                pass
