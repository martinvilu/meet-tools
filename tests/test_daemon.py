import asyncio
import pytest
from websockets.asyncio.client import connect

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
async def daemon_server():
    daemon = MeetDaemon(host="127.0.0.1", port=0, command_timeout=1.0)
    await daemon.start()
    port = daemon._server.sockets[0].getsockname()[1]
    yield daemon, port
    await daemon.stop()


@pytest.mark.asyncio
async def test_no_active_call_rejection(daemon_server):
    daemon, port = daemon_server
    uri = f"ws://127.0.0.1:{port}"

    async with connect(uri, proxy=None) as client:
        # 1. Al conectarse, recibe STATE_SYNC con inCall=False
        init_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
        init_msg = Message.from_json(init_raw)
        assert init_msg.action == "STATE_SYNC"
        assert init_msg.payload["inCall"] is False

        # 2. Intentar comandar micrófono sin llamadas activas
        cmd = Message.command(Action.TOGGLE_MIC)
        await client.send(cmd.to_json())

        resp_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
        resp = Message.from_json(resp_raw)
        assert resp.type == MessageType.ERROR
        assert resp.payload["code"] == ErrorCode.ERR_NO_ACTIVE_CALL.value


@pytest.mark.asyncio
async def test_single_call_forwarding_and_ack(daemon_server):
    daemon, port = daemon_server
    uri = f"ws://127.0.0.1:{port}"

    # Conectar extensión
    async with connect(uri, proxy=None) as ext:
        await asyncio.wait_for(ext.recv(), timeout=2.0)  # Drenar saludo inicial

        # Registrar pestaña con inCall=True
        state = StateSyncPayload(inCall=True, micMuted=False, isHost=True, tabId="tab_1")
        reg_msg = Message.state_sync(state, source=Source.EXTENSION)
        await ext.send(reg_msg.to_json())
        await asyncio.sleep(0.05)

        # Conectar cliente
        async with connect(uri, proxy=None) as client:
            # Cliente recibe estado inicial
            init_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
            init_msg = Message.from_json(init_raw)
            assert init_msg.payload["inCall"] is True
            assert init_msg.payload["micMuted"] is False

            # Cliente envía TOGGLE_MIC
            cmd = Message.command(Action.TOGGLE_MIC)
            await client.send(cmd.to_json())

            # Extensión recibe el comando ruteado
            ext_recv_raw = await asyncio.wait_for(ext.recv(), timeout=2.0)
            ext_cmd = Message.from_json(ext_recv_raw)
            assert ext_cmd.action == "TOGGLE_MIC"
            assert "requestId" in ext_cmd.payload

            # Extensión responde con ACK
            ack = Message.ack("TOGGLE_MIC", {"requestId": ext_cmd.payload["requestId"], "micMuted": True}, source=Source.EXTENSION)
            await ext.send(ack.to_json())

            # Cliente recibe respuesta
            client_resp_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
            client_resp = Message.from_json(client_resp_raw)
            assert client_resp.type == MessageType.ACK
            assert client_resp.payload["micMuted"] is True


@pytest.mark.asyncio
async def test_concurrency_lock_and_recovery(daemon_server):
    daemon, port = daemon_server
    uri = f"ws://127.0.0.1:{port}"

    # 1. Conectar pestaña 1 en llamada
    async with connect(uri, proxy=None) as tab1:
        await asyncio.wait_for(tab1.recv(), timeout=2.0)  # saludo
        s1 = StateSyncPayload(inCall=True, tabId="tab_1")
        await tab1.send(Message.state_sync(s1, source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)
        assert daemon.is_locked is False

        # Conectar cliente
        async with connect(uri, proxy=None) as client:
            await asyncio.wait_for(client.recv(), timeout=2.0)  # Estado inicial

            # 2. Conectar pestaña 2 TAMBIÉN en llamada -> Se dispara LOCK
            async with connect(uri, proxy=None) as tab2:
                await asyncio.wait_for(tab2.recv(), timeout=2.0)  # saludo
                s2 = StateSyncPayload(inCall=True, tabId="tab_2")
                await tab2.send(Message.state_sync(s2, source=Source.EXTENSION).to_json())
                await asyncio.sleep(0.05)

                assert daemon.is_locked is True

                # Tab 1 y Tab 2 deben haber recibido SHOW_ALERT
                t1_alert = Message.from_json(await asyncio.wait_for(tab1.recv(), timeout=2.0))
                assert t1_alert.action == Action.SHOW_ALERT.value
                t2_alert = Message.from_json(await asyncio.wait_for(tab2.recv(), timeout=2.0))
                assert t2_alert.action == Action.SHOW_ALERT.value

                # Cliente debe haber recibido LOCKED_STATE
                client_lock = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
                assert client_lock.action == Action.LOCKED_STATE.value
                assert client_lock.payload["locked"] is True

                # Comando en estado bloqueado debe ser rechazado inmediatamente
                await client.send(Message.command(Action.TOGGLE_CAM).to_json())
                rej = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
                assert rej.type == MessageType.ERROR
                assert rej.payload["code"] == ErrorCode.ERR_MULTIPLE_CALLS_ACTIVE.value

            # 3. Tab 2 se desconectó
            await asyncio.sleep(0.1)
            assert daemon.is_locked is False

            # Tab 1 recibe orden de cerrar banner
            t1_dismiss = Message.from_json(await asyncio.wait_for(tab1.recv(), timeout=2.0))
            assert t1_dismiss.action == Action.DISMISS_ALERT.value

            # Cliente recibe notificación de desbloqueo
            client_unlock = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
            assert client_unlock.payload["locked"] is False


@pytest.mark.asyncio
async def test_permission_denied_event_forwarding(daemon_server):
    daemon, port = daemon_server
    uri = f"ws://127.0.0.1:{port}"

    async with connect(uri, proxy=None) as ext:
        await asyncio.wait_for(ext.recv(), timeout=2.0)  # saludo
        s = StateSyncPayload(inCall=True, isHost=False, tabId="tab_guest")
        await ext.send(Message.state_sync(s, source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        async with connect(uri, proxy=None) as client:
            await asyncio.wait_for(client.recv(), timeout=2.0)  # Estado inicial

            # Extensión emite PERMISSION_DENIED
            perm_ev = Message.event(
                Action.PERMISSION_DENIED,
                {"action": "MUTE_ALL", "detail": "No eres anfitrión"},
                source=Source.EXTENSION
            )
            await ext.send(perm_ev.to_json())

            # Cliente debe recibir el evento
            ev_recv = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
            assert ev_recv.action == Action.PERMISSION_DENIED.value
            assert ev_recv.payload["action"] == "MUTE_ALL"
