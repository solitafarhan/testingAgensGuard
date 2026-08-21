"""gRPC server implementing the GuardModule service over a Unix domain socket
(spec sections 2, 3). The Module is the gRPC SERVER; the Daemon is the client.

This phase implements only the GuardModule decision-path service (Health +
the four checks). GuardModuleAdmin is deferred.
"""
from __future__ import annotations

import os
from concurrent import futures

import grpc

from guardmodule.checks.prompt_check import check_prompt
from guardmodule.checks.tool_input_check import check_tool_input
from guardmodule.checks.tool_output_check import check_tool_output
from guardmodule.checks.transcript_check import check_transcript
from guardmodule.health import MAX_CONCURRENT_CHECKS, HealthState
from guardmodule.pb import pb2_grpc
from guardmodule.rules.loader import load_rule_set


class GuardModuleServicer(pb2_grpc.GuardModuleServicer):
    def __init__(self, rules_dir: str | None = None) -> None:
        self.health_state = HealthState()
        # Rules are cheap to evaluate (regex only), so the Module is ready as soon
        # as it has loaded them — no async warm-up needed in this phase.
        ruleset = load_rule_set(rules_dir)
        self.health_state.mark_ready(ruleset)

    @property
    def ruleset(self):
        assert self.health_state.ruleset is not None
        return self.health_state.ruleset

    def Health(self, request, context):
        return self.health_state.health_response()

    def CheckPrompt(self, request, context):
        return check_prompt(request, self.ruleset)

    def CheckTranscript(self, request, context):
        return check_transcript(request, self.ruleset)

    def CheckToolInput(self, request, context):
        return check_tool_input(request, self.ruleset)

    def CheckToolOutput(self, request, context):
        return check_tool_output(request, self.ruleset)


def unix_socket_target(socket_path: str) -> str:
    """Build a grpc Unix-domain-socket target for socket_path, per spec sections 2.2/2.3:
    the Module MUST remove a stale socket file before binding."""
    if os.path.exists(socket_path):
        os.remove(socket_path)
    return f"unix://{socket_path}"


def create_server(bind_target: str, rules_dir: str | None = None) -> tuple[grpc.Server, int]:
    """bind_target is a full grpc target string: either a Unix socket target from
    unix_socket_target() (production — Linux/macOS), or a TCP target such as
    "127.0.0.1:0" (local Windows dev/tests, where grpcio cannot bind AF_UNIX; see
    /memories/repo/guardmodule-notes.md). Returns (server, bound_port); bound_port is
    0 for a Unix socket target."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CHECKS))
    servicer = GuardModuleServicer(rules_dir)
    pb2_grpc.add_GuardModuleServicer_to_server(servicer, server)
    bound_port = server.add_insecure_port(bind_target)
    return server, bound_port


def serve(socket_path: str | None = None, rules_dir: str | None = None) -> None:
    socket_path = socket_path or os.environ["GUARDMODULE_SOCKET"]
    server, _ = create_server(unix_socket_target(socket_path), rules_dir)
    server.start()
    try:
        # Socket file MUST be mode 0600 (spec 2.2) — only the owner may connect.
        os.chmod(socket_path, 0o600)
    except OSError:
        pass
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
