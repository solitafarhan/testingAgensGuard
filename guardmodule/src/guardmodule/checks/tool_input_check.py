"""CheckToolInput handler: evaluates a tool call before it runs (model-outbound
direction) against global + tool_input.yaml rules and produces a ToolInputVerdict
(spec section 5.2)."""
from __future__ import annotations

from guardmodule.pb import pb2
from guardmodule.rules.engine import evaluate
from guardmodule.rules.loader import RuleSet


def check_tool_input(request, ruleset: RuleSet):
    rules = ruleset.rules_for("tool_input")
    text = f"{request.tool_name}: {request.tool_input_json}"
    verdict = evaluate([text], rules, ruleset.ruleset_id)

    action = pb2.GUARD_ACTION_DENY if verdict.action == "DENY" else pb2.GUARD_ACTION_ALLOW
    info = pb2.VerdictInfo(
        reason=verdict.reason,
        labels=verdict.labels,
        rule_id=verdict.rule_id,
        ruleset_id=verdict.ruleset_id,
        confidence=verdict.confidence,
    )
    return pb2.ToolInputVerdict(action=action, info=info)
