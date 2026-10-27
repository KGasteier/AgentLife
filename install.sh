#!/usr/bin/env bash
# Installiert agentscope für den aktuellen Benutzer (kein sudo, startet nichts neu).
#   bash install.sh [--no-hypr]     --no-hypr: Hyprland-Konfiguration nicht anfassen
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
hypr=1; [[ "${1:-}" == --no-hypr ]] && hypr=0

python3 - <<'PY' || { echo "Fehlt: python3 mit GTK4 (python-gobject, gtk4) und pycairo. Arch: sudo pacman -S python-gobject gtk4 python-cairo" >&2; exit 1; }
import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk; import cairo
PY

mkdir -p ~/.local/bin
ln -sfn "$here/bin/agentscope" ~/.local/bin/agentscope
echo "Launcher: ~/.local/bin/agentscope"

# pi-Erweiterung (liefert Tokens/Kontext/Fehler); wird beim nächsten pi-Start geladen
if [[ -d ~/.pi/agent ]]; then
  mkdir -p ~/.pi/agent/extensions
  ln -sfn "$here/extension" ~/.pi/agent/extensions/agentscope
  echo "pi-Erweiterung: ~/.pi/agent/extensions/agentscope (gilt ab dem nächsten pi-Start oder /reload)"
else
  echo "Hinweis: ~/.pi/agent fehlt – ohne pi gibt es nur Claude-Code-/Codex-Logs und --demo."
fi

if [[ $hypr == 1 && -f ~/.config/hypr/bindings.lua ]]; then
  if ! grep -q 'Agentscope (xkcd)' ~/.config/hypr/bindings.lua; then
    cp ~/.config/hypr/bindings.lua ~/.config/hypr/bindings.lua.bak.agentscope.$(date +%s)
    printf '\n-- agentscope: xkcd-Screensaver (Zweiter Druck schließt ihn wieder)\no.bind("SUPER + Z", "Agentscope (xkcd)", "~/.local/bin/agentscope")\n' >> ~/.config/hypr/bindings.lua
    echo "Keybind SUPER + Z eingetragen (Sicherung .bak.agentscope.*)"
  fi
  if ! grep -q 'org.omarchy.agentscope' ~/.config/hypr/hyprland.lua; then
    cp ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.lua.bak.agentscope.$(date +%s)
    printf '\n-- agentscope: Vollbild\no.window("org.omarchy.agentscope", { fullscreen = true })\no.window("org.omarchy.agentscope", { float = true })\n' >> ~/.config/hypr/hyprland.lua
    echo "Fensterregel eingetragen"
  fi
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
fi
echo "Test:  ~/.local/bin/agentscope --demo --windowed"
