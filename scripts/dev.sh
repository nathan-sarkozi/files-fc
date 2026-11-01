#!/usr/bin/env bash
set -euo pipefail
atelier_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$atelier_root/.venv/bin/python" ]]; then
    echo 'Environnement absent. Lancez ./scripts/setup.sh pour préparer .venv.' >&2
    exit 1
fi
export PYTHONPATH="$atelier_root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$atelier_root/.venv/bin/python" -m atelier "$@"
