# STATUS

## Stand 0.4.1
- **Schrift wieder scharf:** GTK4 liefert eine Aufzeichnungsfläche mit Maßstab 1, die erst später auf Skalierung 2 gerastert wird. Statische Ebene und Textmasken wurden deshalb in halber Auflösung gebaut und hochskaliert. Jetzt Maßstab über `area.get_scale_factor()` (`sketch.HINT_SCALE`). Regressionstest `test_regression_hidpi_text_stays_sharp`.
- **Panel-Titel = Sitzungsname** (`/name`): Live-Datei `sessionName`, sonst letzter `session_info` aus der Sitzungsdatei, sonst Verzeichnis. Ohne Namen zeigt das Panel das Verzeichnis (z. B. `~`).

## Stand 0.4.0
- **Deutsche Oberfläche** (Texte in `scene.py`, Ereignisse in `core.ts`/`model.py`); Fachbegriffe (Token, Tools, Retry, Compaction) bleiben.
- **Bug „wartet auf deinen nächsten Prompt“ trotz Aktivität:** Das Log-Fallback galt nach 20 s Stille als idle. pi schreibt aber erst nach fertiger Nachricht, ein langer Modellaufruf oder eine Kompaktierung sieht also wie Leerlauf aus. Jetzt `model.log_phase`: idle nur nach abgeschlossener Antwort; offene Anfrage gilt `BUSY_MAX_S` (10 min) als aktiv.
- **Bug Kompaktierung nicht sichtbar:** Mit Erweiterung funktioniert sie (live geprüft: `compacting` 13,6–24,5 s, Zähler 0→1). Laufende pi-Prozesse ohne neu geladene Erweiterung nutzen das Log, das keine laufende Kompaktierung kennt → zeigt jetzt „denkt nach“ statt Schlaf; echte Anzeige nach Neustart/`/reload` von pi. Manuelles `/compact` bleibt nicht mehr in „thinking“ hängen (kein `agent_settled`).
- **Statische Ebene** (`scene.StaticLayer`, `render(layer=…)`) + **Text-Maskencache** (`Pen._text_cached`) + Takt über `add_tick_callback`. CPU-Zeit je Frame 2880×1808: 41 → 18 ms; im Vollbild ca. 45 % → 41 % eines Kerns (Rest: GTK-Software-Upload). `AGENTSCOPE_DEBUG=1` gibt fps/ms aus.

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
1. Laufende pi-Prozesse neu starten bzw. `/reload`, damit sie die Erweiterung laden; dann Kompaktierungsanzeige im Screensaver am echten Agenten prüfen.
2. Optional: Auslösung über hypridle als echter Idle-Screensaver.
3. Performance: Rest sind GTK-Software-Upload und dynamische Striche; falls nötig `--fps 5`.

## Stand 0.5.0 – Abwechslung
- Neues Modul `agentscope/acts.py`: je Phase 2–4 Varianten (Denken: auf und ab laufen / Geistesblitz / Jo-Jo; Tippen: Kaffee / Kopfhörer; Koffer packen; Fehler: Panik-Lauf / Feuerlöscher; Retry: Klingel / Türspion; bash: Terminal / Kurbel; read: Schriftrolle / vorlesen; edit: Steintafel / Tafel; subagent: Fahne / Glocke; sonstige: Fernglas).
- `variant()` wählt deterministisch aus Agent-Key + Zeit (alle 10 s, nie zweimal dasselbe hintereinander, Panels verschieden).
- **Siegestanz:** Wechsel „arbeitet → fertig" (`History.sample` setzt `Agent.idle_since`) → 15 s Tanz auf dem Tisch: Hopak (Kosaken-Hocke mit Beinwurf + Sprünge, Papakha), Roboter, Siegerhüpfer mit Konfetti (`dance.py`).
- **Leerlauf:** 8 Szenen im 14-s-Takt (Zeitung, Kaffee, Jonglieren, Pflanze gießen, Papierflieger, Besuch eines blauen Kollegen mit Dialog, Vogel auf dem Tisch, Yoga).
- **Umgebung:** Katze, Vogel, Ballon, Schnecke ziehen zeitversetzt je Panel durchs Bild.
- **Leeres Bild:** Hängematte, Angeln, Lagerfeuer, Sternegucken im Wechsel.
- Alles liegt auf der dynamischen Ebene; Rechenzeit pro Frame im Rauschen der VM unverändert.
- Tests: Python 40 (neu `VarietyTest`), Node unverändert.
- Offen: Siegestanz erst nach beobachtetem Übergang (nicht bei Start im Leerlauf); Log-Fallback erkennt ihn über die History ebenfalls.
