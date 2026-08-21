"""Health / readiness / ModuleCapabilities responder (spec section 8, appendix step 0).

`ready` becomes true once the RuleSet is loaded. `capabilities` advertises all
four decision RPCs as implemented; `admin` is false because GuardModuleAdmin is
deferred in this phase.
"""
from __future__ import annotations

import time

from guardmodule.pb import pb2
from guardmodule.rules.loader import RuleSet

MODULE_NAME = "guardmodule-python-mock"
MODULE_VERSION = "0.1.0"
INTERFACE_VERSION = 1

# Sizing: non-zero so the Module never has to open a user's transcript/tool-output
# file itself (spec section 5.3 recommendation).
MAX_TOOL_OUTPUT_BYTES = 65536
MAX_TRANSCRIPT_BYTES = 262144
MAX_CONCURRENT_CHECKS = 8


class HealthState:
    """Tracks readiness and the loaded ruleset so Health can report both."""

    def __init__(self) -> None:
        self.ready = False
        self.ruleset: RuleSet | None = None
        self.ruleset_loaded_unix = 0
        self.degraded_reason = ""

    def mark_ready(self, ruleset: RuleSet) -> None:
        self.ruleset = ruleset
        self.ruleset_loaded_unix = int(time.time())
        self.ready = True

    def capabilities(self) -> "pb2.ModuleCapabilities":
        return pb2.ModuleCapabilities(
            check_prompt=True,
            check_transcript=True,
            check_tool_input=True,
            check_tool_output=True,
            max_tool_output_bytes=MAX_TOOL_OUTPUT_BYTES,
            max_transcript_bytes=MAX_TRANSCRIPT_BYTES,
            max_concurrent_checks=MAX_CONCURRENT_CHECKS,
            admin=False,
        )

    def health_response(self) -> "pb2.HealthResponse":
        return pb2.HealthResponse(
            ready=self.ready,
            module_name=MODULE_NAME,
            module_version=MODULE_VERSION,
            ruleset_id=self.ruleset.ruleset_id if self.ruleset else "",
            ruleset_loaded_unix=self.ruleset_loaded_unix,
            capabilities=self.capabilities(),
            interface_version=INTERFACE_VERSION,
            degraded_reason=self.degraded_reason,
        )
