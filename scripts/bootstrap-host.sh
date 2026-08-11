#!/usr/bin/env bash
set -euo pipefail
echo "This legacy M0 bootstrap cannot provision the M1 runtime safely." >&2
echo "Use: (cd ansible && sudo ansible-playbook playbooks/site.yml)" >&2
exit 2
