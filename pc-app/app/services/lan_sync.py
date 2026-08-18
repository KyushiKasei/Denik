"""Volitelná domácí relace: PIN, 15 min, druhý listener jen pro /lan."""

from __future__ import annotations

import ipaddress
import os
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import segno

from app.config import DEFAULT_LAN_PORT
from app.logging_setup import get_logger

COOKIE_NAME = "pamatky_lan"
SESSION_SECONDS = 15 * 60
LAN_PATH = "/lan"

_log = get_logger()

_lock = threading.Lock()
_session: LanSession | None = None
_server: Any = None
_thread: threading.Thread | None = None
_timer: threading.Timer | None = None
_generation = 0


class LanListenError(RuntimeError):
    """Port 8766 se nepodařilo otevřít."""


@dataclass
class LanSession:
    pin: str
    token: str
    expires_at: float
    urls: list[str] = field(default_factory=list)
    qr_svg: str = ""
    listen: bool = True


def lan_port() -> int:
    return DEFAULT_LAN_PORT


def is_rfc1918(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.version == 4 and addr.is_private and not addr.is_loopback and not addr.is_link_local


def private_ipv4_addresses() -> list[str]:
    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if is_rfc1918(ip) and ip not in found:
                found.append(ip)
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0)
        probe.connect(("192.168.0.1", 1))
        ip = probe.getsockname()[0]
        probe.close()
        if is_rfc1918(ip) and ip not in found:
            found.insert(0, ip)
    except OSError:
        pass
    return found


def _urls_for(ips: list[str]) -> list[str]:
    port = lan_port()
    if not ips:
        return [f"http://<IP-tohoto-PC>:{port}{LAN_PATH}"]
    return [f"http://{ip}:{port}{LAN_PATH}" for ip in ips]


def _qr_svg(url: str) -> str:
    if "<" in url:
        return ""
    qr = segno.make(url, error="m")
    try:
        return qr.svg_inline(scale=5, dark="#1e1a16", light="#ffffff")
    except TypeError:
        return qr.svg_inline(scale=5)


def remaining_seconds() -> int:
    with _lock:
        if _session is None:
            return 0
        return max(0, int(_session.expires_at - time.monotonic()))


def session_is_active() -> bool:
    with _lock:
        return _active_unlocked()


def _active_unlocked() -> bool:
    if _session is None:
        return False
    if _session.expires_at <= time.monotonic():
        return False
    return True


def current_pin() -> str | None:
    with _lock:
        if not _active_unlocked() or _session is None:
            return None
        return _session.pin


def current_token() -> str | None:
    with _lock:
        if not _active_unlocked() or _session is None:
            return None
        return _session.token


def token_is_valid(token: str | None) -> bool:
    if not token:
        return False
    with _lock:
        if not _active_unlocked() or _session is None:
            return False
        try:
            return secrets.compare_digest(_session.token, token)
        except (ValueError, TypeError):
            return False


def pin_matches(pin: str | None) -> bool:
    if not pin:
        return False
    cleaned = pin.strip().replace(" ", "")
    with _lock:
        if not _active_unlocked() or _session is None:
            return False
        try:
            return secrets.compare_digest(_session.pin, cleaned)
        except (ValueError, TypeError):
            return False


def lan_status() -> dict[str, Any]:
    with _lock:
        active = _active_unlocked()
        session = _session if active else None
        remaining = max(0, int(session.expires_at - time.monotonic())) if session else 0
        return {
            "active": active,
            "pin": session.pin if session else None,
            "urls": list(session.urls) if session else [],
            "url": session.urls[0] if session and session.urls else None,
            "qr_svg": session.qr_svg if session else "",
            "remaining_seconds": remaining,
            "port": lan_port(),
            "listen": session.listen if session else False,
        }


def start_lan_session(*, listen: bool = True) -> dict[str, Any]:
    global _session, _generation
    if os.environ.get("PAMATKY_LAN_LISTEN", "1") == "0":
        listen = False
    stop_lan_session()
    ips = private_ipv4_addresses()
    urls = _urls_for(ips)
    session = LanSession(
        pin=f"{secrets.randbelow(1_000_000):06d}",
        token=secrets.token_urlsafe(24),
        expires_at=time.monotonic() + SESSION_SECONDS,
        urls=urls,
        qr_svg=_qr_svg(urls[0]) if ips else "",
        listen=listen,
    )
    with _lock:
        _generation += 1
        gen = _generation
        _session = session
    if listen:
        try:
            _start_listener()
        except OSError as exc:
            stop_lan_session()
            raise LanListenError(f"Port {lan_port()} se nepodařilo otevřít.") from exc
    _arm_timer(gen)
    _log.info("lan session started listen=%s urls=%s", listen, urls)
    return lan_status()


def stop_lan_session() -> None:
    global _session, _server, _thread, _timer
    with _lock:
        timer = _timer
        _timer = None
        server = _server
        thread = _thread
        _server = None
        _thread = None
        _session = None
    if timer is not None:
        timer.cancel()
    if server is not None:
        server.should_exit = True
        server.force_exit = True
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=3)
    if server is not None:
        _log.info("lan session stopped")


def expire_lan_session_for_tests() -> None:
    with _lock:
        if _session is not None:
            _session.expires_at = time.monotonic() - 1


def reset_lan_state() -> None:
    stop_lan_session()


def _arm_timer(generation: int) -> None:
    global _timer

    def _expire() -> None:
        with _lock:
            if _generation != generation:
                return
        stop_lan_session()

    timer = threading.Timer(SESSION_SECONDS, _expire)
    timer.daemon = True
    with _lock:
        _timer = timer
    timer.start()


def _start_listener() -> None:
    global _server, _thread
    import uvicorn

    from app.web.lan_app import lan_app

    config = uvicorn.Config(
        lan_app,
        host="0.0.0.0",
        port=lan_port(),
        log_level="warning",
        access_log=False,
        loop="asyncio",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="pamatky-lan", daemon=True)
    with _lock:
        _server = server
        _thread = thread
    thread.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if getattr(server, "started", False):
            return
        if not thread.is_alive():
            raise OSError("LAN listener skončil hned po startu.")
        time.sleep(0.05)
    if not getattr(server, "started", False):
        raise OSError("LAN listener se nespustil.")
