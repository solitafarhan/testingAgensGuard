#!/usr/bin/env python
"""CLI: run one named mock scenario against a real GuardModule server and
print the full request/response trace as JSON.

Usage:
    python scripts/run_scenario.py <scenario_name>
    python scripts/run_scenario.py --list
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Allow running this script directly (python scripts/run_scenario.py) by
# putting the guardmodule/ root — not scripts/ — on sys.path, so `guardmodule`,
# `mock`, and `mock.scenarios` are all importable regardless of invocation style.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import grpc  # noqa: E402

from guardmodule.server import create_server  # noqa: E402
from guardmodule.transport import client_target, server_bind_target  # noqa: E402
from mock.mock_daemon import MockDaemon  # noqa: E402
from mock.scenarios import SCENARIOS  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    if sys.argv[1] == "--list":
        for name, scenario in sorted(SCENARIOS.items()):
            print(f"{name}: {scenario.description}")
        return 0

    scenario_name = sys.argv[1]
    scenario = SCENARIOS.get(scenario_name)
    if scenario is None:
        print(f"unknown scenario: {scenario_name!r}", file=sys.stderr)
        print("available scenarios:", ", ".join(sorted(SCENARIOS)), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        socket_path = str(Path(tmp_dir) / "guardmodule.sock")
        server, bound_port = create_server(server_bind_target(socket_path))
        server.start()
        try:
            channel = grpc.insecure_channel(client_target(socket_path, bound_port))
            daemon = MockDaemon(channel)
            trace = daemon.run_scenario(scenario)
        finally:
            server.stop(None)

    output = {
        "scenario": scenario.name,
        "description": scenario.description,
        "trace": [entry.to_dict() for entry in trace],
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
