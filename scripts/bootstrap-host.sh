#!/usr/bin/env bash
set -euo pipefail
echo "This legacy M0 bootstrap cannot provision the M1 runtime safely." >&2
echo "Use from the repository root: make provision" >&2
exit 2
