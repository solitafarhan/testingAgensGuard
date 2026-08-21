"""CheckTranscript handler: parses the agent's completed-turn transcript (JSONL
tail or file), extracts text/tool_use blocks, and evaluates them against global +
transcript.yaml rules, producing a TranscriptVerdict (spec section 5.2, 5.5, 5.6).

Note: turn-suppression (never re-checking a denied turn's transcript on a
stop-hook re-invocation) is Daemon behavior per the spec and is implemented in
mock/mock_daemon.py, not here — this handler always evaluates whatever it is
given.
"""
from __future__ import annotations

from guardmodule.pb import pb2
from guardmodule.rules.engine import evaluate
from guardmodule.rules.loader import RuleSet
from guardmodule.transcript_parser import parse_transcript_file, parse_transcript_tail


def check_transcript(request, ruleset: RuleSet):
    if request.transcript_tail:
        parsed = parse_transcript_tail(request.transcript_tail, request.transcript_tail_truncated)
    else:
        parsed = parse_transcript_file(request.transcript_path)

    rules = ruleset.rules_for("transcript")
    verdict = evaluate(parsed.all_text(), rules, ruleset.ruleset_id)

    action = pb2.GUARD_ACTION_DENY if verdict.action == "DENY" else pb2.GUARD_ACTION_ALLOW
    info = pb2.VerdictInfo(
        reason=verdict.reason,
        labels=verdict.labels,
        rule_id=verdict.rule_id,
        ruleset_id=verdict.ruleset_id,
        confidence=verdict.confidence,
    )
    return pb2.TranscriptVerdict(action=action, info=info)
