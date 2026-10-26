# STATUS

## Stand 0.1.0
- pi-Erweiterung schreibt Live-Zustand (live geprüft: Tools, Tool-Fehler, Tokens, Kontext, parallele Subagents).
- Screensaver: Panels pro Agent, alle Phasen gezeichnet (Demo + echte Daten), Vollbild per Tastenkürzel.
- Fallback für pi-Prozesse ohne Erweiterung über Session-Logs.
- Tests: `node --test tests/` (11), `python3 -m unittest discover -s tests` (13).

## Bekannte Grenzen
- Laufende pi-Prozesse laden die Erweiterung erst nach Neustart / `/reload`; bis dahin Log-Fallback (ohne Live-Rate).
- Kompaktierung live nur über die Erweiterung gesehen (im Test nicht real ausgelöst, nur Unit-Test).
- `tokensAfter` liefert pi nicht immer → Anzeige „less“.
- CPU: ca. 45 % eines Kerns bei 10 fps in dieser VM (2880×1808, Software-Rendering). `--fps 5` halbiert das.
- Modelle ohne `contextWindow` (Log-Fallback): Füllstand wird mit 200k geschätzt („~N tokens“).

## TODO
1. Echte Kompaktierung live testen (`/compact` in einer Test-Session) und Animation prüfen.
2. Optional: Auslösung über hypridle als echter Idle-Screensaver.
3. xkcd-Schrift (xkcd Script, OFL) als optionale Installation anbieten.
