import asyncio
import pytest
from websockets.asyncio.client import connect

from meet_tools.client import MeetClient
from meet_tools.daemon import MeetDaemon
from meet_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    Source,
    StateSyncPayload,
)


@pytest.fixture
async def dynamic_daemon():
    daemon = MeetDaemon(host="127.0.0.1", port=0, command_timeout=1.0)
    await daemon.start()
    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"
    yield daemon, uri
    await daemon.stop()


@pytest.mark.asyncio
async def test_malformed_json_handling(dynamic_daemon):
    daemon, uri = dynamic_daemon
    async with connect(uri, proxy=None) as client:
        await client.recv()  # saludo

        # Enviar JSON corrupto
        await client.send("esto no es un json valido {")
        resp_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
        resp = Message.from_json(resp_raw)
        assert resp.type == MessageType.ERROR
        assert resp.payload["code"] == ErrorCode.ERR_MALFORMED_MESSAGE.value


@pytest.mark.asyncio
async def test_tab_state_transition_in_call_to_lobby(dynamic_daemon):
    """Prueba que si una de dos pestañas pasa de in_call a lobby, el bloqueo se libera sin desconexión."""
    daemon, uri = dynamic_daemon

    async with connect(uri, proxy=None) as tab1, connect(uri, proxy=None) as tab2:
        await tab1.recv()
        await tab2.recv()

        # Ambas reportan inCall=True
        await tab1.send(Message.state_sync(StateSyncPayload(inCall=True, tabId="t1"), source=Source.EXTENSION).to_json())
        await tab2.send(Message.state_sync(StateSyncPayload(inCall=True, tabId="t2"), source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        assert daemon.is_locked is True

        # Tab2 cambia de llamada activa a lobby
        await tab2.send(Message.state_sync(StateSyncPayload(inCall=False, tabId="t2"), source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        assert daemon.is_locked is False


@pytest.mark.asyncio
async def test_client_listen_events_generator(dynamic_daemon):
    daemon, uri = dynamic_daemon

    async with connect(uri, proxy=None) as ext:
        await ext.recv()
        # Registrar extensión activa
        await ext.send(Message.state_sync(StateSyncPayload(inCall=True, tabId="t_ev"), source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        async with MeetClient(uri=uri) as client:
            # Emitir evento desde extensión
            await ext.send(Message.event(Action.ADMISSION_REQUESTED, {"count": 4}, source=Source.EXTENSION).to_json())

            # Consumir eventos del generador
            events_received = []
            async for ev in client.listen_events():
                events_received.append(ev)
                if ev.action == Action.ADMISSION_REQUESTED.value:
                    break

            assert any(e.action == Action.ADMISSION_REQUESTED.value and e.payload["count"] == 4 for e in events_received)


@pytest.mark.asyncio
async def test_commands_all_variants(dynamic_daemon):
    """Verifica el ruteo de comandos varios: TOGGLE_CAM, TOGGLE_HAND, ADMIT_ALL, MUTE_ALL, LEAVE_CALL."""
    daemon, uri = dynamic_daemon

    async with connect(uri, proxy=None) as ext:
        await ext.recv()
        await ext.send(Message.state_sync(StateSyncPayload(inCall=True, isHost=True, tabId="t_all"), source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        async with MeetClient(uri=uri) as client:
            # Task que responde a comandos en la extensión
            async def mock_ext_worker():
                while True:
                    raw = await ext.recv()
                    msg = Message.from_json(raw)
                    if msg.type == MessageType.COMMAND:
                        req_id = msg.payload.get("requestId")
                        ack = Message.ack(msg.action, {"requestId": req_id, "ok": True}, source=Source.EXTENSION)
                        await ext.send(ack.to_json())

            worker_task = asyncio.create_task(mock_ext_worker())

            try:
                for act in (Action.TOGGLE_CAM, Action.TOGGLE_HAND, Action.ADMIT_ALL, Action.MUTE_ALL):
                    resp = await client.send_command(act)
                    assert resp.type == MessageType.ACK
                    assert resp.payload.get("ok") is True

                resp_leave = await client.send_command(Action.LEAVE_CALL, {"endForAll": True})
                assert resp_leave.type == MessageType.ACK
            finally:
                worker_task.cancel()
