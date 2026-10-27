# tools – Reproduzierbare Hilfsskripte

Diese Skripte waren ursprünglich Wegwerf-Prototypen in `/tmp`; sie erzeugen Artefakte,
die im Repo liegen, und gehören deshalb mitversioniert.

## `build-font.py`

Baut `agentscope/fonts/steel-umlaut-city.regular.ttf` (Familie **Steel Umlaut City**) aus
`SteelCityComic-Regular.ttf`:

- Die leeren Umlaut-Slots (`ÄÖÜäöü`) werden an Ort und Stelle mit den Konturen des
  Grundbuchstabens plus zwei handgezeichneten Punkten gefüllt.
- `ß` wird als monolineare Drei-Band-Konstruktion (Stiel, Haken, Schleife) neu gezeichnet.
- Eigener Familienname, damit es keine Fontconfig-Kollision mit dem Original gibt.

```bash
PYTHONPATH=~/.local/share/pylibs python3 tools/build-font.py
```

`sz.py`/`sz2.py` sind die ß-Prototypen (SVG/PNG-Vorschau), die in die Konstruktion eingeflossen sind.

## Bezug zu den Tests

`tests/test_drawing.py::FontTest` prüft, dass die gebaute Schrift gebündelt ist, sich in-process
auflöst und Umlaute Tinte aufs Papier bringen – die Datei ist also nicht optional.
