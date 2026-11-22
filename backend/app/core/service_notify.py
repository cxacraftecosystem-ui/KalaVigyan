from __future__ import annotations

import os
import socket
from collections.abc import Mapping

__all__ = ["NOTIFY_SOCKET", "READY", "WATCHDOG", "notify_service"]

NOTIFY_SOCKET = "NOTIFY_SOCKET"
READY = "READY=1"
WATCHDOG = "WATCHDOG=1"
ABSTRACT_PREFIX = "@"


def notify_service(state: str, *, environ: Mapping[str, str] = os.environ) -> bool:
    address = environ.get(NOTIFY_SOCKET, "")
    if not address:
        return False
    if address.startswith(ABSTRACT_PREFIX):
        address = "\0" + address.removeprefix(ABSTRACT_PREFIX)
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sender:
        sender.connect(address)
        sender.sendall(state.encode("utf-8"))
    return True
