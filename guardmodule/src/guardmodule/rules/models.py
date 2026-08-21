"""Data model for a single detection rule.

A rule is loaded from a YAML file and matched against a piece of text (a
prompt, a tool_input_json string, a tool_output body, or a transcript text
block). See docs/guardmodule-implementation-plan.md for the schema.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class RuleAction:
    """Valid values for a rule's ``action`` field."""

    DENY = "deny"
    ALLOW_WITH_CONTEXT = "allow_with_context"

    ALL = (DENY, ALLOW_WITH_CONTEXT)


class PatternType:
    """Valid values for a rule's ``pattern_type`` field."""

    REGEX = "regex"
    SUBSTRING = "substring"

    ALL = (REGEX, SUBSTRING)


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    action: str
    rule_id: str
    pattern_type: str = PatternType.REGEX
    confidence: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    steering_context: str = ""
    correction_message: str = ""
    source_file: str = ""

    def __post_init__(self) -> None:
        if self.action not in RuleAction.ALL:
            raise ValueError(
                f"rule {self.id!r}: invalid action {self.action!r}, must be one of {RuleAction.ALL}"
            )
        if self.pattern_type not in PatternType.ALL:
            raise ValueError(
                f"rule {self.id!r}: invalid pattern_type {self.pattern_type!r}, "
                f"must be one of {PatternType.ALL}"
            )
        if self.action == RuleAction.DENY and not self.correction_message:
            raise ValueError(
                f"rule {self.id!r}: action=deny requires a non-empty correction_message "
                "(spec 6.3: reason is REQUIRED on a deny)"
            )
        if self.action == RuleAction.ALLOW_WITH_CONTEXT and not self.steering_context:
            raise ValueError(
                f"rule {self.id!r}: action=allow_with_context requires a non-empty steering_context"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"rule {self.id!r}: confidence must be in [0, 1], got {self.confidence}")

    def matches(self, text: str) -> bool:
        if not text:
            return False
        if self.pattern_type == PatternType.SUBSTRING:
            return self.pattern.lower() in text.lower()
        return re.search(self.pattern, text, re.IGNORECASE) is not None
