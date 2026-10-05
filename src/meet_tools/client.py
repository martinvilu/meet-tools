"""Cliente WebSocket para interactuar con el MeetDaemon."""

import asyncio
import os
from typing import Any, AsyncGenerator, Dict, Optional
import websockets
from websockets.asyncio.client import connect

from meet_tools.protocol import Action, ErrorCode, Message, MessageType, Source, StateSyncPayload


class MeetClient:
    """Cliente para control y monitoreo externo de Google Meet."""

    def __init__(self, uri: str = "ws://127.0.0.1:8765", timeout: float = 3.0, reintentos: int = 3):
        self.uri = uri
        self.timeout = timeout
        self.reintentos = reintentos
        self._ws: Optional[Any] = None

    async def connect(self) -> None:
        """Conecta con el daemon concentrador local o LAN."""
        # Evitar interferencias con variables de entorno de proxy HTTP/HTTPS. Si la red del aula se cae
        # un momento, reintenta con espera exponencial (QoL #608): 0,5 s, 1 s, 2 s… hasta `reintentos`.
        espera = 0.5
        for intento in range(self.reintentos + 1):
            try:
                self._ws = await connect(self.uri, proxy=None, open_timeout=self.timeout)
                return
            except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException):
                if intento == self.reintentos:
                    raise
                await asyncio.sleep(espera)
                espera = min(espera * 2, 8.0)

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

        # Drenar saludo inicial si es la primera lectura
        try:
            raw_initial = await asyncio.wait_for(self._ws.recv(), timeout=0.2)
            init_msg = Message.from_json(raw_initial)
            # Saludo inicial consumido
        except asyncio.TimeoutError:
            pass

        cmd = Message.command(action, payload=payload or {}, source=Source.CLIENT)
        await self._ws.send(cmd.to_json())

        resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
        return Message.from_json(resp_raw)

    async def listen_events(self) -> AsyncGenerator[Message, None]:
        """Escucha eventos y actualizaciones de estado en tiempo real."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        async for raw in self._ws:
            try:
                yield Message.from_json(raw)
            except Exception:
                pass
