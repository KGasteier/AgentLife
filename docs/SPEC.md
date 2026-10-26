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
- **Schrift Kalam** (OFL, `agentscope/fonts/`) für Überschriften, Blasen und Ausrufe; wird pro Prozess
  über `FcConfigAppFontAddFile` angemeldet – keine Systeminstallation. Fließtext bleibt in der
  Grundschrift (xkcd Script/Humor Sans, sonst URW Gothic). `text(..., hand=None)`: fett ⇒ Kalam.
- **Blasentext**: `Pen.think`/`Pen.say` setzen Text über `text_block` (umbrechen → verkleinern → mit …
  kürzen) in das Innere der Ellipse; die Wolkenbögen liegen außerhalb. Test: `tests/test_drawing.py`.
- **Posen**: Proportionen Rumpf 48, Beine 2×30, Arme 2×24. Hände/Füße werden per Zwei-Glied-IK an
  Zielpunkte gesetzt (`figure(hands=…, feet=…)`). Sitzen: Gesäß auf der Sitzfläche (`SEAT_H` = Unterschenkel),
  Oberschenkel waagerecht, Füße am Boden, Knie vorn; Tisch `DESK_H` = 62. Stehen: Füße auf `FLOOR`.

## Metaphern
siehe README „Was man sieht“.

## Nicht-Ziele (vorerst)
- Kein Sperrbildschirm/Idle-Auslöser (hypridle) – nur manueller Start.
- Keine Steuerung der Agenten aus dem Screensaver.
