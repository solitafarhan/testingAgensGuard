"""Scripted mock agent/session data structures for testing GuardModule handlers
without a real LLM. Each Scenario is fully deterministic: the plan text and
tool calls for every turn are authored by hand, matching the pattern
demonstrated in the spec's worked trace (prompt_guard.md section 10).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ToolCallEvent:
    tool_name: str
    tool_input_json: str
    tool_output: bytes
    tool_output_truncated: bool = False


@dataclass
class Turn:
    turn_index: int
    plan_text: str
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    # Informational only: the plan text the agent would produce on a stop-hook
    # re-invocation of THIS SAME turn after a CheckTranscript DENY. The mock
    # daemon never issues a second CheckTranscript call for it (spec section
    # 10, step 5 — turn suppression); it is only rendered as a trace note.
    reinvocation_plan_text: str | None = None


@dataclass
class Scenario:
    name: str
    description: str
    prompt: str | None = None
    turns: list[Turn] = field(default_factory=list)
    agent_id: str = "spiffe://tii.ae/agent/claude-code/7cfc977c-38bc-492c-9dfe-ae6cdb8512ee"
    agent_class: str = "claude-code"
    session_id: str = "7cfc977c-38bc-492c-9dfe-ae6cdb8512ee"
    cwd: str = "/Users/deimoz/src/payments"
    matched_profile: str = "go-dev"


def build_transcript_tail(turn: Turn) -> bytes:
    """Builds one JSONL assistant record: an empty `thinking` block (matching
    spec section 5.5's finding that Claude Code never populates it), a `text`
    block with the turn's stated plan, and a `tool_use` block per scripted
    tool call."""
    content: list[dict] = [{"type": "thinking", "thinking": "", "signature": "mock-signature"}]
    if turn.plan_text:
        content.append({"type": "text", "text": turn.plan_text})
    for call in turn.tool_calls:
        content.append(
            {
                "type": "tool_use",
                "name": call.tool_name,
                "input": json.loads(call.tool_input_json),
            }
        )
    record = {"type": "assistant", "message": {"role": "assistant", "content": content}}
    return json.dumps(record).encode("utf-8")
