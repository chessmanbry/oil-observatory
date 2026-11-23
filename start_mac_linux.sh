#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import yaml' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
printf 'Open http://localhost:8501 in your browser.\n'
exec .venv/bin/python serve.py
