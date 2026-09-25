"""Empaquetador de la WebExtension para Google Chrome y Mozilla Firefox."""

from pathlib import Path
from typing import Dict, Optional

from cast_tools_common.packer import pack_web_extension


def package_extension(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    target: str = "both",  # "chrome", "firefox", "both"
    addon_id: str = "meet-bridge@local.dev",
) -> Dict[str, Path]:
    """Genera paquetes .zip para Chrome y .xpi / .zip para Firefox con manifiestos adaptados."""
    ext_path = extension_dir or Path(__file__).resolve().parent.parent.parent / "extension"
    out_path = output_dir or Path(__file__).resolve().parent.parent.parent / "dist"
    return pack_web_extension(
        extension_dir=ext_path,
        output_dir=out_path,
        target=target,
        addon_id=addon_id,
        addon_slug="meet-bridge",
        firefox_background_scripts=False,
    )
