"""Emparejamiento seguro: PIN, tokens de reconexión, origen web y confianza local (Ola 24)."""

import asyncio

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from meet_tools.client import MeetClient
from meet_tools.daemon import MeetDaemon
from meet_tools.protocol import Action, ErrorCode, Message, MessageType, Source


async def _daemon(**kw):
    daemon = MeetDaemon(host="127.0.0.1", port=0, pin="482913", require_pin=True, enable_mdns=False,
                        command_timeout=0.5, **kw)
    await daemon.start()
    return daemon, f"ws://127.0.0.1:{daemon._server.sockets[0].getsockname()[1]}"


async def _recibir(ws):
    return Message.from_json(await asyncio.wait_for(ws.recv(), timeout=3))


@pytest.mark.asyncio
async def test_el_pin_no_se_entrega_a_quien_no_se_emparejo():
    daemon, uri = await _daemon(confiar_en_local=False)
    try:
        async with connect(uri, proxy=None) as ws:
            saludo = await _recibir(ws)
            assert saludo.payload["pin"] is None and saludo.payload["qrSvg"] is None
            await ws.send(Message.command(Action.PAIR_REQUEST, {"pin": "482913"}).to_json())
            ok = await _recibir(ws)
            assert ok.action == Action.PAIRING_SUCCESS.value and len(ok.payload["token"]) >= 40
            assert (await _recibir(ws)).payload["pin"] == "482913"
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_una_pagina_web_no_puede_conectarse():
    daemon, uri = await _daemon()
    try:
        with pytest.raises(InvalidStatus) as exc:
            async with connect(uri, proxy=None, origin="https://sitio-malicioso.example"):
                pass
        assert exc.value.response.status_code == 403
        async with connect(uri, proxy=None, origin="moz-extension://meet-bridge") as ws:
            assert (await _recibir(ws)).action == Action.STATE_SYNC.value
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_la_cli_local_no_necesita_pin():
    """Antes `meet-tools mic` salía con ERR_PAIRING_REQUIRED con el PIN por omisión."""
    daemon, uri = await _daemon()
    try:
        async with MeetClient(uri=uri) as cliente:
            resp = await cliente.send_command(Action.TOGGLE_MIC)
        assert resp.payload["code"] == ErrorCode.ERR_NO_ACTIVE_CALL.value
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_reconexion_con_token_sin_pin():
    daemon, uri = await _daemon(confiar_en_local=False)
    try:
        cliente = MeetClient(uri=uri, pin="482913")
        await cliente.connect()
        token = cliente.token
        await cliente.close()
        assert token

        otro = MeetClient(uri=uri)
        otro.token = token
        await otro.connect()  # sin PIN: alcanza el token
        resp = await otro.send_command(Action.TOGGLE_MIC)
        assert resp.payload["code"] == ErrorCode.ERR_NO_ACTIVE_CALL.value
        await otro.close()

        daemon._tokens.revocar_todos()
        vencido = MeetClient(uri=uri)
        vencido.token = token
        with pytest.raises(RuntimeError, match="ERR_INVALID_PIN"):
            await vencido.connect()
        await vencido.close()
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_la_extension_de_otro_equipo_necesita_pin_y_tiene_limite():
    daemon, uri = await _daemon(confiar_en_local=False)
    try:
        async with connect(uri, proxy=None) as ext:
            await _recibir(ext)
            for _ in range(5):
                await ext.send(Message(source=Source.EXTENSION, type=MessageType.EVENT, action=Action.TAB_REGISTER.value,
                                       payload={"tabId": "t", "pin": "000000", "tabState": "in_call"}).to_json())
                assert (await _recibir(ext)).payload["code"] == ErrorCode.ERR_INVALID_PIN.value
            # Bloqueada: ni el PIN correcto entra durante un minuto.
            await ext.send(Message(source=Source.EXTENSION, type=MessageType.EVENT, action=Action.TAB_REGISTER.value,
                                   payload={"tabId": "t", "pin": "482913", "tabState": "in_call"}).to_json())
            assert (await _recibir(ext)).payload["code"] == ErrorCode.ERR_INVALID_PIN.value
        assert daemon.active_tabs_count == 0
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_la_extension_conecta_desde_la_pagina_de_meet():
    """content.js abre el WebSocket con el Origin de meet.google.com: es local y de confianza."""
    daemon, uri = await _daemon()
    try:
        async with connect(uri, proxy=None, origin="https://meet.google.com") as ext:
            assert (await _recibir(ext)).payload["pin"] == "482913"
            await ext.send(Message(source=Source.EXTENSION, type=MessageType.EVENT, action=Action.TAB_REGISTER.value,
                                   payload={"tabId": "t1", "tabState": "in_call"}).to_json())
            await asyncio.sleep(0.1)
            assert daemon.active_tabs_count == 1
    finally:
        await daemon.stop()
