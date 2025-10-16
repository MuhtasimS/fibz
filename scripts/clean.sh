#!/usr/bin/env bash
set -euo pipefail

# scripts/clean.sh — remove caches and build artifacts

rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml dist build wheels || true
find . -type f -name "*.py[co]" -delete || true
find . -type d -name "__pycache__" -prune -exec rm -rf {} + || true
echo "[clean] Done."
