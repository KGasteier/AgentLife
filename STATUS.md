# STATUS

## Stand 0.8.1
- **Sprechblasen-Vorrat** `agentscope/quips.py`: Memes im englischen Original („Live long and prosper.“, „This is fine.“, „Beam me up, Scotty!“) plus deutsche Antworten in Variation. `quips.line(key, …)` wählt deterministisch aus der Liste (Lauf-`RUN_SEED`, Agent-Schlüssel, Zeitschlitz) – nie zweimal dasselbe; neue Antworten einfach anhängen. Antworten auf Spocks Gruß enthalten „Möge die Macht mit dir sein.“ und Verwandte.
- **Verdrahtet:** Vulkanier (Gruß/Antwort/Beamen), „This is fine“, „6-7“, „Distracted Developer“, KI-Gegner, Sith/Jedi, Zombies, Gandalf.
- **Tastenkürzel jetzt `SUPER + A`** (war frei; `SUPER+CTRL+A` = Audio, `SUPER+CTRL+ALT+A` = ChatGPT bleiben). `~/.config/hypr/bindings.lua` und README angepasst, live als modmask 64 registriert.
- Tests: node 12, Python 62 (`test_regression_quips_vary_and_keep_the_original`, `test_spock_greeting_reply_is_star_wars`).

## Stand 0.8.0
- **Farbe nur im Titelkasten:** Die Umrissfarbe je Harness sitzt jetzt ausschließlich im Beschriftungskasten (`scene.harness_tint` als Füllung, `scene.harness_ink` als Rahmen/Text). Alle Skizzenlinien bleiben schwarz; `Pen.ink` wird nicht mehr gesetzt. Regressionstest `Wunsch080Test.test_regression_only_the_title_box_is_tinted`.
- **Titel trägt immer Sitzungsinfo:** Ohne Skill und Sitzungsnamen zeigt der Titel statt „?“ eine kurze Sitzungskennung (`scene.session_label` aus dem Agent-Schlüssel). Regressionstest `test_regression_title_always_carries_session_info`.
- **Maul gespiegelt und farbig:** Das Maul sitzt rechts neben „gesamt gefressen…“ (`MAUL = (806, 150)`) und öffnet nach links. Gelbe Tokens fliegen hinein (`scene.TOK_IN`), grüne kommen oben wieder heraus (`scene.TOK_OUT`); der Strom bleibt lokal im Tacho-Bereich. Regressionstest `test_regression_tokens_are_yellow_in_and_green_out`.
- **Grundlinien-Wackeln der Comicschrift:** `Pen._laid_out`/`Pen._glyphs` setzen handgesetzte Zeichen minimal unruhig auf die Grundlinie (wie die Unterzeile). Regressionstest `test_regression_comic_font_wobbles_on_the_baseline`.
- **Reihenfolge variiert je Lauf:** `acts.RUN_SEED` (pro Programmlauf) fließt in `variant()`, `finale_style()` und die Umgebungsfiguren (`_slot_kind`) ein – Szenen laufen nie zweimal in derselben Reihenfolge. Regressionstest `test_regression_animation_order_varies_between_runs`.
- **Protest-Antwort:** Die KI-Gegner bekommen jetzt „Ich mach nur meinen Job.“ zu hören. Test `test_protesters_answer_ich_mach_nur_meinen_job`.
- **`--fps 8` als Vorgabe** (vorher 10). Test `test_default_fps_is_eight`.
- **Politur:** Karate-Tritt mit durchgehendem Bewegungsbogen und früherem Brettbruch, Pappdrache kippt weich per Ease und meldet „plumps!“, Spinnweben starten kleiner (r = 14 + 46·g), früh wachsende Ranken mit kleineren Blättern.
- **Neue Szenen:** Memes `idle_67`, `idle_thisisfine`, `idle_distracted`; TikTok-Challenges `idle_planking`, `idle_mannequin`, `idle_icebucket` (je 3, `StayInActorAreaTest` bis `range(1, 40)`). Tests: node 12, Python 60.

