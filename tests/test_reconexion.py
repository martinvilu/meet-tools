"""Reconexión con espera exponencial cuando el daemon no responde (QoL #608)."""

import asyncio
import importlib

import pytest

paquete = "meet_tools" if importlib.util.find_spec("meet_tools") else "slide_tools"
cliente = importlib.import_module(f"{paquete}.client")
Clase = getattr(cliente, "MeetClient", None) or cliente.SlideClient


def test_reintenta_y_despues_falla(monkeypatch):
    intentos = []
    esperas = []

    async def conectar(*args, **kwargs):
        intentos.append(1)
        raise OSError("sin red")

    async def dormir(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(cliente, "connect", conectar)
    monkeypatch.setattr(cliente.asyncio, "sleep", dormir)
    with pytest.raises(OSError):
        asyncio.run(Clase(uri="ws://127.0.0.1:1", reintentos=3).connect())
    assert len(intentos) == 4 and esperas == [0.5, 1.0, 2.0]
