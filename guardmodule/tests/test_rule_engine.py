"""Unit tests for the rule engine (models, loader, engine)."""
from __future__ import annotations

import pytest

from guardmodule.rules.engine import evaluate
from guardmodule.rules.loader import load_rule_set
from guardmodule.rules.models import PatternType, Rule, RuleAction


def make_rule(**overrides) -> Rule:
    defaults = dict(
        id="test.rule",
        pattern="danger",
        action=RuleAction.DENY,
        rule_id="test.rule",
        pattern_type=PatternType.REGEX,
        confidence=0.9,
        labels={},
        correction_message="dangerous pattern found",
        steering_context="",
    )
    defaults.update(overrides)
    return Rule(**defaults)


class TestRuleValidation:
    def test_deny_requires_correction_message(self):
        with pytest.raises(ValueError, match="correction_message"):
            make_rule(action=RuleAction.DENY, correction_message="")

    def test_allow_with_context_requires_steering_context(self):
        with pytest.raises(ValueError, match="steering_context"):
            make_rule(action=RuleAction.ALLOW_WITH_CONTEXT, correction_message="", steering_context="")

    def test_invalid_action_rejected(self):
        with pytest.raises(ValueError, match="invalid action"):
            make_rule(action="maybe")

    def test_invalid_pattern_type_rejected(self):
        with pytest.raises(ValueError, match="invalid pattern_type"):
            make_rule(pattern_type="fuzzy")

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            make_rule(confidence=1.5)


class TestRuleMatching:
    def test_regex_match_case_insensitive(self):
        rule = make_rule(pattern=r"disable.{0,10}audit", pattern_type=PatternType.REGEX)
        assert rule.matches("I will DISABLE the audit log")
        assert not rule.matches("everything is fine")

    def test_substring_match_case_insensitive(self):
        rule = make_rule(pattern="secret", pattern_type=PatternType.SUBSTRING)
        assert rule.matches("this contains a SECRET value")
        assert not rule.matches("nothing here")

    def test_empty_text_never_matches(self):
        rule = make_rule(pattern="danger")
        assert not rule.matches("")
        assert not rule.matches(None)  # type: ignore[arg-type]


class TestEngineEvaluate:
    def test_no_match_allows_plain(self):
        rules = [make_rule(pattern="danger")]
        verdict = evaluate(["benign text"], rules, ruleset_id="sha256:abc")
        assert verdict.action == "ALLOW"
        assert verdict.reason == ""
        assert verdict.steering_context == ""

    def test_deny_match_wins(self):
        rules = [make_rule(pattern="danger", correction_message="found danger")]
        verdict = evaluate(["this is danger"], rules, ruleset_id="sha256:abc")
        assert verdict.action == "DENY"
        assert verdict.reason == "found danger"
        assert verdict.ruleset_id == "sha256:abc"

    def test_allow_with_context_when_only_steering_rule_matches(self):
        rules = [
            make_rule(
                pattern="credential",
                action=RuleAction.ALLOW_WITH_CONTEXT,
                correction_message="",
                steering_context="be careful with credentials",
            )
        ]
        verdict = evaluate(["mentions credential here"], rules, ruleset_id="sha256:abc")
        assert verdict.action == "ALLOW"
        assert verdict.steering_context == "be careful with credentials"

    def test_deny_beats_allow_with_context_when_both_match(self):
        deny_rule = make_rule(id="deny1", pattern="danger", correction_message="danger found")
        steer_rule = make_rule(
            id="steer1",
            pattern="credential",
            action=RuleAction.ALLOW_WITH_CONTEXT,
            correction_message="",
            steering_context="steer text",
        )
        verdict = evaluate(["danger and credential in one text"], [deny_rule, steer_rule], ruleset_id="sha256:abc")
        assert verdict.action == "DENY"
        assert verdict.reason == "danger found"

    def test_highest_confidence_deny_wins_among_multiple(self):
        low = make_rule(id="low", pattern="danger", confidence=0.3, correction_message="low conf")
        high = make_rule(id="high", pattern="danger", confidence=0.9, correction_message="high conf")
        verdict = evaluate(["danger"], [low, high], ruleset_id="sha256:abc")
        assert verdict.reason == "high conf"
        assert verdict.confidence == 0.9

    def test_global_and_individual_rules_both_evaluated(self):
        """Simulates the union behavior: caller passes global + check-specific rules
        together, and either can fire."""
        global_rule = make_rule(id="global.secret", pattern="BEGIN PRIVATE KEY", correction_message="key material")
        prompt_rule = make_rule(id="prompt.cred", pattern="credential", correction_message="cred read")
        combined = [global_rule, prompt_rule]

        verdict_global_fires = evaluate(["-----BEGIN PRIVATE KEY-----"], combined, ruleset_id="x")
        assert verdict_global_fires.reason == "key material"

        verdict_prompt_fires = evaluate(["read credential file"], combined, ruleset_id="x")
        assert verdict_prompt_fires.reason == "cred read"

    def test_multiple_texts_evaluated_together(self):
        rule = make_rule(pattern="danger", correction_message="found danger")
        verdict = evaluate(["benign", "still benign", "now danger appears"], [rule], ruleset_id="x")
        assert verdict.action == "DENY"


class TestLoader:
    def test_loads_bundled_rules_dir(self):
        ruleset = load_rule_set()
        assert ruleset.ruleset_id.startswith("sha256:")
        assert len(ruleset.rules_for("prompt")) > 0
        assert len(ruleset.global_rules()) > 0

    def test_rules_for_includes_global_and_check_specific(self):
        ruleset = load_rule_set()
        prompt_rules = ruleset.rules_for("prompt")
        global_ids = {r.id for r in ruleset.global_rules()}
        assert global_ids.issubset({r.id for r in prompt_rules})

    def test_ruleset_id_stable_for_same_content(self):
        a = load_rule_set()
        b = load_rule_set()
        assert a.ruleset_id == b.ruleset_id

    def test_ruleset_id_changes_with_content(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "prompt.yaml").write_text(
            "rules:\n  - id: a\n    pattern: 'x'\n    action: deny\n    rule_id: a\n"
            "    correction_message: 'msg'\n"
        )
        first = load_rule_set(str(rules_dir))

        (rules_dir / "prompt.yaml").write_text(
            "rules:\n  - id: a\n    pattern: 'y'\n    action: deny\n    rule_id: a\n"
            "    correction_message: 'msg'\n"
        )
        second = load_rule_set(str(rules_dir))

        assert first.ruleset_id != second.ruleset_id

    def test_missing_check_file_yields_empty_rules(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        ruleset = load_rule_set(str(rules_dir))
        assert ruleset.rules_for("prompt") == []
