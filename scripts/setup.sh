#!/usr/bin/env bash
set -euo pipefail
atelier_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$atelier_root"
echo 'Installation des dépendances Python dans .venv uniquement. Aucun paquet système.'
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements-dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation --editable .
echo 'Prêt. Lancez ./scripts/dev.sh ou utilisez la configuration VS Code « Atelier ».'
