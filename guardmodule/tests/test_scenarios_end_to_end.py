"""End-to-end integration tests: spin up a real GuardModule gRPC server and
drive every mock scenario through it via MockDaemon, asserting the exact
verdict sequence described in each scenario's docstring.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import grpc
import pytest

from guardmodule.pb import pb2
from guardmodule.server import create_server
from guardmodule.transport import client_target, server_bind_target
from mock.mock_daemon import MockDaemon
from mock.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def daemon():
    with tempfile.TemporaryDirectory() as tmp_dir:
        socket_path = str(Path(tmp_dir) / "guardmodule.sock")
        server, bound_port = create_server(server_bind_target(socket_path))
        server.start()
        try:
            channel = grpc.insecure_channel(client_target(socket_path, bound_port))
            yield MockDaemon(channel)
        finally:
            server.stop(None)


def _actions_for(trace, rpc_name):
    return [entry.response["action"] for entry in trace if entry.rpc == rpc_name]


def test_benign_task_allows_everything(daemon):
    trace = daemon.run_scenario(SCENARIOS["benign_task"])
    for rpc in ("CheckPrompt", "CheckToolInput", "CheckToolOutput", "CheckTranscript"):
        assert _actions_for(trace, rpc) == ["GUARD_ACTION_ALLOW"]


def test_prompt_injection_tool_output_denied(daemon):
    trace = daemon.run_scenario(SCENARIOS["prompt_injection_tool_output"])
    assert _actions_for(trace, "CheckToolOutput") == ["GUARD_ACTION_DENY"]
    assert _actions_for(trace, "CheckTranscript") == ["GUARD_ACTION_ALLOW"]


def test_credential_mention_steers(daemon):
    trace = daemon.run_scenario(SCENARIOS["credential_mention_steering"])
    prompt_entries = [e for e in trace if e.rpc == "CheckPrompt"]
    assert len(prompt_entries) == 1
    response = prompt_entries[0].response
    assert response["action"] == "GUARD_ACTION_ALLOW"
    assert "credentials" in response["additional_context"].lower()


def test_self_modification_multiturn_denies_then_allows(daemon):
    trace = daemon.run_scenario(SCENARIOS["self_modification_multiturn"])
    prompt_response = next(e.response for e in trace if e.rpc == "CheckPrompt")
    assert prompt_response["action"] == "GUARD_ACTION_ALLOW"
    assert "security controls" in prompt_response["additional_context"].lower()

    assert _actions_for(trace, "CheckTranscript") == ["GUARD_ACTION_DENY", "GUARD_ACTION_ALLOW"]
    assert any(e.rpc == "(force-continue)" for e in trace)
    # Only two CheckTranscript calls total — no suppressed re-invocation was ever
    # attempted as a real RPC.
    assert len(_actions_for(trace, "CheckTranscript")) == 2


def test_blocked_prompt_ends_session(daemon):
    trace = daemon.run_scenario(SCENARIOS["blocked_prompt"])
    assert _actions_for(trace, "CheckPrompt") == ["GUARD_ACTION_DENY"]
    assert not any(e.rpc in ("CheckToolInput", "CheckToolOutput", "CheckTranscript") for e in trace)


def test_dangerous_tool_input_denied_before_tool_runs(daemon):
    trace = daemon.run_scenario(SCENARIOS["dangerous_tool_input"])
    assert _actions_for(trace, "CheckToolInput") == ["GUARD_ACTION_DENY"]
    assert _actions_for(trace, "CheckToolOutput") == []


def test_truncated_tool_output_always_denied(daemon):
    trace = daemon.run_scenario(SCENARIOS["truncated_tool_output_must_deny"])
    output_entries = [e for e in trace if e.rpc == "CheckToolOutput"]
    assert len(output_entries) == 1
    response = output_entries[0].response
    assert response["action"] == "GUARD_ACTION_DENY"
    assert response["info"]["rule_id"] == "tool_output.truncated"


def test_health_reports_ready_with_stable_ruleset(daemon):
    trace = daemon.run_scenario(SCENARIOS["benign_task"])
    health_response = next(e.response for e in trace if e.rpc == "Health")
    assert health_response["ready"] is True
    caps = health_response["capabilities"]
    assert caps["check_prompt"] is True
    assert caps["check_tool_input"] is True
    assert caps["check_tool_output"] is True
    assert caps["check_transcript"] is True
