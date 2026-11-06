"""Advertise the API on the local network with mDNS / Bonjour.

Dispensers look for the service type `_dietbalancer._tcp` and read the TXT record
`path=/api/v1`, so nobody has to type the server's IP address into the device.
If this fails (no multicast, Docker bridge networking, a firewall), the app keeps
working: the dispenser's setup page lets you type the address instead."""
import logging
import socket

from app.core.config import get_settings

logger = logging.getLogger("diet_balancer.discovery")
SERVICE_TYPE = "_dietbalancer._tcp.local."
_zc = None
_info = None


def _lan_ip() -> str | None:
    # Opening a UDP socket "towards" a public address picks the LAN interface; no packet is sent.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except OSError:
            return None
    return None if ip.startswith("127.") else ip


def start() -> None:
    global _zc, _info
    settings = get_settings()
    if not settings.MDNS_ENABLED:
        return
    try:
        from zeroconf import ServiceInfo, Zeroconf

        ip = settings.MDNS_ADVERTISE_IP or _lan_ip()
        if not ip:
            logger.warning("mDNS: no LAN address found; dispensers must be given the server address manually.")
            return
        _info = ServiceInfo(
            SERVICE_TYPE, f"Diet Balancer API.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(ip)], port=settings.MDNS_PORT,
            properties={"path": "/api/v1", "api": "1"}, server="diet-balancer.local.",
        )
        _zc = Zeroconf()
        _zc.register_service(_info, allow_name_change=True)
        logger.info("mDNS: advertising %s on %s:%s", SERVICE_TYPE, ip, settings.MDNS_PORT)
    except Exception as exc:  # never block the API because discovery failed
        logger.warning("mDNS advertising unavailable (%s). Dispensers can use a manual server address.", exc)
        _zc = None


def stop() -> None:
    global _zc
    if _zc is not None:
        try:
            _zc.unregister_service(_info)
            _zc.close()
        except Exception:
            pass
        _zc = None
