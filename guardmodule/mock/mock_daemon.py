"""Acts as the real AgentsGuard Daemon for testing purposes: drives the full
gRPC call sequence (Health -> CheckPrompt -> per-turn CheckToolInput /
CheckToolOutput -> CheckTranscript) against a real GuardModule server, and
reproduces the Daemon's turn-suppression behavior (spec section 10, step 5):
never re-call CheckTranscript a second time for a turn already checked once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict

from guardmodule.pb import pb2, pb2_grpc
from mock.mock_agent import Scenario, build_transcript_tail


@dataclass
class TraceEntry:
    rpc: str
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rpc": self.rpc, "request": self.request, "response": self.response, "note": self.note}


class MockDaemon:
    def __init__(self, channel: grpc.Channel) -> None:
        self.stub = pb2_grpc.GuardModuleStub(channel)

    @staticmethod
    def _ctx(scenario: Scenario) -> "pb2.GuardContext":
        return pb2.GuardContext(
            agent_id=scenario.agent_id,
            agent_class=scenario.agent_class,
            session_id=scenario.session_id,
            cwd=scenario.cwd,
            matched_profile=scenario.matched_profile,
        )

    def _call(self, trace: list[TraceEntry], rpc_name: str, stub_method, request, note: str = ""):
        response = stub_method(request, timeout=2)
        trace.append(
            TraceEntry(
                rpc=rpc_name,
                request=MessageToDict(request, preserving_proto_field_name=True),
                response=MessageToDict(response, preserving_proto_field_name=True),
                note=note,
            )
        )
        return response

    def run_scenario(self, scenario: Scenario) -> list[TraceEntry]:
        trace: list[TraceEntry] = []
        ctx = self._ctx(scenario)

        self._call(trace, "Health", self.stub.Health, pb2.HealthRequest())

        if scenario.prompt is not None:
            prompt_req = pb2.CheckPromptRequest(ctx=ctx, prompt=scenario.prompt)
            prompt_verdict = self._call(trace, "CheckPrompt", self.stub.CheckPrompt, prompt_req)
            if prompt_verdict.action == pb2.GUARD_ACTION_DENY:
                trace.append(
                    TraceEntry(rpc="(session)", note="prompt denied — session ends, no turns run")
                )
                return trace

        checked_turns: dict[int, str] = {}

        for turn in scenario.turns:
            for call in turn.tool_calls:
                input_req = pb2.CheckToolInputRequest(
                    ctx=ctx, tool_name=call.tool_name, tool_input_json=call.tool_input_json
                )
                input_verdict = self._call(trace, "CheckToolInput", self.stub.CheckToolInput, input_req)
                if input_verdict.action == pb2.GUARD_ACTION_DENY:
                    trace.append(
                        TraceEntry(
                            rpc="(tool call)",
                            note=f"{call.tool_name} refused before running — no CheckToolOutput call",
                        )
                    )
                    continue

                output_req = pb2.CheckToolOutputRequest(
                    ctx=ctx,
                    tool_name=call.tool_name,
                    tool_output=call.tool_output,
                    tool_output_truncated=call.tool_output_truncated,
                )
                output_verdict = self._call(trace, "CheckToolOutput", self.stub.CheckToolOutput, output_req)
                if output_verdict.action == pb2.GUARD_ACTION_DENY:
                    trace.append(
                        TraceEntry(
                            rpc="(tool result)",
                            note=f"{call.tool_name} output blocked — the tool already ran, "
                            "but its output does not reach the model",
                        )
                    )

            if turn.turn_index in checked_turns:
                trace.append(
                    TraceEntry(
                        rpc="(stop hook)",
                        note=(
                            f"turn {turn.turn_index} re-invocation suppressed — transcript only "
                            "grows, Daemon does not re-call CheckTranscript"
                        ),
                    )
                )
                continue

            transcript_req = pb2.CheckTranscriptRequest(
                ctx=ctx,
                transcript_path="",
                transcript_tail=build_transcript_tail(turn),
                transcript_tail_truncated=False,
                turn_index=turn.turn_index,
            )
            transcript_verdict = self._call(
                trace, "CheckTranscript", self.stub.CheckTranscript, transcript_req
            )
            checked_turns[turn.turn_index] = (
                "DENY" if transcript_verdict.action == pb2.GUARD_ACTION_DENY else "ALLOW"
            )

            if transcript_verdict.action == pb2.GUARD_ACTION_DENY:
                trace.append(
                    TraceEntry(
                        rpc="(force-continue)",
                        note="turn force-continued; info.reason injected into the agent's "
                        "next turn as an instruction",
                    )
                )

        return trace
