"""meet-tools debe resolver sus dependencias como paquete, no desde carpetas hermanas (N-MEET-01).

Antes importaba cast_tools_common agregando ../cast-tools-common/src a sys.path:
funcionaba solo dentro del monorepo de la cátedra, y el wheel instalado en un
entorno limpio ni siquiera ejecutaba `meet-tools --help`.
"""

from __future__ import annotations

from pathlib import Path

import cast_tools_common

SRC = Path(__file__).resolve().parents[1] / "src"


def test_el_codigo_no_modifica_sys_path():
    culpables = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if "sys.path.insert" in p.read_text(encoding="utf-8")]
    assert culpables == []


def test_cast_tools_common_viene_del_entorno_instalado():
    origen = Path(cast_tools_common.__file__).resolve()
    assert "site-packages" in origen.parts, origen
