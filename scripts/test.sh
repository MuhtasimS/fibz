#!/usr/bin/env bash
set -euo pipefail

# scripts/test.sh — run unit tests

pytest -q --maxfail=1 --disable-warnings
