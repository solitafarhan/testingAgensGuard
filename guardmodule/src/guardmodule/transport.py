"""Local dev/test transport helper.

Production target is always a Unix domain socket (spec sections 2, 3). This
module exists only so tests and the mock harness can run on this Windows dev
machine, where grpcio cannot bind AF_UNIX (see
/memories/repo/guardmodule-notes.md in agent memory for details). On POSIX
this uses a real Unix socket, identical to production; on Windows it falls
back to TCP loopback so the rest of the code under test is unchanged.
"""
from __future__ import annotations

import sys

from guardmodule.server import unix_socket_target

UDS_SUPPORTED = not sys.platform.startswith("win")


def server_bind_target(socket_path: str) -> str:
    if UDS_SUPPORTED:
        return unix_socket_target(socket_path)
    return "127.0.0.1:0"


def client_target(socket_path: str, bound_port: int) -> str:
    if UDS_SUPPORTED:
        return f"unix://{socket_path}"
    return f"127.0.0.1:{bound_port}"
