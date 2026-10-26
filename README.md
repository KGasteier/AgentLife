# agentscope – xkcd-Screensaver für pi-Agenten

Ein Vollbild-Screensaver für Omarchy (Hyprland), der im Strichmännchen-Stil von xkcd zeigt,
was **alle laufenden pi-Agenten** gerade tun – inklusive Subagents, Tokenverbrauch,
Kontextfüllung, Kompaktierung und Fehlern.

![Demo](docs/demo.png)

## Start

| Weg | Befehl |
|---|---|
| Tastenkürzel | **SUPER + CTRL + ALT + A** (nochmal drücken = schließen) |
| Terminal | `agentscope` |
| Demo ohne Agenten | `agentscope --demo` |
| Fenster statt Vollbild | `agentscope --windowed` (nur `q`/`Esc` schließt) |
| Sparsamer | `agentscope --fps 5` |
| PNG-Vorschau | `python3 -m agentscope.snapshot out.png [--demo]` |

Beenden im Vollbild: beliebige Taste, Mausklick oder Mausbewegung (erst nach 1 s).

## Was man sieht

Jeder pi-Prozess ist ein Comic-Panel:

| Bild | Bedeutung |
|---|---|
| Figur am Schreibtisch | Hauptagent – Pose = Phase (Denkblase mit dem Prompt, Tippen, Werkzeug, Schlafen) |
| Hammer auf `>_`-Kiste / Buch / Bleistift / Megafon / Lupe | Werkzeug `bash` / `read` / `edit`·`write` / `subagent` / sonstige |
| Glas „CONTEXT“ mit Presse | Kontextfüllung; Presse drückt + „SQUEEEZE!“ = Kompaktierung läuft, „SQUISH!“ = gerade fertig |
| Tacho „TOKENS / SEC“ + fliegende Münzen | aktuelle Ausgaberate, darunter Gesamtverbrauch (in/out); „~N“ = aus Session-Logs geschätzt |
| Kurve „CONTEXT OVER TIME“ | Kontextverlauf; Sägezahn mit „squish“-Marken = Kompaktierungen |
| Kleine Figuren unten + Balken | Subagents: tanzen = arbeiten (Disco, Gangnam, Twerk, Stepptanz, Irish, YMCA, Floss, Moonwalk) / Haken = fertig / rot umgefallen = Fehler; Balken = Fortschritt |
| Brennender Laptop, „AAAAA!“ | Fehler in diesem Moment; Figur klopft an Tür „API“ = automatischer Retry |
| „OOPS COUNTER“ (Strichliste) | Anzahl Fehler (Tool-Fehler, Modellfehler, fehlgeschlagene Kompaktierung) |
| Notizblock „LAB NOTES“ | letzte Ereignisse (rot = Fehler, blau = Kompaktierung/Delegation) |

## Datenquellen

1. **pi-Erweiterung** `extension/` (Symlink in `~/.pi/agent/extensions/agentscope`): schreibt je
   pi-Prozess `$XDG_RUNTIME_DIR/agentscope/<pid>.json` (max. 4×/s, atomar). Wirkt in allen Modi
   (TUI, RPC/copi, Subagent-Kinder). Erst **neu gestartete** pi-Prozesse laden sie.
   Abschalten: `AGENTSCOPE=off`.
2. **Fallback Session-Logs** (`~/.pi/agent/sessions/**/*.jsonl`, < 15 min alt): für pi-Prozesse
   ohne Erweiterung. Panel zeigt „(from session log)“; keine Live-Tokenrate.

Schema: [docs/STATE.md](docs/STATE.md) · Konzept: [docs/SPEC.md](docs/SPEC.md) · Stand: [STATUS.md](STATUS.md)

## Installation (bereits erledigt auf diesem Rechner)

```bash
ln -sfn ~/Work/omarchy-agentscope/extension ~/.pi/agent/extensions/agentscope
ln -sfn ~/Work/omarchy-agentscope/bin/agentscope ~/.local/bin/agentscope
# ~/.config/hypr/bindings.lua:
o.bind("SUPER + CTRL + ALT + A", "Agentscope (xkcd)", "~/.local/bin/agentscope")
# ~/.config/hypr/hyprland.lua:
o.window("org.omarchy.agentscope", { fullscreen = true })
```

Abhängigkeiten: python3 mit GObject (GTK 4) und pycairo – auf Omarchy vorhanden.
Schrift: Überschriften und Blasen in [Kalam](https://fonts.google.com/specimen/Kalam) (mitgeliefert unter
`agentscope/fonts/`, SIL OFL 1.1, wird nur für den Prozess geladen). Fließtext nimmt `xkcd Script`/`Humor Sans`,
falls installiert, sonst `URW Gothic`.

## Tests

```bash
node --test tests/                       # Erweiterungslogik
python3 -m unittest discover -s tests    # Datenschicht + Rendering
```
