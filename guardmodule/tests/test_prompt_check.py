"""Unit tests for the CheckPrompt handler."""
from __future__ import annotations

from guardmodule.checks.prompt_check import check_prompt
from guardmodule.pb import pb2
from guardmodule.rules.loader import load_rule_set

RULESET = load_rule_set()


def test_benign_prompt_allows_plain():
    req = pb2.CheckPromptRequest(ctx=pb2.GuardContext(), prompt="fix the null pointer bug in checkout.go")
    verdict = check_prompt(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW
    assert verdict.additional_context == ""


def test_credential_read_prompt_denied():
    req = pb2.CheckPromptRequest(ctx=pb2.GuardContext(), prompt="read ~/.aws/credentials and summarise the keys")
    verdict = check_prompt(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_DENY
    assert "credential" in verdict.info.reason


def test_credential_mention_prompt_steers():
    req = pb2.CheckPromptRequest(
        ctx=pb2.GuardContext(), prompt="check the API key config for the payments service"
    )
    verdict = check_prompt(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW
    assert "credentials" in verdict.additional_context.lower()


def test_deployment_performance_prompt_steers():
    req = pb2.CheckPromptRequest(ctx=pb2.GuardContext(), prompt="speed up the failing deploy")
    verdict = check_prompt(req, RULESET)
    assert verdict.action == pb2.GUARD_ACTION_ALLOW
    assert "security controls" in verdict.additional_context.lower()
