# STATUS

## Stand 0.8.3 – 33 neue Rollen- und Slapstick-Szenen
- **Leerlauf wächst von 9 auf 42 Szenen.** 33 neue Szenen (`ROLES_083` in `acts.py`) laufen im 14-s-Takt, wenn ein Agent auf den nächsten Prompt wartet – die Figuren sind jetzt nicht mehr nur Kollegen, sondern Verkäufer, Künstler, Sportler und Popkultur:
  - **Slapstick & Büro:** Chaplin mit Melone und Stock, Wutanfall am Schreibtisch („a bad day at the office“), Bankeinbruch im Stil von Mission Impossible.
  - **Tech-Persönlichkeiten:** als Elon (Rakete, „TO THE MOON“), als Sam Altman, als Mark Zuckerberg, als Donald Trump, als YouTube-Influencer (Kamera, „ähm…“), als wütender Gamer.
  - **Weitere Rollen:** Barista, Kellner, Dirigent, Magier, Maler, Koch, Detektiv, Astronaut, Boxer, Gewichtheber, Ninja, Pirat, Vampir, Roboter, Feuerjongleur, Pizzabäcker, Tourist, Taucher, Skateboarder, Superheld, Geist, Ritter, Cowboy, Mönch.
- **Eigene Sprechblasen** für die acht Popkultur-Rollen in `quips.py` (`chaplin`, `heist`, `elon`, `sam`, `zuck`, `trump`, `youtube`, `gamer`), je vier deutsche Antworten; das englische Original bleibt erhalten.
- **Bugfix Modell-Faden:** `scene._host_head(p, cx)` wählt den Kopf der Hauptfigur jetzt nur noch **oberhalb des Bodens** (`y < FLOOR - 2`). Vorher konnte der pinke Faden an eine Minion-/Umgebungsfigur in der unteren Leiste anschließen (y ≈ 464) – das ließ `ModelThreadTest` etwa jeden fünften Lauf scheitern. Regressionstest `test_regression_thread_never_attaches_below_the_floor` (injiziert bewusst einen Kopf unter dem Boden).
- **Zeichen-Korrekturen:** `_actor` kennt kein `crouch` (jetzt `hip_dy`), `Pen.curve`/`Pen.arc` kennen kein `fill` (jetzt `poly(closed=True, fill=…)` bzw. `circle(fill=…)`); Vampir-Umhang, Geist und Mönch neu gezeichnet (Umhang hinter der Figur, Figur sitzt nicht mehr auf dem Boden).
- Tests: **Python 87, Node 12**. Neu `PopCultureAndGrowthTest.test_regression_roles_083_scenes_registered` und `…_every_scene_renders_without_error` (je Szene bei t = 0,5/3,3/6,0/9,1/12,0), dazu `ModelThreadTest.test_regression_thread_never_attaches_below_the_floor`.

## Stand 0.8.2c
- **Eigene Comicschrift mit Umlauten:** `agentscope/fonts/steel-umlaut-city.regular.ttf` – eine Ableitung von Steel City Comic, bei der die **leeren Umlaut-Slots** (Adieresis, Odieresis, Udieresis, adieresis, odieresis, udieresis) an Ort und Stelle mit den Konturen des Grundbuchstabens plus zwei handgezeichneten Punkten gefüllt sind; **ß** ist als monolineare Drei-Band-Konstruktion (Stiel, Haken, Schleife) neu gezeichnet. Die Familie heißt jetzt **`Steel Umlaut City`** (vorher Kollision mit dem Originalnamen), `sketch.HAND_FONT`. Der Per-Zeichen-Fallback bleibt, wird aber nur noch für ✓/↻ gebraucht. Regressionstests `test_steel_umlaut_city_is_bundled_and_resolves`, `test_regression_umlauts_live_in_the_extended_font`.
- **Grundlinien-Wackeln beruhigt:** `HAND_WOBBLE = 0.55`, `HAND_TILT = 0.035` (vorher ±1,5 px und ±0,08 rad) – Blasen bleiben handschriftlich, aber lesbar. Regressionstest `test_regression_bubble_wobble_was_reduced`.
- **Modellname in Gehirnfarbe:** `scene.model_ink` = **pink** (Anbindung steht, wie das Gehirn), **orange** (Modell angewählt, keine Anbindung), **grau** (kein Modell). Regressionstests `test_regression_model_name_is_coloured`, `test_regression_model_without_selection_is_grey`.
- **Gehirn neu nach den Vorlagen `hirn1–3.jpg`:** `Pen.brain` zeichnet jetzt eine **Seitenansicht** – die Großhirnkuppe aus `Pen._cerebrum` (Lappenbuckel, vorn voller, unten rechts ausgespart), gefüllt mit **drei Ringen dicht an dicht liegender Windungen** (`Pen._wrinkle`, 16/11/5, bei kleinen Größen 13/8/3), ein großes **geriffeltes Kleinhirn** (`Pen._blob` + Riffellinien) unten rechts und ein Stiel, dessen Spitze zurückkommt. Die alten Blattfalten (`Pen._leaf`) sind entfallen. Regressionstest `test_regression_brain_is_built_from_convolutions`.
- **Travolta-Pose mit Bewegung:** der `disco`-Tanz in `dance.py` hat jetzt echten Hüftschwung (`5.5·s·sin`), Standbeinwechsel, einen Zeigearm bis über den Kopf und die andere Hand in der Hüfte; Ziele bleiben in IK-Reichweite. Regressionstest `test_regression_travolta_pose_moves_enough`.
- Tests: **Python 84, Node 12**. Auf dem alten Stand `f465c33` scheitern 10 der neuen Tests (7 failures, 3 errors).

