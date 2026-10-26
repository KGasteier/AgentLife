# SPEC – agentscope

## Ziel
Per Tastenkürzel startbarer Vollbild-Screensaver für Omarchy, der die Aktivität aller pi-Agenten
(Hauptagenten, Worker, Subagents) als xkcd-Comic mit Metaphern zeigt: Fortschritt, Live-Tokenverbrauch,
Kontextkompaktierung und Fehler.

## Architektur
```
pi-Prozess ──(Erweiterung extension/)──► $XDG_RUNTIME_DIR/agentscope/<pid>.json
                                              │
~/.pi/agent/sessions/**/*.jsonl ──(Fallback)──┤
                                              ▼
                          agentscope/model.py  (collect → [Agent])
                                              ▼
                          agentscope/scene.py  (Cairo-Comic, Panels)
                                              ▼
           agentscope/app.py (GTK4-Vollbild) · agentscope/snapshot.py (PNG)
```

## Entscheidungen
- **Erweiterung statt Log-Parsing** als Hauptquelle: nur Events liefern Live-Zustand (laufende Tools,
  Kompaktierung *während* sie läuft, Retries, Teilergebnisse von Subagents, Kontextfüllung).
- **Dateien statt Socket**: kein Daemon, robust bei Abstürzen (tote PIDs werden ignoriert).
- **Python + GTK4 + Cairo**: auf Omarchy vorhanden, kein Browser, wenig Ressourcen.
- **Eigene Strichzeichnung** (deterministisches Wackeln, langsames „Boiling“) statt Bibliothek.
- Tastenkürzel **SUPER+CTRL+ALT+A** (A = Agents; SUPER+CTRL+A war belegt).
- Radial-Mesh-Layout: Vollbild über `radialmesh-fullscreen`, sonst Fensterregel.
- **Schrift Steel City Comic** (mitgeliefert in `agentscope/fonts/`, frei nutzbar mit Namensnennung) für
  Überschriften, Blasen und Ausrufe; wird pro Prozess über `FcConfigAppFontAddFile` angemeldet – keine
  Systeminstallation. Fließtext bleibt in der Grundschrift (xkcd Script/Humor Sans, sonst URW Gothic).
  `text(..., hand=None)`: fett ⇒ Comicschrift. Die Grundlinie der Comicschrift sitzt bewusst leicht
  unruhig (`Pen._laid_out`/`Pen._glyphs`), die Oberlänge je Familie steht in `_BASELINE_EM`.
- **Blasentext**: `Pen.think`/`Pen.say` setzen Text über `text_block` (umbrechen → verkleinern → mit …
  kürzen) in das Innere der Ellipse; die Wolkenbögen liegen außerhalb. Test: `tests/test_drawing.py`.
- **Posen**: Proportionen Rumpf 48, Beine 2×30, Arme 2×24. Hände/Füße werden per Zwei-Glied-IK an
  Zielpunkte gesetzt (`figure(hands=…, feet=…)`). Sitzen: Gesäß auf der Sitzfläche (`SEAT_H` = Unterschenkel),
  Oberschenkel waagerecht, Füße am Boden, Knie vorn; Tisch `DESK_H` = 62. Stehen: Füße auf `FLOOR`.

- **Bewegung**: Hammer über Phasenfunktion `hammer_swing(t)` (Ausholen langsam, Schlag k², Rückprall);
  Tippen über `typing_hands` (deterministischer Rhythmus per Hash, kein Zufallsflimmern).
  Tänze in `agentscope/dance.py`: je Stil Hüfte + Hand-/Fußziele, Frontansicht mit `splay`.
- **Tokenrate im Log-Fallback**: Summe Output-Tokens / Summe Antwortdauern der letzten 90 s, 0 nach 25 s Stille.

## Metaphern
siehe README „Was man sieht“.

## Nicht-Ziele (vorerst)
- Kein Sperrbildschirm/Idle-Auslöser (hypridle) – nur manueller Start.
- Keine Steuerung der Agenten aus dem Screensaver.
