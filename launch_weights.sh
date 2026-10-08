#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
status=0
./SPY-Pesos || status=$?
read -r -p 'Presioná Enter para cerrar…' || true
exit "$status"
