#!/usr/bin/env bash
set -euo pipefail
folder=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
chmod +x "$folder/SPY-Pesos" "$folder/launch_weights.sh"
# Escape the absolute filename according to Desktop Entry Exec quoting rules.
launcher="$folder/launch_weights.sh"
launcher=${launcher//\\/\\\\}
launcher=${launcher//\"/\\\"}
launcher=${launcher//\$/\\\$}
launcher=${launcher//\`/\\\`}
launcher=${launcher//%/%%}
printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=Actualizar pesos SPY' \
  "Exec=bash \"$launcher\"" 'Terminal=true' 'Icon=utilities-terminal' \
  > "$folder/Actualizar-pesos.desktop"
chmod +x "$folder/Actualizar-pesos.desktop"
printf '%s\n' "Lanzador creado: $folder/Actualizar-pesos.desktop"
