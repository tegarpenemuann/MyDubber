import ipaddress
import os
import socket
import sys

_enabled = False


def require_loopback(host) -> None:
    if isinstance(host, bytes):
        host = host.decode("ascii")
    if host in {None, "localhost"}:
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise PermissionError(f"Offline mode blocked an external host: {host}") from exc
    if not address.is_loopback:
        raise PermissionError(f"Offline mode blocked an external address: {host}")


def network_audit(event: str, arguments: tuple) -> None:
    if event == "socket.getaddrinfo":
        require_loopback(arguments[0])
    elif event in {"socket.connect", "socket.sendto"}:
        connection, address = arguments
        if connection.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address[0])


def enforce_offline() -> None:
    global _enabled
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    if not _enabled:
        sys.addaudithook(network_audit)
        _enabled = True
