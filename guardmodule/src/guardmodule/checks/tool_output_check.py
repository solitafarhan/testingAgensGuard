"""CheckToolOutput handler: evaluates what a tool returned before the model reads
it (model-inbound direction — where prompt injection actually arrives, per spec
section 5.2) against global + tool_output.yaml rules, producing a ToolOutputVerdict.

Per spec section 5.3: "A Module that must see the whole body MUST deny when this
[tool_output_truncated] is true rather than judge a fragment." This handler
enforces that rule unconditionally, before running any pattern match.
"""
from __future__ import annotations

from guardmodule.pb import pb2
from guardmodule.rules.engine import evaluate
from guardmodule.rules.loader import RuleSet

TRUNCATED_REASON = (
    "tool output was truncated before the Module could see the whole body; "
    "a fragment cannot be judged safely"
)


def check_tool_output(request, ruleset: RuleSet):
    if request.tool_output_truncated:
        info = pb2.VerdictInfo(
            reason=TRUNCATED_REASON,
            labels={"rule": "truncated-output", "detector": "tool_output"},
            rule_id="tool_output.truncated",
            ruleset_id=ruleset.ruleset_id,
            confidence=1.0,
        )
        return pb2.ToolOutputVerdict(action=pb2.GUARD_ACTION_DENY, info=info)

    rules = ruleset.rules_for("tool_output")
    decoded = request.tool_output.decode("utf-8", errors="replace")
    verdict = evaluate([decoded], rules, ruleset.ruleset_id)

    action = pb2.GUARD_ACTION_DENY if verdict.action == "DENY" else pb2.GUARD_ACTION_ALLOW
    info = pb2.VerdictInfo(
        reason=verdict.reason,
        labels=verdict.labels,
        rule_id=verdict.rule_id,
        ruleset_id=verdict.ruleset_id,
        confidence=verdict.confidence,
    )
    return pb2.ToolOutputVerdict(action=action, info=info)
