"""Infraestructura para validación y firma digital de WebExtensions con web-ext de Mozilla."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Dict, Optional, Tuple


DEFAULT_ADDON_ID = "meet-bridge@local.dev"


def prepare_firefox_staging(extension_dir: Path, staging_dir: Path, addon_id: str = DEFAULT_ADDON_ID) -> Path:
    """Prepara un directorio temporal con el manifiesto adaptado según las reglas de firma de Mozilla."""
    if not extension_dir.exists():
        raise FileNotFoundError(f"Directorio de extensión no encontrado: {extension_dir}")

    staging_dir.mkdir(parents=True, exist_ok=True)

    for item in extension_dir.rglob("*"):
        if item.is_file() and not item.name.startswith(".") and item.suffix not in (".swp", ".tmp", ".pyc"):
            rel_path = item.relative_to(extension_dir)
            dest = staging_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)

    # Adaptar manifest.json
    manifest_path = staging_dir / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["browser_specific_settings"] = {
        "gecko": {
            "id": addon_id,
            "strict_min_version": "142.0",
            "data_collection_permissions": {
                "required": ["none"]
            }
        }
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return staging_dir


def run_web_ext_lint(source_dir: Path) -> Tuple[bool, str]:
    """Ejecuta web-ext lint sobre el directorio de extensión preparado."""
    cmd = ["web-ext", "lint", "-s", str(source_dir), "--no-config-discovery"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    success = (res.returncode == 0)
    output = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
    return success, output.strip()


def sign_firefox_addon(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    channel: str = "unlisted",  # "unlisted" o "listed"
    timeout_ms: int = 600000,
    lint_only: bool = False,
    dry_run: bool = False,
    addon_id: str = DEFAULT_ADDON_ID
) -> Dict[str, any]:
    """Ejecuta el flujo de validación y firma digital de la extensión mediante Mozilla web-ext."""
    ext_path = extension_dir or Path(__file__).resolve().parent.parent.parent / "extension"
    out_path = output_dir or Path(__file__).resolve().parent.parent.parent / "dist"
    out_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="web-ext-staging-") as temp_dir:
        staging_dir = Path(temp_dir) / "extension"
        prepare_firefox_staging(ext_path, staging_dir, addon_id=addon_id)

        # 1. Lint previo obligatorio
        lint_ok, lint_output = run_web_ext_lint(staging_dir)
        if not lint_ok and not lint_only:
            raise RuntimeError(f"Fallo de validación web-ext lint:\n{lint_output}")

        if lint_only:
            return {
                "status": "lint_passed" if lint_ok else "lint_failed",
                "lint_output": lint_output,
                "staging_dir": str(staging_dir)
            }

        # 2. Obtener credenciales AMO
        key = api_key or os.environ.get("WEB_EXT_API_KEY") or os.environ.get("AMO_JWT_ISSUER")
        secret = api_secret or os.environ.get("WEB_EXT_API_SECRET") or os.environ.get("AMO_JWT_SECRET")

        if dry_run:
            cmd_preview = [
                "web-ext", "sign",
                "--source-dir", str(staging_dir),
                "--artifacts-dir", str(out_path),
                "--api-key", key or "<AMO_API_KEY>",
                "--api-secret", secret or "<AMO_API_SECRET>",
                "--channel", channel,
                "--timeout", str(timeout_ms),
                "--no-config-discovery"
            ]
            return {
                "status": "dry_run",
                "lint_ok": lint_ok,
                "command": " ".join(cmd_preview),
                "credentials_present": bool(key and secret)
            }

        if not key or not secret:
            raise ValueError(
                "Credenciales de Mozilla AMO ausentes. Proporcioná --api-key y --api-secret "
                "o definí las variables de entorno WEB_EXT_API_KEY y WEB_EXT_API_SECRET.\n"
                "Podés generar tus claves en: https://addons.mozilla.org/developers/addon/api/key/"
            )

        # 3. Ejecutar web-ext sign
        artifacts_dir = Path(temp_dir) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        sign_cmd = [
            "web-ext", "sign",
            "--source-dir", str(staging_dir),
            "--artifacts-dir", str(artifacts_dir),
            "--api-key", key,
            "--api-secret", secret,
            "--channel", channel,
            "--timeout", str(timeout_ms),
            "--no-config-discovery"
        ]

        proc = subprocess.run(sign_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            err_msg = (proc.stderr or "") + "\n" + (proc.stdout or "")
            raise RuntimeError(f"Fallo en web-ext sign (código {proc.returncode}):\n{err_msg.strip()}")

        # 4. Localizar y copiar el .xpi firmado
        signed_files = list(artifacts_dir.glob("*.xpi"))
        if not signed_files:
            raise FileNotFoundError("web-ext sign finalizó sin generar un archivo .xpi firmado en los artefactos.")

        signed_src = signed_files[0]
        final_dest = out_path / f"meet-bridge-v1.1.0-signed.xpi"
        shutil.copy2(signed_src, final_dest)

        return {
            "status": "signed",
            "signed_file": str(final_dest),
            "channel": channel,
            "raw_output": proc.stdout.strip()
        }
