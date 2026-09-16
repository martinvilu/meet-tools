"""Infraestructura para validación y firma digital de WebExtensions con web-ext de Mozilla."""

from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple

try:
    from cast_tools_common.signer import (
        prepare_firefox_staging as _prep_common,
        run_web_ext_lint,
        sign_firefox_addon as _sign_common,
    )
except ImportError:
    sibling = Path(__file__).resolve().parents[3] / "cast-tools-common" / "src"
    if sibling.is_dir() and str(sibling) not in sys.path:
        sys.path.insert(0, str(sibling))
    from cast_tools_common.signer import (
        prepare_firefox_staging as _prep_common,
        run_web_ext_lint,
        sign_firefox_addon as _sign_common,
    )

DEFAULT_ADDON_ID = "meet-bridge@local.dev"


def prepare_firefox_staging(extension_dir: Path, staging_dir: Path, addon_id: str = DEFAULT_ADDON_ID) -> Path:
    """Prepara un directorio temporal con el manifiesto adaptado según las reglas de firma de Mozilla."""
    return _prep_common(
        extension_dir=extension_dir,
        staging_dir=staging_dir,
        addon_id=addon_id,
        firefox_background_scripts=False,
    )


def sign_firefox_addon(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    channel: str = "unlisted",  # "unlisted" o "listed"
    timeout_ms: int = 600000,
    lint_only: bool = False,
    dry_run: bool = False,
    addon_id: str = DEFAULT_ADDON_ID,
) -> Dict[str, Any]:
    """Ejecuta el flujo de validación y firma digital de la extensión mediante Mozilla web-ext."""
    ext_path = extension_dir or Path(__file__).resolve().parent.parent.parent / "extension"
    return _sign_common(
        extension_dir=ext_path,
        output_dir=output_dir,
        api_key=api_key,
        api_secret=api_secret,
        channel=channel,
        timeout_ms=timeout_ms,
        lint_only=lint_only,
        dry_run=dry_run,
        addon_id=addon_id,
        addon_slug="meet-bridge",
        firefox_background_scripts=False,
    )

__all__ = [
    "DEFAULT_ADDON_ID",
    "prepare_firefox_staging",
    "run_web_ext_lint",
    "sign_firefox_addon",
]
