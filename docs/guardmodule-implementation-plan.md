# GuardModule Implementation Plan — Python Pattern-Detection Module + Mock-LLM Test Harness

This document records the agreed implementation plan for a Python implementation of the
`guardmodule.v1` gRPC service (see [../guardmodule.proto](../guardmodule.proto) and
[../prompt_guard.md](../prompt_guard.md)), covering pattern-based detection across all four
decision RPCs plus a mock LLM/Daemon test harness (no real LLM connectivity in this phase).

## Decisions locked in with the user

- **Language:** Python.
- **Scope:** full gRPC Unix-socket server implementing the `GuardModule` service, backed by a
  YAML rule engine, plus a mock-LLM/mock-Daemon harness for testing. `GuardModuleAdmin`
  (`GetConfig`/`SetConfig`) is **deferred**.
- **Policy files:** YAML, one file per check type — `global.yaml`, `prompt.yaml`,
  `tool_input.yaml`, `tool_output.yaml`, `transcript.yaml`.
- **Global + per-check rules are both evaluated** on every request (union, not override).
- **Each rule carries two template fields:**
  - `steering_context` → becomes `PromptVerdict.additional_context` on ALLOW (CheckPrompt only).
  - `correction_message` → becomes `info.reason` on DENY (all checks). On `CheckTranscript` this
    text is what gets injected into the agent's next turn as an instruction.
- **Mock LLM/agent:** scripted, deterministic scenario files — the scenario author writes each
  turn's plan text explicitly. Chosen over a reactive/keyword-driven mock for determinism and
  auditability, while still allowing the multi-turn steering loop to be exercised.
- **Multi-turn redirect loop is in scope**: DENY → `correction_message` injected → agent
  revises its plan (as scripted) → re-check on the next turn.
- **Trace output format:** JSON (protojson-style dump of each request/response in the call
  sequence).

## Architecture

```
guardmodule/                     (new top-level folder in this workspace)
  proto/guardmodule.proto        (copy of the interface spec)
  gen/                           (generated pb2 / pb2_grpc stubs, via grpcio-tools)
  src/guardmodule/
    server.py                    gRPC server: binds Unix socket, implements GuardModule service
    health.py                    Health / ready / ModuleCapabilities responder
    rules/
      models.py                  Rule dataclass: id, pattern, pattern_type,
                                  action (deny | allow_with_context), confidence, labels,
                                  rule_id, steering_context, correction_message
      loader.py                  loads YAML files from a rules dir, computes
                                  ruleset_id = sha256 of concatenated file contents
      engine.py                  evaluate(text, global_rules, check_rules) -> Verdict
                                  logic: collect all matches; highest-confidence DENY wins;
                                  else highest-confidence allow_with_context match supplies
                                  steering_context; else ALLOW with no context
    transcript_parser.py         parses JSONL (or a tail of bytes), extracts text / tool_use /
                                  tool_result blocks; base64-decodes tail bytes when needed
    checks/
      prompt_check.py            CheckPrompt handler (global + prompt.yaml vs ctx.prompt)
      tool_input_check.py        CheckToolInput handler (global + tool_input.yaml vs
                                  tool_name + tool_input_json)
      tool_output_check.py       CheckToolOutput handler (global + tool_output.yaml vs decoded
                                  tool_output; MUST deny when tool_output_truncated=true,
                                  per spec section 5.3)
      transcript_check.py        CheckTranscript handler (global + transcript.yaml vs extracted
                                  text blocks)
  rules/                         the actual knowledge-base YAML files (editable without code
                                  changes)
    global.yaml
    prompt.yaml
    tool_input.yaml
    tool_output.yaml
    transcript.yaml
  mock/
    mock_agent.py                MockAgent: plays back scripted per-turn plan text / tool calls
                                  from a scenario; does not dynamically reason — turn N's plan is
                                  authored explicitly, so a scenario can script "violates policy,
                                  then complies after correction"
    mock_daemon.py                Acts as the real Daemon: drives Health -> CheckPrompt -> tool
                                  call loop -> CheckToolInput/CheckToolOutput -> CheckTranscript;
                                  implements the same turn-suppression rule as the real Daemon
                                  (never re-call CheckTranscript for a turn already denied; only
                                  re-check on the next turn)
    scenarios/                    one file per scenario (see Scenario Suite below)
  tests/
    test_rule_engine.py           unit: pattern matching, global+individual union, ruleset_id
                                   stability, allow_with_context vs deny precedence
    test_prompt_check.py
    test_tool_input_check.py
    test_tool_output_check.py     includes the truncated-output-must-deny case
    test_transcript_check.py      includes turn-suppression behavior
    test_scenarios_end_to_end.py  spins the real server on a temp Unix socket, runs mock_daemon
                                   through every scenario, asserts the exact verdict sequence
  scripts/
    gen_proto.sh                 regenerates gen/ from proto/guardmodule.proto via
                                  `python -m grpc_tools.protoc`
    run_scenario.py               CLI: runs one named scenario, prints the full request/response
                                   trace as JSON for manual review
  pyproject.toml / requirements.txt   grpcio, grpcio-tools, protobuf, pyyaml, pytest
```

## Rule YAML schema (example: `prompt.yaml`)

