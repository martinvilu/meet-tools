"""Regresión: `--version` como opción global (LINEAMIENTOS §3).

Antes solo existía (en algunas herramientas) como subcomando y `--version`
terminaba en "No such option".
"""

from importlib.metadata import version

import pytest
from typer.testing import CliRunner

from meet_tools import __version__
from meet_tools.cli import app

runner = CliRunner()


@pytest.mark.parametrize("opcion", ["--version", "-v"])
def test_la_opcion_version_imprime_la_del_paquete_y_sale_con_0(opcion):
    res = runner.invoke(app, [opcion])
    assert res.exit_code == 0
    assert "MEET" in res.output
    assert version("meet-tools") in res.output


def test_la_version_del_modulo_coincide_con_la_instalada():
    assert __version__ == version("meet-tools")
