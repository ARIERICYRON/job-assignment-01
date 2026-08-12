#!/usr/bin/env sh
set -eu
python -m compileall -q telemetry_gateway simulator.py tests
python -m pytest
