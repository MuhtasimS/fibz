#!/usr/bin/env bash
set -euo pipefail

# scripts/ci_local.sh — mirrors CI locally

bash scripts/format.sh
bash scripts/typecheck.sh
pytest -q --maxfail=1 --disable-warnings --cov=fibz_bot --cov-report=term
