"""El PIN de emparejamiento se genera con un generador criptográfico de 6 dígitos (N-MEET-02)."""

from __future__ import annotations

import secrets

from meet_tools.daemon import generar_pin


def test_pin_de_6_digitos():
    for _ in range(200):
        pin = generar_pin()
        assert len(pin) == 6 and pin.isdigit()


def test_usa_secrets(monkeypatch):
    monkeypatch.setattr(secrets, "randbelow", lambda n: 0)
    assert generar_pin() == "100000"
