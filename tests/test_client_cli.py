import asyncio
import threading
import time
import pytest
from typer.testing import CliRunner

from meet_tools.cli import app
from meet_tools.client import MeetClient
from meet_tools.daemon import MeetDaemon
from meet_tools.protocol import Action, Message, Source, StateSyncPayload
from websockets.asyncio.client import connect

runner = CliRunner()


@pytest.fixture
def thread_daemon():
    """Ejecuta el daemon en un hilo separado para pruebas sincrónicas de CLI."""
    loop = asyncio.new_event_loop()
    daemon = MeetDaemon(host="127.0.0.1", port=0)

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(daemon.start())
        loop.run_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.1)

    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"

    yield daemon, uri

    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=1.0)


@pytest.fixture
async def running_daemon():
    daemon = MeetDaemon(host="127.0.0.1", port=0)
    await daemon.start()
    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"
    yield daemon, uri
    await daemon.stop()


@pytest.mark.asyncio
async def test_client_get_state(running_daemon):
    daemon, uri = running_daemon

    # Conectar pestaña activa
    async with connect(uri, proxy=None) as tab:
        await tab.recv()  # saludo
        st = StateSyncPayload(inCall=True, micMuted=True, cameraOff=False, isHost=True, tabId="tab_cli")
        await tab.send(Message.state_sync(st, source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        async with MeetClient(uri=uri) as client:
            state = await client.get_state()
            assert state.inCall is True
            assert state.micMuted is True
            assert state.isHost is True


def test_cli_help():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Sistema de control externo para Google Meet" in res.stdout


def test_cli_status_command(thread_daemon):
    daemon, uri = thread_daemon
    res = runner.invoke(app, ["status", "--uri", uri])
    assert res.exit_code == 0
    assert "Estado Consolidado de Google Meet" in res.stdout
    assert "En Llamada" in res.stdout


def test_cli_mic_command_no_call(thread_daemon):
    daemon, uri = thread_daemon
    res = runner.invoke(app, ["mic", "--uri", uri])
    assert res.exit_code == 0
    assert "ERR_NO_ACTIVE_CALL" in res.stdout


def test_cli_doctor():
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert "Diagnóstico del Entorno MEET-TOOLS" in res.stdout

    res_json = runner.invoke(app, ["doctor", "--json"])
    assert res_json.exit_code == 0
    assert '"schema_version": "1.0.0"' in res_json.stdout
    assert '"herramienta": "meet-tools"' in res_json.stdout
    assert '"ok": true' in res_json.stdout

