"""La extensión declara su CSP sin `upgrade-insecure-requests`.

Sin `content_security_policy`, Firefox aplica a las extensiones Manifest V3 un CSP por omisión
con `upgrade-insecure-requests`, que convierte `ws://127.0.0.1:8765` en `wss://`: el daemon no
habla TLS y la extensión nunca se conecta (el daemon sólo registra «connection closed").
Reproducido en slide-tools con Firefox 158; acá se aplica lo mismo.
"""

import json
import zipfile
from pathlib import Path

from meet_tools.packer import package_extension

MANIFEST = Path(__file__).resolve().parent.parent / "extension" / "manifest.json"


def test_csp_explicito_sin_upgrade():
    csp = json.loads(MANIFEST.read_text(encoding="utf-8"))["content_security_policy"]["extension_pages"]
    assert "script-src 'self'" in csp and "upgrade-insecure-requests" not in csp


def test_el_paquete_de_firefox_conserva_el_csp(tmp_path):
    xpi = package_extension(target="firefox", output_dir=tmp_path)["firefox"]
    with zipfile.ZipFile(xpi) as z:
        manifest = json.loads(z.read("manifest.json"))
    assert "upgrade-insecure-requests" not in manifest["content_security_policy"]["extension_pages"]
