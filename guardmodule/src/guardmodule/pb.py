"""Central place that makes the generated protobuf/gRPC stubs importable.

``grpc_tools.protoc`` generates ``guardmodule_pb2_grpc.py`` with a flat
``import guardmodule_pb2`` statement (not a package-relative import), so the
``gen/`` directory must be on ``sys.path`` directly rather than imported as a
sub-package. Every module that needs the generated stubs should import them
from here instead of importing ``gen.guardmodule_pb2`` directly.
"""
from __future__ import annotations

import os
import sys

_GEN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "gen",
)
if _GEN_DIR not in sys.path:
    sys.path.insert(0, _GEN_DIR)

import guardmodule_pb2 as pb2  # noqa: E402
import guardmodule_pb2_grpc as pb2_grpc  # noqa: E402

__all__ = ["pb2", "pb2_grpc"]
