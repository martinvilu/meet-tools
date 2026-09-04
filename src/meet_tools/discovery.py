"""Módulo de descubrimiento en red local (mDNS) y utilidades de código QR."""

import io
import logging
import socket
from typing import Dict, Optional
import qrcode
import qrcode.image.svg
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

logger = logging.getLogger("meet_tools.discovery")


def get_local_ip() -> str:
    """Obtiene la dirección IP local de la interfaz de red primaria."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def build_pairing_uri(service: str, host: str, port: int, pin: str, name: Optional[str] = None) -> str:
    """Construye el URI estandarizado de emparejamiento directo."""
    host_name = name or socket.gethostname()
    return f"bridge://pair?v=1.3&host={host}&port={port}&service={service}&pin={pin}&name={host_name}"


def generate_qr_ascii(data: str) -> str:
    """Genera una representación ASCII compacta del código QR para terminales."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    out = io.StringIO()
    qr.print_ascii(out=out, invert=True)
    return out.getvalue().strip()


def generate_qr_svg(data: str) -> str:
    """Genera una cadena XML con el código QR vectorizado en formato SVG."""
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(data, image_factory=factory)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


class MdnsPublisher:
    """Publicador asíncrono de servicios en red local mediante mDNS / DNS-SD."""

    def __init__(
        self,
        service_name: str,
        service_type: str,
        port: int,
        properties: Optional[Dict[str, str]] = None,
        host_ip: Optional[str] = None,
    ):
        self.service_name = service_name
        self.service_type = service_type if service_type.endswith(".") else f"{service_type}."
        self.port = port
        self.properties = properties or {}
        self.host_ip = host_ip or get_local_ip()

        self._azc: Optional[AsyncZeroconf] = None
        self._info: Optional[ServiceInfo] = None

    async def start(self) -> bool:
        """Registra el servicio mDNS en la red local."""
        try:
            hostname = socket.gethostname()
            server_name = f"{hostname}.local."
            fqdn = f"{self.service_name}.{self.service_type}"

            raw_props = {
                k.encode("utf-8"): str(v).encode("utf-8") for k, v in self.properties.items()
            }

            self._info = ServiceInfo(
                type_=self.service_type,
                name=fqdn,
                addresses=[socket.inet_aton(self.host_ip)],
                port=self.port,
                properties=raw_props,
                server=server_name,
            )

            self._azc = AsyncZeroconf()
            await self._azc.async_register_service(self._info)
            logger.info(f"mDNS publicado: {fqdn} -> {self.host_ip}:{self.port}")
            return True
        except Exception as e:
            logger.warning(f"No se pudo publicar servicio mDNS ({e}). Operando en modo directo.")
            if self._azc:
                try:
                    await self._azc.async_close()
                except Exception:
                    pass
                self._azc = None
            return False

    async def stop(self) -> None:
        """Cancela el registro mDNS y cierra el socket multicast."""
        if self._azc and self._info:
            try:
                await self._azc.async_unregister_service(self._info)
                await self._azc.async_close()
                logger.info(f"mDNS despublicado: {self.service_name}")
            except Exception as e:
                logger.debug(f"Error cerrando mDNS: {e}")
            finally:
                self._azc = None
                self._info = None
