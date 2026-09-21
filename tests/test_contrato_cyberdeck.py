"""Contrato de meet-tools con su consumidor declarado (cyberdeck) — MEET-D0902.

cyberdeck es solo especificación (`cyberdeck/android-spec.md`): no hay cliente que
consuma este daemon. Estos tests fijan lo que la spec asume y que SÍ existe aquí,
para que un cambio de puerto, de servicio mDNS o del URI de emparejamiento no
rompa en silencio a un futuro cliente.
"""

import re

from typer.testing import CliRunner

from meet_tools.cli import app
from meet_tools.daemon import MeetDaemon
from meet_tools.discovery import build_pairing_uri
import inspect

runner = CliRunner()


def test_puerto_por_defecto_coincide_con_la_spec():
    firma = inspect.signature(MeetDaemon.__init__)
    assert firma.parameters["port"].default == 8765


def test_servicio_mdns_publicado():
    fuente = inspect.getsource(MeetDaemon)
    assert "_meet-bridge._tcp.local." in fuente


def test_uri_de_emparejamiento_v13():
    uri = build_pairing_uri("meet", "192.168.1.105", 8765, "4821", name="Workstation")
    assert uri == "bridge://pair?v=1.3&host=192.168.1.105&port=8765&service=meet&pin=4821&name=Workstation"
    assert re.fullmatch(r"bridge://pair\?v=1\.3(&[a-z]+=[^&]+)+", uri)
