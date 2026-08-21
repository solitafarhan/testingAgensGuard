#!/usr/bin/env bash
# Regenerates gen/guardmodule_pb2.py and gen/guardmodule_pb2_grpc.py from proto/guardmodule.proto.
set -euo pipefail
cd "$(dirname "$0")/.."

python -m grpc_tools.protoc \
  -I proto \
  --python_out=gen \
  --grpc_python_out=gen \
  --pyi_out=gen \
  proto/guardmodule.proto

echo "Generated gen/guardmodule_pb2.py and gen/guardmodule_pb2_grpc.py"
