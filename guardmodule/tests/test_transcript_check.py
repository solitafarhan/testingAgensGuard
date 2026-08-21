"""Unit tests for the CheckTranscript handler."""
from __future__ import annotations

import json

from guardmodule.checks.transcript_check import check_transcript
from guardmodule.pb import pb2
from guardmodule.rules.loader import load_rule_set

RULESET = load_rule_set()


def _transcript_tail(text_blocks: list[str]) -> bytes:
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    content += [{"type": "text", "text": t} for t in text_blocks]
    line = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})
    return line.encode("utf-8")


def test_benign_plan_allowed():
    tail = _transcript_tail(["Plan: read the config file and compare values."])
    req = pb2.CheckTranscriptRequest(
        ctx=pb2.GuardContext(), transcript_tail=tail, transcript_tail_truncated=False, turn_index=1
    )
    verdict = check_transcript(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW


def test_disabling_audit_log_denied():
    tail = _transcript_tail(
        ["Plan: read the deploy config, then disable the audit log since it adds latency."]
    )
    req = pb2.CheckTranscriptRequest(
        ctx=pb2.GuardContext(), transcript_tail=tail, transcript_tail_truncated=False, turn_index=1
    )
    verdict = check_transcript(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_DENY
    assert "audit log" in verdict.info.reason


def test_thinking_blocks_never_contribute_text():
    """Regression check for spec section 5.5: thinking blocks are always empty in
    Claude Code and must not be treated as a text source."""
    content = [{"type": "thinking", "thinking": "disable the audit log", "signature": "sig"}]
    line = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})
    req = pb2.CheckTranscriptRequest(
        ctx=pb2.GuardContext(),
        transcript_tail=line.encode("utf-8"),
        transcript_tail_truncated=False,
        turn_index=1,
    )
    verdict = check_transcript(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW


def test_truncated_tail_with_partial_first_line_is_handled():
    good_line = _transcript_tail(["Plan: run the test suite."]).decode("utf-8")
    tail = ("bogus_partial_fragment_not_json" + "\n" + good_line).encode("utf-8")
    req = pb2.CheckTranscriptRequest(
        ctx=pb2.GuardContext(), transcript_tail=tail, transcript_tail_truncated=True, turn_index=1
    )
    verdict = check_transcript(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW
