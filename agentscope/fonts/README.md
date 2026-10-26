# Mitgelieferte Schriften

## Steel City Comic

`SteelCityComic-Regular.ttf` – Familie „Steel City Comic“, Copyright 2004, Gestalter Timothy Dunn
und Joshua Dunn. Laut beiliegender Lizenzangabe der Schrift frei nutzbar und weitergebbar; bei
Verwendung ist „Steel City“ als Herkunft zu nennen. Änderungen an der Schrift gehen an den
Bearbeiter über. Die Datei wird nur für den laufenden Prozess über `FcConfigAppFontAddFile`
angemeldet (`sketch.register_fonts`), nicht ins System installiert.

Verwendet für Überschriften, Sprech-/Gedankenblasen und Ausrufe (`sketch.HAND_FONT`).
Die Grundlinie sitzt absichtlich leicht unruhig (`Pen._laid_out`, `Pen._glyphs`); die Oberlänge
für die erste Blasenzeile steht je Familie in `sketch._BASELINE_EM`.

**Wichtig:** Steel City Comic enthält für Ä/Ö/Ü/ä/ö/ü/ß zwar einen cmap-Eintrag, aber keine
Konturen, und für ✓/↻ gar keine Glyphe. `sketch._glyph_probe` prüft deshalb je Zeichen Glyphenindex
*und* Tinte; fehlende Zeichen kommen aus `HAND_FALLBACK` (zuerst Kalam).

## Kalam

`Kalam-Regular.ttf`, `Kalam-Bold.ttf` – indische Handschriftenschrift von Indian Type Foundry,
SIL Open Font License 1.1 (`OFL.txt`). Sie wird hier nicht mehr für den ganzen Text verwendet,
sondern nur noch als Zeichen-Ersatz für die Zeichen, die Steel City Comic fehlen (Umlaute,
Satzzeichen) – dadurch bleiben deutsche Texte in Handschrift-Optik lesbar.
