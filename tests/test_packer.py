import json
from pathlib import Path
import zipfile
import pytest

from meet_tools.packer import package_extension


def test_package_extension_chrome_and_firefox(tmp_path):
    res = package_extension(output_dir=tmp_path, target="both")

    assert "chrome" in res
    assert "firefox" in res

    chrome_zip = res["chrome"]
    firefox_xpi = res["firefox"]

    assert chrome_zip.exists()
    assert firefox_xpi.exists()

    # Verificar paquete de Chrome
    with zipfile.ZipFile(chrome_zip, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "content.js" in namelist
        assert "overlay.css" in namelist
        assert "popup.html" in namelist

        chrome_manifest = json.loads(zf.read("manifest.json"))
        assert chrome_manifest["manifest_version"] == 3
        assert "browser_specific_settings" not in chrome_manifest

    # Verificar paquete de Firefox
    with zipfile.ZipFile(firefox_xpi, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "content.js" in namelist

        ff_manifest = json.loads(zf.read("manifest.json"))
        assert ff_manifest["manifest_version"] == 3
        assert "browser_specific_settings" in ff_manifest
        assert "gecko" in ff_manifest["browser_specific_settings"]
        assert ff_manifest["browser_specific_settings"]["gecko"]["id"] == "meet-bridge@local.dev"
        assert ff_manifest["browser_specific_settings"]["gecko"]["data_collection_permissions"]["required"] == ["none"]

