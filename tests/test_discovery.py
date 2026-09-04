import pytest
from unittest.mock import AsyncMock, patch
from meet_tools.discovery import (
    build_pairing_uri,
    generate_qr_ascii,
    generate_qr_svg,
    get_local_ip,
    MdnsPublisher,
)


def test_get_local_ip():
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4


def test_build_pairing_uri():
    uri = build_pairing_uri("meet", "192.168.1.50", 8765, "1234", name="my-laptop")
    assert uri == "bridge://pair?v=1.3&host=192.168.1.50&port=8765&service=meet&pin=1234&name=my-laptop"


def test_generate_qr_ascii():
    uri = "bridge://pair?v=1.3&host=127.0.0.1&port=8765&service=meet&pin=1234&name=test"
    qr_ascii = generate_qr_ascii(uri)
    assert isinstance(qr_ascii, str)
    assert len(qr_ascii) > 20
    assert "█" in qr_ascii


def test_generate_qr_svg():
    uri = "bridge://pair?v=1.3&host=127.0.0.1&port=8765&service=meet&pin=1234&name=test"
    qr_svg = generate_qr_svg(uri)
    assert isinstance(qr_svg, str)
    assert "<svg" in qr_svg
    assert "</svg>" in qr_svg


@pytest.mark.asyncio
async def test_mdns_publisher_mocked():
    publisher = MdnsPublisher(
        service_name="MeetBridge-test",
        service_type="_meet-bridge._tcp.local.",
        port=8765,
        properties={"service": "meet"},
        host_ip="192.168.1.100",
    )

    with patch("meet_tools.discovery.AsyncZeroconf") as mock_azc_cls:
        mock_azc_instance = AsyncMock()
        mock_azc_cls.return_value = mock_azc_instance

        success = await publisher.start()
        assert success is True
        assert mock_azc_instance.async_register_service.called

        await publisher.stop()
        assert mock_azc_instance.async_unregister_service.called
        assert mock_azc_instance.async_close.called
