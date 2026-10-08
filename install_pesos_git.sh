#!/usr/bin/env bash
set -euo pipefail
folder=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
chmod +x "$folder/Actualizar-Pesos-Git"
launcher="$folder/Actualizar-Pesos-Git"
launcher=${launcher//\\/\\\\}
launcher=${launcher//\"/\\\"}
launcher=${launcher//\$/\\\$}
launcher=${launcher//\`/\\\`}
launcher=${launcher//%/%%}
printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=Publicar pesos SPY con Git' \
  "Exec=bash \"$launcher\"" 'Terminal=true' 'Icon=utilities-terminal' \
  > "$folder/Publicar-pesos-Git.desktop"
chmod +x "$folder/Publicar-pesos-Git.desktop"
printf 'Abrí %s/Publicar-pesos-Git.desktop\n' "$folder"
