#!/usr/bin/env bash
set -euo pipefail

# scripts/format.sh — apply linters/formatters

ruff --fix .
black .
