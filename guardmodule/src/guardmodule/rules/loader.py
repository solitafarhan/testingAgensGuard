"""Loads rule YAML files into Rule objects and computes a stable ruleset_id.

Each YAML file has a top-level ``rules:`` list. See
docs/guardmodule-implementation-plan.md for the schema and
src/guardmodule/rules/models.py for field validation.
"""
from __future__ import annotations

import hashlib
import os

import yaml

from guardmodule.rules.models import Rule

CHECK_FILES = {
    "global": "global.yaml",
    "prompt": "prompt.yaml",
    "tool_input": "tool_input.yaml",
    "tool_output": "tool_output.yaml",
    "transcript": "transcript.yaml",
}


class RuleSet:
    """All loaded rules, split by check type, plus a content-hash ruleset_id."""

    def __init__(self, rules_by_check: dict[str, list[Rule]], ruleset_id: str, rules_dir: str) -> None:
        self.rules_by_check = rules_by_check
        self.ruleset_id = ruleset_id
        self.rules_dir = rules_dir

    def global_rules(self) -> list[Rule]:
        return self.rules_by_check.get("global", [])

    def rules_for(self, check: str) -> list[Rule]:
        """Global rules first, then the check-specific rules (union, both apply)."""
        return self.global_rules() + self.rules_by_check.get(check, [])


def _default_rules_dir() -> str:
    """Resolve the rules directory: GUARDMODULE_CONFIG_DIR env var, else the
    bundled ./rules/ directory next to the guardmodule/ project root."""
    env_dir = os.environ.get("GUARDMODULE_CONFIG_DIR")
    if env_dir:
        return env_dir
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(project_root, "rules")


def load_rule_set(rules_dir: str | None = None) -> RuleSet:
    rules_dir = rules_dir or _default_rules_dir()

    rules_by_check: dict[str, list[Rule]] = {}
    hash_parts: list[bytes] = []

    for check, filename in sorted(CHECK_FILES.items()):
        path = os.path.join(rules_dir, filename)
        if not os.path.isfile(path):
            rules_by_check[check] = []
            continue

        with open(path, "rb") as fh:
            raw = fh.read()
        hash_parts.append(filename.encode("utf-8"))
        hash_parts.append(raw)

        doc = yaml.safe_load(raw.decode("utf-8")) or {}
        entries = doc.get("rules", []) or []

        parsed: list[Rule] = []
        for entry in entries:
            parsed.append(
                Rule(
                    id=entry["id"],
                    pattern=entry["pattern"],
                    action=entry["action"],
                    rule_id=entry.get("rule_id", entry["id"]),
                    pattern_type=entry.get("pattern_type", "regex"),
                    confidence=float(entry.get("confidence", 0.0)),
                    labels=dict(entry.get("labels", {}) or {}),
                    steering_context=entry.get("steering_context", "") or "",
                    correction_message=entry.get("correction_message", "") or "",
                    source_file=filename,
                )
            )
        rules_by_check[check] = parsed

    digest = hashlib.sha256(b"".join(hash_parts)).hexdigest()
    ruleset_id = f"sha256:{digest[:16]}"

    return RuleSet(rules_by_check=rules_by_check, ruleset_id=ruleset_id, rules_dir=rules_dir)
