#!/usr/bin/env bash
set -euo pipefail

# scripts/run_bot.sh — run the Discord bot locally
# Loads environment variables from .env if present.

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

python -m fibz_bot.bot.main
