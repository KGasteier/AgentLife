# STATUS

## Stand 0.3.0
- Tacho bewegt sich jetzt auch ohne Live-Datei: Rate aus den Session-Logs (Output-Tokens / Antwortdauer,
  Anzeige „~N“), Nadel geglättet. Ursache war: laufende pi-Prozesse ohne geladene Erweiterung → Log-Fallback ohne Rate.
- Hammer mit Ausholen → Halten → beschleunigtem Schlag → „bonk!“ und Rückprall; Knie federn mit.
- Lesen: Buch aufgeschlagen in Seitenansicht vor dem Gesicht, Seiten blättern um.
- Tippen: einzelne Anschläge, Hände abwechselnd, Denkpausen, gelegentlich ein beherztes Enter, leichtes Wippen.
- Subagent-Minions tanzen 8 Stile (Disco, Gangnam, Twerk, Stepptanz, Irish, YMCA, Floss, Moonwalk),
  je Minion verschieden, Wechsel alle 12 s, Noten schweben hoch.
- Schrift „kocht“ nicht mehr mit (ruhiger, besser lesbar).
- Tests: node 11, Python 29.

## Stand 0.2.0
- Kalam-Handschrift (mitgeliefert) für Überschriften, Blasen, Ausrufe.
- Blasentext wird umbrochen/verkleinert/gekürzt und bleibt sicher in der Wolke (Regressionstest).
- Figuren: realistische Proportionen, IK für Hände/Füße; sitzt auf dem Stuhl, Füße am Boden,
  Hände auf Tastatur/Buch/Kinn; Hammer trifft die Kiste.

## Stand 0.1.0
- pi-Erweiterung schreibt Live-Zustand (live geprüft: Tools, Tool-Fehler, Tokens, Kontext, parallele Subagents).
- Screensaver: Panels pro Agent, alle Phasen gezeichnet (Demo + echte Daten), Vollbild per Tastenkürzel.
- Fallback für pi-Prozesse ohne Erweiterung über Session-Logs.
- Tests: `node --test tests/` (11), `python3 -m unittest discover -s tests` (20 inkl. Zeichnen).

## Bekannte Grenzen
- Laufende pi-Prozesse laden die Erweiterung erst nach Neustart / `/reload`; bis dahin Log-Fallback
  (Rate nur geschätzt, aktualisiert sich erst nach jeder fertigen Antwort).
- Kompaktierung live nur über die Erweiterung gesehen (im Test nicht real ausgelöst, nur Unit-Test).
- `tokensAfter` liefert pi nicht immer → Anzeige „less“.
- CPU: ca. 45 % eines Kerns bei 10 fps in dieser VM (2880×1808, Software-Rendering). `--fps 5` halbiert das.
- Modelle ohne `contextWindow` (Log-Fallback): Füllstand wird mit 200k geschätzt („~N tokens“).

## TODO
1. Echte Kompaktierung live testen (`/compact` in einer Test-Session) und Animation prüfen.
2. Optional: Auslösung über hypridle als echter Idle-Screensaver.
3. Performance: statische Ebene (Rahmen, Möbel, Titel) einmal vorrendern und nur Figuren/Tacho
   neu zeichnen; Text-Glyphen cachen. Gemessen: `show_text` ist der größte Einzelposten.