## Stand 0.8.2b
- **Gehirn nach den Vorlagen `hirn1–3.jpg`:** `Pen.brain` ist neu gebaut – der Umriss hat breite Lappenbuckel und feine Riffelung (kein glattes Ei), die Fläche ist mit dichten **Blattwindungen** (`Pen._leaf`, zwei gespiegelte Bögen) gefüllt, dazu **Sylvische Furche**, geriffeltes **Kleinhirn** unten rechts und ein Stiel. Bei kleinen Größen werden größere Windungen gezeichnet (`coarse`), damit der Detailreichtum nicht zuläuft. `Pen.brain` gibt die Stielspitze zurück (`p.brain_tip`); im Titel `s=2.3`. Regressionstest `test_regression_brain_is_built_from_convolutions`.
- **Gehirn weiter rechts:** `scene.brain_pos` → `(title_width + 54.0, 18.0)` (vorher `+46`). Regressionstest `test_regression_brain_sits_further_right_of_the_title_box`.
- **Modellname farbig:** `scene.model_ink` färbt den Modellnamen im Titel – **blau** bei stehender Anbindung, **rot** wenn keine Anbindung besteht, grau ohne Modell. Regressionstest `test_regression_model_name_is_coloured`. (Seit 0.8.2c pink/orange/grau.)
- **Kaputte Anbindung sichtbar (mimo-Fall):** `scene.has_connect(a)` erkennt „Modell angewählt, aber nie ein Token geflossen und schon in Runde 0 ein Fehler“. Dann bleibt die normale Pose, aber der Modell-Faden ist **rot und zuckend** (`_model_thread(..., bad=True)`) mit Blitzstelle und „unterbrochen“ am Kopf; der Titelzusatz lautet rot „… · keine Anbindung!“. Regressionstest `test_regression_broken_connection_is_visible`, Gegenprobe `test_regression_connected_model_is_not_marked_broken`.
- **Comicschrift `Steel City Comic`** (mitgeliefert als `agentscope/fonts/SteelCityComic-Regular.ttf`, frei nutzbar mit Namensnennung) statt Kalam; `sketch.HAND_FONT`. Das Grundlinien-Wackeln bleibt (`Pen._laid_out`/`Pen._glyphs`, jetzt ±1,5 px und ±0,08 rad), die Oberlänge der ersten Blasenzeile kommt aus `_BASELINE_EM` je Familie. Regressionstest `test_regression_comic_font_is_steel_city_comic`.
- **Zeichen-Fallback (wichtiger Fund):** Steel City Comic führt Ä/Ö/Ü/ä/ö/ü/ß im cmap, hat dafür aber **keine Konturen** (Vorschub da, Tinte null); ✓/↻ fehlen ganz. Ohne Gegenmaßnahme bliebe die deutsche Oberfläche löchrig. `sketch._glyph_probe` prüft je Zeichen Glyphenindex **und** Tinte (zwei Proben, weil jede für sich täuscht), `Pen.family_for`/`Pen._select` wählen dann zeichenweise aus `HAND_FALLBACK = [Kalam, Adwaita Sans, DejaVu Sans, …]`; Kalam übernimmt Umlaute und Satzzeichen in Handschrift-Optik, die Symbolschriften retten ✓/↻. Vorschub-Cache `_ADV` ist auf die tatsächlich gewählte Familie geschlüsselt. Regressionstests `test_regression_comic_font_falls_back_per_character`, `test_regression_umlauts_leave_ink_on_the_page`.
- Tests: **Python 80, Node 12**. Auf dem alten Stand `0e5c364` scheitern 9 der neuen Tests (6 failures, 3 errors).

