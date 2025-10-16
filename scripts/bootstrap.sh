#!/usr/bin/env bash
set -euo pipefail

# scripts/bootstrap.sh — one-time/setup-or-repo-clone script

python -m pip install --upgrade pip
pip install -e ".[dev]"

# Optional: install pre-commit hooks if you use pre-commit (uncomment when configured)
# pre-commit install

echo "[bootstrap] Dev environment ready."
echo "[bootstrap] Next steps:"
echo "  - ruff --fix . && black ."
echo "  - mypy fibz_bot"
echo "  - pytest -q"
