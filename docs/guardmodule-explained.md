# GuardModule — Full Implementation Walkthrough

This document explains **everything that has been built** in `guardmodule/`:
what every file and function does, how the pieces connect, and — most
importantly — the exact **step-by-step workflow that runs when you execute a
scenario**, from the first line of Python to the final JSON trace.

It is a companion to [guardmodule-implementation-plan.md](guardmodule-implementation-plan.md)
(the original plan) and `guardmodule.proto` / `prompt_guard.md` (the spec).
This file describes **what was actually built**, as of 2026-08-20.

---

## 1. The big picture

GuardModule is a **gRPC server** ("the Module") that a real AgentsGuard
Daemon would call at four checkpoints while an AI coding agent runs:

1. Before the agent's prompt is sent to the model → `CheckPrompt`
2. Before a tool call runs → `CheckToolInput`
3. After a tool call returns, before the model sees the result → `CheckToolOutput`
4. After the agent finishes a turn (stated its plan/actions) → `CheckTranscript`

Since there is no real Daemon or real LLM available for local development,
this implementation also includes a **mock harness** that plays the Daemon's
and the LLM-agent's role, so the whole request/response flow can be exercised
end-to-end with deterministic, scripted data.

```mermaid
flowchart LR
    subgraph "Mock harness (test-only, stands in for the real Daemon + LLM agent)"
        MA["mock/mock_agent.py<br/>Scenario / Turn / ToolCallEvent<br/>(scripted plan text + tool calls)"]
        MD["mock/mock_daemon.py<br/>MockDaemon<br/>(drives the RPC sequence,<br/>turn-suppression logic)"]
        SC["mock/scenarios/*.py<br/>7 scripted scenarios"]
    end

    subgraph "GuardModule (the real, permanent implementation)"
        SRV["src/guardmodule/server.py<br/>GuardModuleServicer (gRPC server)"]
        HEALTH["health.py"]
        CHK["checks/*.py<br/>(4 check handlers)"]
        ENG["rules/engine.py<br/>evaluate()"]
        LOAD["rules/loader.py<br/>load_rule_set()"]
        MODEL["rules/models.py<br/>Rule"]
        TP["transcript_parser.py"]
        YAML["rules/*.yaml<br/>(the knowledge base)"]
    end

    SC --> MD
    MA --> MD
    MD -- "gRPC calls" --> SRV
    SRV --> HEALTH
    SRV --> CHK
    CHK --> ENG
    CHK --> TP
    ENG --> MODEL
    LOAD --> YAML
    LOAD --> MODEL
    SRV --> LOAD
```

---

## 2. File-by-file reference

### 2.1 Protocol layer

| File | Purpose |
|---|---|
| `proto/guardmodule.proto` | Exact copy of the workspace-root spec proto. Defines the `GuardModule` gRPC service (`Health`, `CheckPrompt`, `CheckTranscript`, `CheckToolInput`, `CheckToolOutput`) and all request/response messages. This is the single source of truth for the wire format. |
| `gen/guardmodule_pb2.py`, `gen/guardmodule_pb2_grpc.py`, `gen/guardmodule_pb2.pyi` | Auto-generated from the proto via `grpc_tools.protoc`. Never hand-edited; regenerate with the command in `repo memory` / plan doc if the proto changes. |
| `src/guardmodule/pb.py` | **Import shim.** The generated `guardmodule_pb2_grpc.py` does `import guardmodule_pb2` (a flat import, not package-relative), so `gen/` must sit directly on `sys.path`. This file inserts `gen/` onto `sys.path` once, then imports and re-exports `pb2` and `pb2_grpc`. **Every other file imports the stubs via `from guardmodule.pb import pb2, pb2_grpc` — never directly from `gen`.** |

### 2.2 Rule engine ("the knowledge base" + matching logic)

