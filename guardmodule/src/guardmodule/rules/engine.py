"""Evaluates a set of rules against one or more pieces of text and produces a
Verdict. Both global rules and check-specific rules are passed in as one
combined list (the caller unions them via RuleSet.rules_for) and are matched
together — "both apply" per the locked-in design decision.

Precedence: any DENY match wins over any ALLOW_WITH_CONTEXT match. Among
matches of the winning kind, the highest-confidence rule is used. Ties keep
the first rule encountered (stable, deterministic for a fixed rules dir).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from guardmodule.rules.models import Rule, RuleAction


@dataclass
class Verdict:
    action: str  # "ALLOW" or "DENY"
    reason: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    rule_id: str = ""
    ruleset_id: str = ""
    confidence: float = 0.0
    # Only meaningful for CheckPrompt: injected as PromptVerdict.additional_context
    # when action == "ALLOW" and a steering rule matched.
    steering_context: str = ""


def evaluate(texts: list[str], rules: list[Rule], ruleset_id: str) -> Verdict:
    deny_matches: list[Rule] = []
    steer_matches: list[Rule] = []

    for text in texts:
        if not text:
            continue
        for rule in rules:
            if rule.matches(text):
                if rule.action == RuleAction.DENY:
                    deny_matches.append(rule)
                else:
                    steer_matches.append(rule)

    if deny_matches:
        best = max(deny_matches, key=lambda r: r.confidence)
        return Verdict(
            action="DENY",
            reason=best.correction_message,
            labels=dict(best.labels),
            rule_id=best.rule_id,
            ruleset_id=ruleset_id,
            confidence=best.confidence,
        )

    if steer_matches:
        best = max(steer_matches, key=lambda r: r.confidence)
        return Verdict(
            action="ALLOW",
            labels=dict(best.labels),
            rule_id=best.rule_id,
            ruleset_id=ruleset_id,
            confidence=best.confidence,
            steering_context=best.steering_context,
        )

    return Verdict(action="ALLOW", ruleset_id=ruleset_id)
