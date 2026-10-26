# Mitgelieferte Schriften

## Steel Umlaut City

`steel-umlaut-city.regular.ttf` – Familie **„Steel Umlaut City“**, abgeleitet von *Steel City Comic*
(`SteelCityComic-Regular.ttf`, Copyright 2004, Gestalter Timothy Dunn und Joshua Dunn; laut
beiliegender Lizenzangabe frei nutzbar und weitergebbar, bei Verwendung ist „Steel City“ als Herkunft
zu nennen; Änderungen gehen an den Bearbeiter über).

Erweiterung (fontTools, upm 2048, keine neuen Glyphennamen):

- Die **leeren Umlaut-Slots** des Originals (Adieresis, Odieresis, Udieresis, adieresis, odieresis,
  udieresis) sind an Ort und Stelle mit den Konturen des Grundbuchstabens plus zwei handgezeichneten
  Punkten (leicht wellig, `wob = 3.0`) gefüllt. Das Original führt die Zeichen im cmap, hat dafür aber
  keine Konturen – ohne diese Füllung blieben deutsche Texte löchrig.
- **ß** (`germandbls`) ist als monolineare Drei-Band-Konstruktion neu gezeichnet (Stiel, Haken, Schleife;
  Bandbreite 84 Einheiten ≈ Strichstärke).
- Eigener **Familienname**, damit Fontconfig nicht die leere Originaldatei für denselben Namen wählt.

Anmeldung nur für den laufenden Prozess über `FcConfigAppFontAddFile` (`sketch.register_fonts`), nicht
im System installiert. Verwendet für Überschriften, Sprech-/Gedankenblasen und Ausrufe (`sketch.HAND_FONT`).
Die Grundlinie sitzt absichtlich leicht unruhig (`Pen._laid_out`, `Pen._glyphs`, `HAND_WOBBLE`/`HAND_TILT`);
die Oberlänge für die erste Blasenzeile steht je Familie in `sketch._BASELINE_EM`.

**Fallback:** Für ✓/↻ fehlen im Original und in der Ableitung die Glyphen. `sketch._glyph_probe` prüft
deshalb je Zeichen Glyphenindex *und* Tinte; fehlende Zeichen kommen aus `HAND_FALLBACK` (zuerst Kalam).

## Kalam

`Kalam-Regular.ttf`, `Kalam-Bold.ttf` – indische Handschriftenschrift von Indian Type Foundry,
SIL Open Font License 1.1 (`OFL.txt`). Sie wird hier nicht mehr für den ganzen Text verwendet,
sondern nur noch als Zeichen-Ersatz für die Zeichen, die Steel Umlaut City fehlen (derzeit ✓/↻) –
dadurch bleiben deutsche Texte in Handschrift-Optik lesbar.