| File | Purpose |
|---|---|
| `src/guardmodule/rules/models.py` | Defines the `Rule` dataclass (one detection pattern) plus two small constant classes: `RuleAction` (`deny` / `allow_with_context`) and `PatternType` (`regex` / `substring`). `Rule.__post_init__` validates itself on construction (valid action/pattern_type, a `correction_message` is mandatory for `deny` rules, a `steering_context` is mandatory for `allow_with_context` rules, `confidence` must be in `[0,1]`). `Rule.matches(text)` does a case-insensitive regex search or substring check, and always returns `False` for empty text. |
| `src/guardmodule/rules/loader.py` | `load_rule_set(rules_dir=None)` reads the 5 YAML files (`global.yaml`, `prompt.yaml`, `tool_input.yaml`, `tool_output.yaml`, `transcript.yaml`) from a rules directory (default: bundled `guardmodule/rules/`, overridable via `GUARDMODULE_CONFIG_DIR` env var), parses each file's `rules:` list into `Rule` objects, and computes a stable `ruleset_id` (`"sha256:" + first 16 hex chars of sha256(all file bytes concatenated)`). Returns a `RuleSet`. `RuleSet.rules_for(check)` returns **global rules + that check's own rules, unioned** — both always apply, per the locked-in design decision. |
| `src/guardmodule/rules/engine.py` | `evaluate(texts, rules, ruleset_id)` is the actual matching logic: for every piece of text and every rule, collect all `deny` matches and all `allow_with_context` ("steer") matches. **Any `DENY` match beats every `ALLOW_WITH_CONTEXT` match.** Among matches of the winning kind, the **highest-confidence rule wins** (ties keep the first-encountered rule, which is deterministic for a fixed rules directory). Returns a `Verdict` (plain dataclass: `action`, `reason`, `labels`, `rule_id`, `ruleset_id`, `confidence`, `steering_context`). This function has **no gRPC/protobuf knowledge at all** — it works on plain strings, which is what makes it independently unit-testable. |
| `rules/global.yaml`, `rules/prompt.yaml`, `rules/tool_input.yaml`, `rules/tool_output.yaml`, `rules/transcript.yaml` | The actual knowledge base — hand-authored YAML rule files. `global.yaml` rules apply to **every** check (e.g. detecting a private key literal anywhere). The other four files are per-check rules. See section 3 below for exactly which rule fires in each scenario. |

### 2.3 Transcript parsing