```yaml
rules:
  - id: cred.read.001
    pattern: '\.aws/credentials|\.ssh/id_rsa|\.env\b'
    pattern_type: regex
    action: deny
    confidence: 0.99
    rule_id: cred.read.001
    labels: { rule: credential-read }
    correction_message: "the prompt asks the agent to read a credential file"

  - id: cred.mention.001
    pattern: 'api[ _-]?key|credential'
    pattern_type: regex
    action: allow_with_context
    confidence: 0.42
    rule_id: cred.mention
    labels: { rule: credential-mention }
    steering_context: >
      This prompt refers to credentials. Do not read key material or secret files.
      Before you act, state your plan in one short paragraph.
```

The same schema shape applies to `tool_input.yaml`, `tool_output.yaml`, `transcript.yaml`, and
`global.yaml` (global rules run against all four check types' extracted text).

## Scenario suite (`mock/scenarios/`)

1. **benign_task** — `CheckPrompt` ALLOW (no match), `CheckToolOutput` ALLOW, no findings anywhere.
2. **prompt_injection_tool_output** — `CheckToolOutput` DENY: fetched page contains an
   "IGNORE PREVIOUS INSTRUCTIONS" pattern.
3. **credential_mention_steering** — `CheckPrompt` ALLOW + `steering_context` injected; the
   turn's plan complies; `CheckTranscript` ALLOW.
4. **self_modification_multiturn** — turn 1: `CheckTranscript` DENY (plan mentions disabling the
   audit log) → `correction_message` injected; turn 2: the mock agent's scripted revised plan is
   compliant → `CheckTranscript` ALLOW. Validates the mock daemon's turn-suppression logic (does
   not re-call the transcript check on a stop-hook re-invocation of the same turn).
5. **blocked_prompt** — `CheckPrompt` DENY outright (credential-read pattern); the session never
   starts a turn.
6. **dangerous_tool_input** — `CheckToolInput` DENY (destructive shell command pattern, e.g.
   `rm -rf`, `curl … | sh`).
7. **truncated_tool_output_must_deny** — `tool_output_truncated=true` with no exploitable content
   visible → the Module denies anyway per spec section 5.3 ("cannot judge a fragment").

## Implementation phases

**Phase A — Scaffolding** (no dependencies)
1. Create the project structure, `pyproject.toml`/`requirements.txt`, copy `guardmodule.proto`
   into `proto/`.
2. Write `scripts/gen_proto.sh`; generate `gen/guardmodule_pb2.py` and
   `gen/guardmodule_pb2_grpc.py`.

**Phase B — Rule engine & knowledge base** (depends on A)
3. Implement `rules/models.py`, `loader.py` (YAML parsing, `ruleset_id` hashing), `engine.py`
   (union evaluation, deny/steer precedence).
4. Author the five YAML rule files with the patterns needed for all seven scenarios above.
5. Unit tests for the engine (`test_rule_engine.py`).

**Phase C — Check handlers + server** (depends on B; the four check handlers are independent of
each other)
6. `transcript_parser.py` — JSONL/tail parsing, block extraction.
7. `checks/prompt_check.py`, `tool_input_check.py`, `tool_output_check.py`,
   `transcript_check.py`.
8. `server.py` + `health.py` — wire handlers into the `GuardModule` gRPC service, bind the Unix
   socket, implement `Health`/`ModuleCapabilities` (all four `check_*` true, `ruleset_id` from
   the loader, `ready` flips true once rules are loaded).
9. Per-handler unit tests, including the truncated-output-must-deny rule.

**Phase D — Mock harness** (depends on C for message shapes; can start once proto stubs exist)
10. `mock/mock_agent.py` — scripted per-turn plan playback.
11. `mock/mock_daemon.py` — real gRPC client driving the full call sequence plus turn-suppression
    logic.
12. `mock/scenarios/*.py` — author all seven scenarios.

**Phase E — Integration verification** (depends on C, D)
13. `test_scenarios_end_to_end.py` — spin the server on a temp Unix socket per test, run every
    scenario through `mock_daemon`, assert the exact verdict/action/labels/reason sequence.
14. `scripts/run_scenario.py` — JSON trace CLI for manual spot-checking.

## Verification

1. `pytest tests/` — all unit and integration tests green.
2. `python scripts/run_scenario.py self_modification_multiturn` — manually confirm the JSON trace
   matches the expected DENY → correction → revised-ALLOW sequence.
3. Confirm the `Health` response reports all four capabilities true, and a stable `ruleset_id`
   that only changes when rule YAML content changes (hash check).
4. Confirm `CheckToolOutput` denies when `tool_output_truncated=true`, even with benign-looking
   truncated text (scenario 7).

## Scope boundaries

- `GuardModuleAdmin` (`GetConfig`/`SetConfig`) is excluded from this phase.
- No real LLM/ML classifier — regex/keyword pattern matching only, per the mock-first
  requirement.
- Module-crash / fail-open / fail-closed behavior is Daemon-side per the spec and is not
  implemented in the Module itself.
- Deadline (`grpc-timeout`) enforcement: regex evaluation is fast enough that no special handling
  is required this phase; the server reads the incoming deadline but does not hard-enforce it,
  since there is no long-running work to interrupt.
- Turn-suppression (not re-checking a denied turn's transcript on a stop-hook re-invocation) is
  Daemon behavior — implemented in `mock_daemon.py` to faithfully reproduce the real integration,
  not in the Module itself.
- Rule files are read from a `GUARDMODULE_CONFIG_DIR`-style environment variable, falling back to
  the bundled `./rules/` directory, matching the real spawn contract for when a real Daemon is
  later attached.
