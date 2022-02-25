#!/usr/bin/env bash
#
# Wrapper script for running pol2dom without installing it in the system.

export PYTHONPATH
PYTHONPATH="$(dirname "$(dirname "$(readlink -f "$0")")"):$PYTHONPATH"
exec python -m p2d.main "$@"