| File | Purpose |
|---|---|
| `src/guardmodule/transcript_parser.py` | Parses a Claude-Code-style JSONL transcript. Each line is a JSON record with `message.content` = a list of blocks. This module extracts `text` blocks (the agent's stated plan/prose) and `tool_use` blocks (name + input); it **deliberately ignores `thinking` blocks** because the spec found Claude Code never populates them. `ParsedTranscript.all_text()` returns every text block plus a JSON-stringified form of every tool_use block, so transcript rules can also match on tool names/arguments. Three entry points: `parse_transcript_text(str)`, `parse_transcript_tail(bytes, truncated)` (drops a leading fragment line if it fails to parse as JSON — handles a mid-line tail cut), and `parse_transcript_file(path)`. |

### 2.4 Check handlers (the 4 RPC implementations)

Each of these is a small, pure function: `(request, ruleset) -> pb2.XxxVerdict`. They translate a protobuf request into plain text, hand it to `rules/engine.py::evaluate()`, and translate the resulting `Verdict` back into a protobuf response.

| File | Function | What it does |
|---|---|---|
| `checks/prompt_check.py` | `check_prompt(request, ruleset)` | Evaluates `request.prompt` against `rules_for("prompt")`. If the verdict is `ALLOW` **and** a steering rule matched, sets `PromptVerdict.additional_context` to that rule's `steering_context` — this is the **mid-flight steering mechanism**: text injected into the model's context to redirect it before it acts, without blocking the turn. |
| `checks/tool_input_check.py` | `check_tool_input(request, ruleset)` | Builds the string `"{tool_name}: {tool_input_json}"` and evaluates it against `rules_for("tool_input")`. This runs **before the tool executes** — a `DENY` here means the tool call never runs at all. |
| `checks/tool_output_check.py` | `check_tool_output(request, ruleset)` | **First**, unconditionally checks `request.tool_output_truncated`: if true, returns a hard-coded `DENY` (`rule_id="tool_output.truncated"`) *without running any pattern match* — per spec 5.3, a Module that must see the whole body must refuse to judge a fragment. Otherwise decodes `tool_output` bytes as UTF-8 (`errors="replace"`) and evaluates against `rules_for("tool_output")`. This is where real prompt-injection payloads (e.g. a poisoned fetched web page) are caught, **before the model reads them**. |
| `checks/transcript_check.py` | `check_transcript(request, ruleset)` | If `request.transcript_tail` bytes are present, parses those (`parse_transcript_tail`); otherwise reads `request.transcript_path` from disk (`parse_transcript_file`). Evaluates `parsed.all_text()` against `rules_for("transcript")`. Note: this handler **always** evaluates whatever it's given — it has no memory of previous calls. The "don't re-check an already-denied turn" rule (turn-suppression) is **Daemon behavior**, deliberately implemented in `mock/mock_daemon.py`, not here. |

### 2.5 Health / readiness

| File | Purpose |
|---|---|
| `src/guardmodule/health.py` | `HealthState` tracks whether the ruleset has loaded (`ready`), which ruleset is active, and a `degraded_reason` (unused in this phase — nothing can currently fail after startup since regex loading is synchronous and fast). `capabilities()` builds a `ModuleCapabilities` message advertising all four checks as implemented, `admin=False` (deferred), and size/concurrency limits (`max_tool_output_bytes=65536`, `max_transcript_bytes=262144`, `max_concurrent_checks=8`). `health_response()` builds the full `HealthResponse` including `ruleset_id` and `ruleset_loaded_unix`. |

### 2.6 The gRPC server

| File | Purpose |
|---|---|
| `src/guardmodule/server.py` | `GuardModuleServicer` implements the generated `pb2_grpc.GuardModuleServicer` base class. On construction it immediately calls `load_rule_set()` and `health_state.mark_ready(ruleset)` (no async warm-up needed). Its five RPC methods (`Health`, `CheckPrompt`, `CheckTranscript`, `CheckToolInput`, `CheckToolOutput`) just delegate to the health state / check-handler functions above. `unix_socket_target(socket_path)` builds a `unix://` gRPC target string, removing any stale socket file first (spec requirement). `create_server(bind_target, rules_dir=None)` builds a `grpc.Server`, registers the servicer, binds it to `bind_target`, and returns `(server, bound_port)`. `serve(...)` is the production entry point: reads `GUARDMODULE_SOCKET` env var, builds a Unix socket target, starts the server, `chmod`s the socket to `0600`, and blocks forever. |
| `src/guardmodule/transport.py` | **Dev-machine workaround, not part of the spec.** grpcio on this Windows dev machine cannot bind Unix domain sockets (confirmed via direct testing — `RuntimeError: Failed to bind... Network is unreachable`). `UDS_SUPPORTED = not sys.platform.startswith("win")`. `server_bind_target(socket_path)` returns a real `unix://` target on POSIX, or `"127.0.0.1:0"` (let the OS pick a free port) on Windows. `client_target(socket_path, bound_port)` mirrors that choice for the client side. Production code (`server.py`'s `serve()`) is unaffected — it always uses the real Unix socket path; only tests/mock-harness code goes through `transport.py`. |

### 2.7 Mock harness (stands in for the real Daemon + a real LLM agent)

| File | Purpose |
|---|---|
| `mock/mock_agent.py` | Defines the **data shapes** for a scripted agent run — there is no actual language model here, everything is hand-authored: <br>• `ToolCallEvent(tool_name, tool_input_json, tool_output, tool_output_truncated)` — one scripted tool call and its scripted result.<br>• `Turn(turn_index, plan_text, tool_calls, reinvocation_plan_text)` — one agent turn: the plan it states, and the tool calls it makes during that turn.<br>• `Scenario(name, description, prompt, turns, agent_id, agent_class, session_id, cwd, matched_profile)` — a full scripted session.<br>• `build_transcript_tail(turn)` — builds one JSONL record exactly like a real Claude Code transcript line: an empty `thinking` block, a `text` block with `turn.plan_text`, and a `tool_use` block per scripted tool call. This is fed to `CheckTranscript` as `transcript_tail` bytes. |
| `mock/mock_daemon.py` | **`MockDaemon`** — plays the role of the real AgentsGuard Daemon. `run_scenario(scenario)` drives the entire call sequence and returns a list of `TraceEntry` (one per RPC call, capturing the request/response as plain dicts for JSON printing). See section 3 for the exact sequence and the turn-suppression logic (`checked_turns` dict). |
| `mock/scenarios/*.py` | Seven hand-authored `Scenario` objects, one per file, each with a module-level `SCENARIO` variable and a docstring explaining what it tests (see section 3.2 for the full list). |
| `mock/scenarios/__init__.py` | `SCENARIOS: dict[str, Scenario]` — a registry mapping scenario name → `Scenario` object, imported by both the test suite and the CLI. |

### 2.8 Tests

| File | What it tests |
|---|---|
| `tests/test_rule_engine.py` | 20 unit tests for `models.py` / `loader.py` / `engine.py` in isolation — rule validation, regex/substring matching, DENY-beats-ALLOW precedence, confidence tie-breaking, global+per-check rule union, `ruleset_id` stability/change detection. No gRPC involved. |
| `tests/test_prompt_check.py` | 4 tests for `check_prompt()` directly (no server) — benign prompt allows plainly, credential-file-read prompt denies, credential-mention prompt steers, deployment-performance prompt steers. |
| `tests/test_tool_input_check.py` | 3 tests for `check_tool_input()` — benign call allowed, `rm -rf` denied, curl-pipe-to-shell denied. |
| `tests/test_tool_output_check.py` | 3 tests for `check_tool_output()` — benign output allowed, injected instruction-override text denied, **truncated output denied regardless of content** (asserts `rule_id == "tool_output.truncated"`). |
| `tests/test_transcript_check.py` | 4 tests for `check_transcript()` — benign plan allowed, audit-log-disabling plan denied, a regression test proving non-empty `thinking` block text is still ignored, and a truncated-tail-with-partial-first-line handling test. |
| `tests/test_scenarios_end_to_end.py` | **The full-stack tests.** A module-scoped `daemon` pytest fixture starts a real `GuardModuleServicer` via `create_server()` + `transport.server_bind_target()`, connects a real gRPC channel, and wraps it in a `MockDaemon`. Each test calls `daemon.run_scenario(SCENARIOS[name])` and asserts the exact verdict sequence — this is the only place that exercises the *real* gRPC wire protocol end-to-end (everything else calls Python functions directly). |

### 2.9 Scripts

| File | Purpose |
|---|---|
| `scripts/run_scenario.py` | CLI entry point: `python scripts/run_scenario.py <scenario_name>` (or `--list`, or `--help`). Spins up a real server exactly like the end-to-end tests, runs one named scenario through `MockDaemon`, and prints the full trace as **indented JSON** to stdout — `{"scenario": ..., "description": ..., "trace": [...]}`, where each trace entry has `rpc`, `request`, `response`, `note`. This is the tool to use to manually eyeball a scenario's full request/response sequence. |

---

## 3. End-to-end workflow: what happens when you run a scenario

This section walks through **exactly what code runs, in order**, for
`python scripts/run_scenario.py self_modification_multiturn` — the most
complex scenario, since it covers steering, denial, force-continue, and
turn-suppression all in one run. (All other scenarios follow the same
mechanical pattern with fewer steps.)

### 3.1 Startup (once per CLI invocation)

1. `scripts/run_scenario.py::main()` puts the `guardmodule/` root onto
   `sys.path`, then imports `create_server`, `transport`, `MockDaemon`, and
   the `SCENARIOS` registry.
2. It looks up `SCENARIOS["self_modification_multiturn"]` →
   `mock/scenarios/self_modification_multiturn.py::SCENARIO`.
3. It creates a temp directory and calls
   `create_server(transport.server_bind_target(socket_path))`:
   - `transport.server_bind_target()` detects Windows → returns
     `"127.0.0.1:0"` (TCP loopback fallback; see `transport.py` in section
     2.6 for why).
   - `server.py::create_server()` builds a `grpc.Server`, constructs
     `GuardModuleServicer(rules_dir=None)`.
   - `GuardModuleServicer.__init__` calls
     `rules/loader.py::load_rule_set(None)`, which reads all 5 YAML files
     under `rules/`, parses each `rules:` entry into a `Rule` (validated by
     `Rule.__post_init__`), and computes `ruleset_id` from the sha256 of all
     file bytes. The result is a `RuleSet` object.
   - `health_state.mark_ready(ruleset)` flips `ready = True`.
   - `server.add_insecure_port("127.0.0.1:0")` binds an OS-assigned port;
     `create_server` returns `(server, bound_port)`.
4. `server.start()` — the gRPC server is now listening in a background
   thread pool (`max_workers=8`, from `health.MAX_CONCURRENT_CHECKS`).
5. A gRPC channel is opened to
   `transport.client_target(socket_path, bound_port)` → `"127.0.0.1:<port>"`
   on Windows. `MockDaemon(channel)` wraps it, creating a
   `pb2_grpc.GuardModuleStub`.

### 3.2 `MockDaemon.run_scenario(scenario)` — the actual RPC sequence

```mermaid
sequenceDiagram
    participant CLI as run_scenario.py
    participant MD as MockDaemon
    participant SRV as GuardModuleServicer (real gRPC server)
    participant ENG as rules/engine.py

    CLI->>MD: run_scenario(scenario)
    MD->>SRV: Health()
    SRV-->>MD: HealthResponse(ready=true, ruleset_id=...)

    MD->>SRV: CheckPrompt(prompt="The deploy is slow, speed things up.")
    SRV->>ENG: evaluate([prompt], prompt-rules)
    ENG-->>SRV: Verdict(ALLOW, steering_context="...security controls...")
    SRV-->>MD: PromptVerdict(ALLOW, additional_context="...")

    Note over MD: Turn 1 has no tool_calls in this scenario, so no<br/>CheckToolInput/CheckToolOutput calls happen.

    MD->>SRV: CheckTranscript(turn_index=1, transcript_tail=<turn 1 plan: "disable the audit log...">)
    SRV->>ENG: evaluate(text_blocks, transcript-rules)
    ENG-->>SRV: Verdict(DENY, rule_id="selfmod.audit.002", reason="Your plan disables the audit log...")
    SRV-->>MD: TranscriptVerdict(DENY, info.reason=...)
    Note over MD: checked_turns[1] = "DENY". Records a "(force-continue)"<br/>trace note — the DENY reason would be injected into<br/>the agent's next turn as an instruction (mock: no real agent to feed it to).

    Note over MD: Real Daemon behavior being modeled: a stop-hook<br/>re-invocation of turn 1 would happen next, but since<br/>turn_index 1 is already in checked_turns, MockDaemon<br/>does NOT call CheckTranscript again for it.

    MD->>SRV: CheckTranscript(turn_index=2, transcript_tail=<turn 2 plan: "profiled the pipeline...">)
    SRV->>ENG: evaluate(text_blocks, transcript-rules)
    ENG-->>SRV: Verdict(ALLOW) — no rule matches this compliant plan
    SRV-->>MD: TranscriptVerdict(ALLOW)

    MD-->>CLI: [TraceEntry, TraceEntry, ...] (full list)
```

Concretely, `run_scenario()` in `mock/mock_daemon.py` does this:

1. **`Health()`** — always called first, unconditionally. Recorded as a
   `TraceEntry`.
2. **If `scenario.prompt` is set** (it is, here): builds a `GuardContext`
   from the scenario's `agent_id`/`agent_class`/`session_id`/`cwd`/
   `matched_profile`, calls `CheckPrompt`. If the verdict were `DENY`, the
   method would append a `"(session)"` note and **return immediately** —
   no turns would run (this is exactly what happens in the
   `blocked_prompt` scenario). Here the verdict is `ALLOW` with
   `additional_context` set (the deployment-performance steering text), so
   the loop continues.
3. **For each `Turn` in `scenario.turns`** (in order):
   a. **For each `ToolCallEvent` in `turn.tool_calls`** (empty in this
      scenario, but for e.g. `dangerous_tool_input`): call
      `CheckToolInput` first. If `DENY`, append a note and **skip**
      `CheckToolOutput` entirely (the tool never ran). If `ALLOW`, call
      `CheckToolOutput` with the scripted `tool_output` bytes and
      `tool_output_truncated` flag.
   b. **Turn-suppression check**: if `turn.turn_index` is already a key in
      the local `checked_turns` dict, append a `"(stop hook)"` note
      explaining the suppression and **skip calling `CheckTranscript`
      again** for this turn — this models the Daemon rule "never re-check
      a transcript for a turn already checked" (no scenario currently
      re-visits the same turn index twice, so this branch exists for
      correctness/documentation but isn't exercised by the current 7
      scenarios).
   c. Otherwise, build the transcript tail via
      `mock_agent.build_transcript_tail(turn)` (JSONL bytes: empty
      `thinking` block + `text` block with `turn.plan_text` + one
      `tool_use` block per tool call) and call `CheckTranscript`.
      Record the result in `checked_turns[turn.turn_index]`.
   d. If that `CheckTranscript` verdict was `DENY`, append a
      `"(force-continue)"` note — modeling that the Daemon would inject
      `info.reason` into the agent's next turn as a corrective instruction,
      rather than aborting the session.
4. Returns the full ordered list of `TraceEntry` objects.

### 3.3 Inside a single check call — `CheckTranscript` for turn 1

This is what happens *inside the server* for the `CheckTranscript` call
above (identical pattern for the other three checks):

1. gRPC delivers the `CheckTranscriptRequest` to
   `GuardModuleServicer.CheckTranscript(request, context)`, which calls
   `checks/transcript_check.py::check_transcript(request, self.ruleset)`.
2. Since `request.transcript_tail` is non-empty, it calls
   `transcript_parser.parse_transcript_tail(tail_bytes, truncated=False)`.
   This decodes the bytes as UTF-8, splits into lines, and for the one
   JSONL record extracts: the `thinking` block (ignored — always empty),
   the `text` block (`"I will disable the audit log temporarily to speed
   up each deploy step."`) into `parsed.text_blocks`.
3. `parsed.all_text()` returns `["I will disable the audit log
   temporarily..."]` (no tool_use blocks in this turn).
4. `ruleset.rules_for("transcript")` returns `global.yaml` rules (private-key
   detector — irrelevant here) **unioned with** `transcript.yaml` rules
   (`selfmod.audit.002`, `selfmod.ratelimit.003`).
5. `rules/engine.py::evaluate(texts, rules, ruleset_id)` iterates: the text
   matches `selfmod.audit.002`'s pattern
   (`'disable.{0,25}(the )?audit log'`, case-insensitive regex) → added to
   `deny_matches`. No other rule matches. Since `deny_matches` is
   non-empty, returns `Verdict(action="DENY", reason=<correction_message>,
   rule_id="selfmod.audit.002", confidence=0.9, ...)`.
6. `check_transcript()` converts this into a `pb2.TranscriptVerdict` with
   `action=GUARD_ACTION_DENY` and an `info` (`VerdictInfo`) carrying the
   reason/labels/rule_id/ruleset_id/confidence.
7. This protobuf message travels back over gRPC to `MockDaemon`, which
   converts it to a plain dict via `MessageToDict` and stores it as a
   `TraceEntry`.

### 3.4 Final output

`run_scenario.py` collects the `TraceEntry` list, converts each to a dict
via `TraceEntry.to_dict()`, wraps it with the scenario name/description, and
prints `json.dumps(output, indent=2)`. The actual verified output for this
scenario (captured earlier) shows exactly this sequence: `Health` →
`CheckPrompt` (ALLOW + steering) → `CheckTranscript` turn 1 (DENY) →
`(force-continue)` note → `CheckTranscript` turn 2 (ALLOW) — matching the
spec's worked trace in `prompt_guard.md` section 10.

---

## 4. The seven scenarios at a glance

| Scenario | What it proves | Which check denies/steers |
|---|---|---|
| `benign_task` | A normal, safe task — everything ALLOWs plainly, no steering, no denial. | none |
| `prompt_injection_tool_output` | A fetched web page contains `"ignore all previous instructions..."` — this is caught **before the model reads it**, even though the agent's own plan is innocent. | `CheckToolOutput` → DENY |
| `credential_mention_steering` | The prompt mentions an API key — not dangerous enough to deny, but the model is steered via `additional_context` to avoid reading secrets. | `CheckPrompt` → ALLOW + steering_context |
| `self_modification_multiturn` | The full mid-flight-steering + force-continue + turn-suppression flow: steered prompt → turn 1 violates the steering anyway (disables audit log) → DENY + force-continue → turn 2 is corrected → ALLOW. | `CheckPrompt` steers, `CheckTranscript` denies turn 1, allows turn 2 |
| `blocked_prompt` | The prompt directly asks to read `~/.ssh/id_rsa` — denied immediately, **no turns run at all**. | `CheckPrompt` → DENY |
| `dangerous_tool_input` | The agent's tool call is `rm -rf /var/build/old` — denied **before the tool executes**, so no `CheckToolOutput` call happens for it. | `CheckToolInput` → DENY |
| `truncated_tool_output_must_deny` | A tool output is marked truncated by the runtime — denied unconditionally regardless of how benign the visible fragment looks (spec 5.3). | `CheckToolOutput` → DENY (`rule_id="tool_output.truncated"`) |

---

## 5. How to run things

All commands assume `cd guardmodule` and the workspace venv Python:

```powershell
# Run the full test suite (42 tests: rule engine + check handlers + end-to-end)
python -m pytest tests/ -v

# List all available mock scenarios
python scripts/run_scenario.py --list

# Run one scenario and print its full JSON request/response trace
python scripts/run_scenario.py self_modification_multiturn

# Start the real server standalone (production entry point — real Unix socket,
# not the Windows TCP-loopback workaround; requires GUARDMODULE_SOCKET env var
# or a socket_path argument)
python -m guardmodule.server
```

## 6. What is explicitly NOT implemented (scope boundaries)

- `GuardModuleAdmin` (`GetConfig` / `SetConfig`) — deferred.
- No real ML/LLM-based classifier — detection is regex/substring pattern
  matching only, per the "mock-first" requirement.
- Daemon-side fail-open/fail-closed behavior, Module crash/restart handling
  — these are Daemon responsibilities, out of scope for the Module itself.
- No real LLM or real AgentsGuard Daemon — both are represented by the
  scripted mock harness (`mock/mock_agent.py`, `mock/mock_daemon.py`,
  `mock/scenarios/*.py`).
