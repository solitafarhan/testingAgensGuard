"""CheckPrompt handler: evaluates GuardContext.prompt against global + prompt.yaml
rules and produces a PromptVerdict (spec section 5.2, 6.2)."""
from __future__ import annotations

from guardmodule.pb import pb2
from guardmodule.rules.engine import evaluate
from guardmodule.rules.loader import RuleSet


def check_prompt(request, ruleset: RuleSet):
    rules = ruleset.rules_for("prompt")
    verdict = evaluate([request.prompt], rules, ruleset.ruleset_id)

    action = pb2.GUARD_ACTION_DENY if verdict.action == "DENY" else pb2.GUARD_ACTION_ALLOW
    info = pb2.VerdictInfo(
        reason=verdict.reason,
        labels=verdict.labels,
        rule_id=verdict.rule_id,
        ruleset_id=verdict.ruleset_id,
        confidence=verdict.confidence,
    )
    return pb2.PromptVerdict(
        action=action,
        info=info,
        additional_context=verdict.steering_context if action == pb2.GUARD_ACTION_ALLOW else "",
    )
