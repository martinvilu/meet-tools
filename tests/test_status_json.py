"""Regresión de MEET-D0601: `status`/`monitor` deben ofrecer `--json` versionado."""

import json

from typer.testing import CliRunner

from meet_tools.cli import app
from test_client_cli import thread_daemon  # noqa: F401

runner = CliRunner()


def test_status_json_es_una_linea_versionada(thread_daemon):  # noqa: F811
    _, uri = thread_daemon
    res = runner.invoke(app, ["status", "--uri", uri, "--json"])
    assert res.exit_code == 0
    datos = json.loads(res.stdout)
    assert datos["schema_version"] == "1.0.0"
    assert datos["herramienta"] == "meet-tools"
    assert "inCall" in datos["estado"] and "participantCount" in datos["estado"]
    assert "Estado Consolidado" not in res.stdout


def test_status_json_sin_daemon_sale_1_con_error_json():
    res = runner.invoke(app, ["status", "--uri", "ws://127.0.0.1:1", "--json"])
    assert res.exit_code == 1


def test_monitor_declara_json():
    res = runner.invoke(app, ["monitor", "--help"])
    assert "--json" in res.stdout