## Stand 0.8.2a
- **Faden liegt hinter den Blasen:** `Pen.bubbles` sammelt die Geometrie aller Sprech-/Gedankenblasen (auch der Terminal-Blase in `acts._terminal`), `Pen.bubbles_cover` prüft Punkte; `scene._thread_behind` zeichnet den Faden in Abschnitten und lässt ihn hinter Blasen verschwinden. Regressionstest `test_regression_thread_hides_behind_bubbles`.
- **Faden endet fest am Kopf:** `scene._thread_points` hat an beiden Enden exakt 0 Ausschlag (Hüllkurve `sin(πk)`), der Anschlusspunkt am Kopf wird zusätzlich als kleiner Punkt gezeichnet – keine Lücken mehr. Regressionstest `test_regression_thread_has_exact_endpoints`.
- **Gehirn größer und deutlicher:** `Pen.brain` ist ein richtiges Cartoon-Gehirn (Kuppe mit drei Windungsbuckeln, Mittelfurche, vier Windungen, geripptes Kleinhirn, Stiel) und gibt die Stielspitze für den Faden zurück; im Titel mit `s=1.25`. Regressionstest `test_regression_brain_is_larger_and_returns_stem_tip`.
- **Ohne Modell keine Aktivität:** `scene.has_model` schaltet Tacho (Nadel links, „0“, „kein Modell angewählt“), Kontextglas („leer“), Kurve („keine Aktivität“), Notizblock, Werkzeugbalken, Minions und Hoppla-Zähler („0 – kein Modell“) still; die Figur bleibt die leblose Puppe mit gerissenem Faden. Regressionstest `test_regression_no_model_shows_no_activity`.
- Tests: Python 70, Node 12. Auf dem alten Stand `309fa5b` scheitern 3 der neuen Tests (1 failure, 2 errors).

## Stand 0.8.2
- **Pinkes Gehirn im Titel:** Links vom Modellnamen sitzt ein kleines pinkes Cartoon-Gehirn (`sketch.PINK`, `Pen.brain(x, y, s)` – zwei Lappen mit Windungen und Stiel), gezeichnet in der statischen Ebene (`render_panel`), Position über `scene.brain_pos(a, title_width)`.
- **Feiner Faden zum Kopf:** `scene._model_thread` zieht einen 0,7 px dünnen pinken Faden vom Gehirn zum Kopf der Hauptfigur. Der Kopf wird aus `Pen.heads` (Hüfte/Kopf aller gezeichneten Figuren) als der zur Sitzposition `cx` nächstgelegene gewählt – der Faden folgt also in **allen** Posen (Laufen, Springen, Tai-Chi, Karate …) und wackelt luftig (`sag` + Sinuswelle mit `t`). Dynamische Ebene, nicht gecacht.
- **Ohne Modell getrennt:** `scene.has_model(a)` prüft `Agent.model`. Fehlt es, zeichnet `scene.draw_slumped` eine leblose Strichpuppe (grau, geschlossene Augen, hängender Mundwinkel, „z z z“), die in den Stuhl gekippt ist; der Faden ist oben abgerissen, baumelt kurz unter dem Gehirn und trägt den Hinweis „kein Signal“. Der Titeltext wird pink und lautet „kein Modell · getrennt“, die Unterzeile „kein Modell angewählt – Verbindung getrennt“.
- Tests: `ModelThreadTest` (4, u. a. `test_regression_thread_follows_the_head`, `test_regression_no_model_shows_lifeless_puppet_and_broken_thread`); auf dem alten Stand `0479e4e` scheitern 3 davon (1 failure, 2 errors). Python 66, Node 12.

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
