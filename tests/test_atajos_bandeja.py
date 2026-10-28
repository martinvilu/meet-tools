"""Atajos de teclado globales y estado para la bandeja (Ola 24)."""

from typer.testing import CliRunner

from meet_tools.cli import app, atajos_de_meet, evaluar_estado_meet


def test_atajos_con_ruta_absoluta_y_notificacion():
    lista = atajos_de_meet("ws://127.0.0.1:9000")
    assert [a.combinacion for a in lista] == ["<Control><Alt>m", "<Control><Alt>v", "<Control><Alt>h",
                                               "<Control><Alt>a", "<Control><Alt>s"]
    assert all(a.clave.startswith("p1-meet-") and a.comando.endswith("--uri ws://127.0.0.1:9000 --notificar")
               for a in lista)


def test_atajos_fuera_de_gnome(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    res = CliRunner().invoke(app, ["atajos", "--instalar"])
    assert res.exit_code == 0 and "sólo funciona en GNOME" in res.output


def test_estado_para_la_bandeja():
    assert evaluar_estado_meet({"inCall": True, "participantCount": 12}) == (True, "En llamada (12 participantes)")
    assert evaluar_estado_meet({"inCall": True, "locked": True})[0] is False
    assert evaluar_estado_meet({}) == (False, "Daemon activo, sin llamada en el navegador")
