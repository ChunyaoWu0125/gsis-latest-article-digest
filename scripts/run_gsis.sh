#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m gsis_notifier --project-root "$PROJECT_ROOT"
fi
exec python3 -m gsis_notifier --project-root "$PROJECT_ROOT"
