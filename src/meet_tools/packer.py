"""Empaquetador de la WebExtension para Google Chrome y Mozilla Firefox."""

import json
from pathlib import Path
from typing import Dict, List, Optional
import zipfile


def package_extension(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    target: str = "both",  # "chrome", "firefox", "both"
    addon_id: str = "meet-bridge@local.dev"
) -> Dict[str, Path]:
    """Genera paquetes .zip para Chrome y .xpi / .zip para Firefox con manifiestos adaptados."""
    ext_path = extension_dir or Path(__file__).resolve().parent.parent.parent / "extension"
    out_path = output_dir or Path(__file__).resolve().parent.parent.parent / "dist"

    if not ext_path.exists():
        raise FileNotFoundError(f"Directorio de extensión no encontrado en: {ext_path}")

    manifest_file = ext_path / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"manifest.json no encontrado en: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        base_manifest = json.load(f)

    version = base_manifest.get("version", "1.0.0")
    out_path.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Path] = {}

    files_to_pack = [
        p for p in ext_path.rglob("*")
        if p.is_file() and not p.name.startswith(".") and not p.suffix in (".swp", ".tmp", ".pyc")
    ]

    targets = ["chrome", "firefox"] if target == "both" else [target.lower()]

    for tgt in targets:
        manifest_copy = json.loads(json.dumps(base_manifest))

        if tgt == "firefox":
            # Inyectar identificación requerida por Firefox MV3
            manifest_copy["browser_specific_settings"] = {
                "gecko": {
                    "id": addon_id,
                    "strict_min_version": "142.0",
                    "data_collection_permissions": {
                        "required": ["none"]
                    }
                }
            }
            archive_name = f"meet-bridge-firefox-v{version}.xpi"
        else:
            # Limpiar posibles campos exclusivos de Firefox
            manifest_copy.pop("browser_specific_settings", None)
            archive_name = f"meet-bridge-chrome-v{version}.zip"

        archive_path = out_path / archive_name
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files_to_pack:
                arcname = file_path.relative_to(ext_path)
                if arcname.as_posix() == "manifest.json":
                    zf.writestr("manifest.json", json.dumps(manifest_copy, indent=2, ensure_ascii=False))
                else:
                    zf.write(file_path, arcname)

        results[tgt] = archive_path

    return results
