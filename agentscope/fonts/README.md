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