## Stand 0.7.0
- **Fremd-Harnessse:** `agentscope/harnesses.py` liest Sitzungs-Logs von **Claude Code** (`~/.claude/projects/<slug>/*.jsonl`) und **Codex** (`~/.codex/sessions/JJJJ/MM/TT/rollout-*.jsonl`) und rekonstruiert daraus Panels (`harness="claude"|"codex"`, nur außerhalb pi). `model.collect` mischt pi (live/Log) zuerst, dann Claude, dann Codex; höchstens zwei Panels je Fremd-Harness, frisch ≤ 30 min.
  - Claude: `ai-title`/`last-prompt` als Titel, `assistant.message.usage` für Kontext/Tokens/Rate, `isCompactSummary` als Kompaktierung, `is_error`-Tool-Ergebnisse als Hoppla.
  - Codex: `session_meta`/`turn_context` (Kopf der Datei, nicht nur Tail!), `token_count.info` für Kontext/Fenster, `token_usage_record` für Tokens/Rate, `compacted` als Kompaktierung, `exec`-Ausgabe mit `exit_code≠0` als Hoppla.
- **Harness im Titel + Farben:** Panel-Beschriftung jetzt `harness · Skill/Sitzung` (`scene.panel_title`), z. B. `pi · vaultdev`. Jeder Harness hat eine **dezent andere Umrissfarbe** (`scene.harness_ink`: pi Tinte, Claude warm-braun, Codex grün-blau); die Tinte wird zentral über `Pen.ink`/`Pen.rgb` durch alle Primitiven gereicht. Der statische Ebenenschlüssel enthält Harness und Titel.
- **Skill-Erkennung:** `model.skill_from_prompt` liest `/skill:name`, `/name` oder ein erstes Wort, das einem installierten Skill entspricht (Verzeichnisse aus `~/.pi/agent/skills`, `~/.agents/skills`).
- Demo zeigt jetzt fünf Panels (zwei pi, je einer Claude/Codex). Tests: node 12, Python 52 (+`HarnessTest` mit Kopf/Tail-Regression).

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

## Stand 0.5.1 – weitere Varianten
- Leerlauf (+7): Zunge schnappt Fliege, Kopf schlafend auf der Tastatur (Zzz, Sabberbläschen), Papierkugel-Basketball (Treffer/daneben, Punktestand), Bürostuhl-Karussell, Strecken+Gähnen, Handy-Doomscrolling, Spinne seilt sich ab (Dialog).
- Denken: am Stift kauen. Tippen: Schweißtropfen. Fehler: Kopf auf den Tisch (bonk).
- Regressionstest `StayInActorAreaTest`: keine Variante malt in den Kontextglas-Bereich (x ≥ 452); er schlug beim ersten Papierkorb an.
- Tests: Python 41.

## Stand 0.5.2 – Besuch und Ambient
- Leerlauf: **Gast-Agent** (blau, Namensschild „Claude", „von nebenan" / „aus dem Nachbarpanel" / „vom Stockwerk drüber", Händeschütteln, 4 Dialogpaare) und **Postbote** (rot, Mütze, Tasche; Brief → Münzen springen heraus, „+Nk tok").
- Ambient (alle 30 s je Panel zeitversetzt): zusätzlich Postbote läuft durchs Bild und Paket-Drohne („tok") fliegt über die Szene; 2 von 8 Slots ruhig.
- Tests: Python 43 (`AmbientTest`; `StayInActorAreaTest` deckt die neuen Varianten ab).

## Stand 0.6.0
- Sprechblasen-Schrift nie fett (`Pen.say` erzwingt es; Test `NoBoldBubblesTest`).
- Token-Münzen fliegen jetzt in das **Maul** (x≈418, `scene.draw_maul`), werden gekaut und zum Tacho ausgespuckt.
- Neue Idle-Szenen (Index 18–28): Star Trek, Zombies, Star Wars, Herr der Ringe, Kaffee zu zweit, Flirt, Kinder, No-AI-Demo, Cosplay/LARP, Tai Chi, Karate. Sabber beim Schreibtisch-Nickerchen.
- `acts.overgrowth`: Unordnung auf Tisch/Boden, Spinnweben und Pflanzen wachsen mit der Leerlaufzeit (240 s nach dem Finale bis voll); `FORCE["grow"]` für Vorschau.
- Tests: Python 48, Node 12.
