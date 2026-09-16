"""Módulo de descubrimiento en red local (mDNS) y utilidades de código QR."""

import logging
from pathlib import Path
import sys

try:
    import cast_tools_common.discovery as _c_disc
    from cast_tools_common.discovery import (
        MdnsPublisher as _BaseMdnsPublisher,
        build_pairing_uri,
        generate_qr_ascii,
        generate_qr_svg,
        get_local_ip,
    )
except ImportError:
    sibling = Path(__file__).resolve().parents[3] / "cast-tools-common" / "src"
    if sibling.is_dir() and str(sibling) not in sys.path:
        sys.path.insert(0, str(sibling))
    import cast_tools_common.discovery as _c_disc
    from cast_tools_common.discovery import (
        MdnsPublisher as _BaseMdnsPublisher,
        build_pairing_uri,
        generate_qr_ascii,
        generate_qr_svg,
        get_local_ip,
    )

from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

logger = logging.getLogger("meet_tools.discovery")


class MdnsPublisher(_BaseMdnsPublisher):
    """Publicador mDNS de meet-tools delegando en cast_tools_common."""

    async def start(self) -> bool:
        # Asegurar interoperabilidad con monkeypatching/mocks sobre el módulo local
        _c_disc.AsyncZeroconf = AsyncZeroconf
        _c_disc.ServiceInfo = ServiceInfo
        return await super().start()


__all__ = [
    "AsyncZeroconf",
    "ServiceInfo",
    "MdnsPublisher",
    "build_pairing_uri",
    "generate_qr_ascii",
    "generate_qr_svg",
    "get_local_ip",
    "logger",
]
