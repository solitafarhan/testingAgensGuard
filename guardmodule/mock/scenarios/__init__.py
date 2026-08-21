"""Registry of all mock scenarios, keyed by name."""
from __future__ import annotations

from mock.mock_agent import Scenario
from mock.scenarios import (
    benign_task,
    blocked_prompt,
    credential_mention_steering,
    dangerous_tool_input,
    prompt_injection_tool_output,
    self_modification_multiturn,
    truncated_tool_output_must_deny,
)

SCENARIOS: dict[str, Scenario] = {
    benign_task.SCENARIO.name: benign_task.SCENARIO,
    prompt_injection_tool_output.SCENARIO.name: prompt_injection_tool_output.SCENARIO,
    credential_mention_steering.SCENARIO.name: credential_mention_steering.SCENARIO,
    self_modification_multiturn.SCENARIO.name: self_modification_multiturn.SCENARIO,
    blocked_prompt.SCENARIO.name: blocked_prompt.SCENARIO,
    dangerous_tool_input.SCENARIO.name: dangerous_tool_input.SCENARIO,
    truncated_tool_output_must_deny.SCENARIO.name: truncated_tool_output_must_deny.SCENARIO,
}
