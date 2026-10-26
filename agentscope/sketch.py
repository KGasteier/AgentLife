"""xkcd-artige Zeichenprimitive auf Cairo: wackelige Linien, Handschrift, Strichmännchen, Requisiten.

Alle Koordinaten sind logische Einheiten im aktuellen Cairo-Koordinatensystem.
Das Wackeln ist deterministisch (Seed aus Koordinaten + `boil`), damit Linien nicht
flimmern; `boil` wechselt langsam und erzeugt den typischen "lebendigen" Strich.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import random
import subprocess
from functools import lru_cache
from pathlib import Path

import cairo

INK = (0.07, 0.07, 0.07)
RED = (0.82, 0.12, 0.10)
BLUE = (0.16, 0.36, 0.74)
GRAY = (0.6, 0.6, 0.6)
LIGHT = (0.86, 0.86, 0.86)
PAPER = (1.0, 1.0, 1.0)
PINK = (0.85, 0.25, 0.5)   # Gehirn und Verbindungsfaden zum Modell
ORANGE = (0.90, 0.48, 0.09)  # Modellname bei defekter Anbindung

FONT_CANDIDATES = ["xkcd Script", "xkcd", "Humor Sans", "Comic Neue", "URW Gothic"]
HAND_FONT = "Steel Umlaut City"        # Steel City Comic inkl. Umlaute/ß (agentscope/fonts)
# Steel Umlaut City deckt Umlaute und ß selbst ab; für die übrigen Sonderzeichen (·»–„→♪✓↻)
# springen diese Familien zeichenweise ein. Kalam hält die Handschrift-Optik; die Symbolschriften retten ✓/↻.
HAND_FALLBACK = ["Kalam", "Adwaita Sans", "DejaVu Sans", "Noto Sans Symbols 2", "Symbola"]
FONT_DIR = Path(__file__).resolve().parent / "fonts"


@lru_cache(maxsize=1)
def register_fonts() -> bool:
    """Mitgelieferte Schriften (Steel City/Umlaut City) für diesen Prozess bei fontconfig anmelden.

    Muss vor der ersten Schriftauswahl laufen; keine Installation ins System nötig."""
    try:
        fc = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        ok = False
        for f in sorted(FONT_DIR.glob("*.ttf")):
            ok = bool(fc.FcConfigAppFontAddFile(None, str(f).encode())) or ok
        return ok
    except Exception:
        return False


@lru_cache(maxsize=1)
def hand_font() -> str:
    """Steel Umlaut City (Steel City Comic + Umlaute/ß), sonst die Grundschrift."""
    register_fonts()
    try:
        fams = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        fams = ""
    if register_fonts() or HAND_FONT.lower() in fams.lower():
        return HAND_FONT
    return pick_font()



@lru_cache(maxsize=1)
def pick_font() -> str:
    """Erste installierte Schrift aus FONT_CANDIDATES (xkcd-Schriften bevorzugt)."""
    try:
        fams = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return "Sans"
    have = {f.strip().lower() for line in fams.splitlines() for f in line.split(",")}
    for f in FONT_CANDIDATES:
        if f.lower() in have:
            return f
    return "Sans"


# Oberlänge (Bruchteil der Schriftgröße) für die erste Textzeile je Handschriftfamilie
_BASELINE_EM = {"Steel Umlaut City": 0.70, "Steel City Comic": 0.70, "Kalam": 0.78}

# Grundlinien-Wackeln und Neigung der Comicschrift (in em-Anteilen, ×1/18).
# 0.8.2c: deutlich ruhiger als zuvor (±1.5/±0.08), damit Sprechblasen lesbar bleiben.
HAND_WOBBLE = 0.55
HAND_TILT = 0.035

_ADV: dict = {}
_MASKS: dict = {}
_GLYPH_OK: dict = {}   # (Familie, Zeichen) → hat die Familie eine sichtbare Glyphe?


def _glyph_probe(fam: str, ch: str) -> bool:
    """Prüft auf einem Wegwerf-Zeichner, ob `fam` für `ch` überhaupt eine sichtbare Glyphe hat.

    Nötig, weil Steel City Comic im cmap zwar z. B. Ä/Ö/Ü/ä/ö/ü/ß führt, die Glyphen aber leer
    sind (Vorschub da, Tinte null). Ohne Probe bliebe in der deutschen Oberfläche eine Lücke."""
    if ch == " ":
        return True
    key = (fam, ch)
    v = _GLYPH_OK.get(key)
    if v is None:
        surf = cairo.ImageSurface(cairo.FORMAT_A8, 4, 4)
        cr = cairo.Context(surf)
        cr.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(32)
        e = cr.text_extents(ch)
        # Zwei Proben, weil jede für sich täuscht: Steel City Comic hat für Ä/Ö/Ü/ä/ö/ü/ß einen
        # gültigen Glyphenindex, aber keine Konturen (Breite/Höhe 0), während ✓/↻ dort auf das
        # Notdef-Kästchen (Index 0) fallen, das sehr wohl Tinte hat.
        glyphs, _cl, _fl = cr.get_scaled_font().text_to_glyphs(0, 0, ch)
        v = bool(glyphs) and glyphs[0][0] != 0 and e.x_advance > 0 and (e.width > 0 or e.height > 0)
        if len(_GLYPH_OK) > 5000:
            _GLYPH_OK.clear()
        _GLYPH_OK[key] = v
    return v
HINT_SCALE = 1.0  # echter Anzeigemaßstab; GTK4 liefert eine Aufzeichnungsfläche mit Maßstab 1, die erst später gerastert wird
_NOMASK = bool(__import__("os").environ.get("AGENTSCOPE_NOMASK"))
LEG = 30.0   # Ober-/Unterschenkel; Rumpf (Hüfte–Hals) = 48
ARM = 24.0   # Ober-/Unterarm
CLOUD_RB = 24.0  # größter Bogenradius der Gedankenwolke (inkl. Wackeln ≈ +5 %)


def _seed(*k) -> int:
    return hash(tuple(round(v, 1) if isinstance(v, float) else v for v in k)) & 0xFFFFFFFF


class Pen:
    def __init__(self, cr: cairo.Context, boil: int = 0, font: str | None = None, ink=None):
        self.cr = cr
        self.boil = boil
        self.ink = tuple(ink) if ink is not None else INK   # Harness-Umrissfarbe (pi = INK)
        self.font = font or pick_font()
        self.hand = hand_font() if font is None else font
        self._cache: dict = {}
        self.layer = None   # None = alles, "static" = nur Unveränderliches, "dynamic" = nur Bewegtes
        self.heads = []         # (Hüfte, Kopf) aller gezeichneten Figuren (für den Modell-Faden)
        self.bubbles = []       # zuletzt gezeichnete Blasen (Geometrie) – für den Modell-Faden dahinter
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

    @property
    def st(self) -> bool:
        return self.layer in (None, "static")

    @property
    def dy(self) -> bool:
        return self.layer in (None, "dynamic")

    # ------------------------------------------------------------------ Linien
    def _wpts(self, x0, y0, x1, y1, amp):
        key = (round(x0), round(y0), round(x1), round(y1), round(amp, 1), self.boil)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.5:
            return [(x0, y0), (x1, y1)]
        n = max(2, int(L / 12) + 1)
        r = random.Random(_seed(*key))
        p1, p2 = r.uniform(0, 6.28), r.uniform(0, 6.28)
        f1, f2 = r.uniform(0.6, 1.1), r.uniform(1.5, 2.6)
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        pts = []
        for i in range(n + 1):
            t = i / n
            env = 0.35 + 0.65 * math.sin(math.pi * t)
            o = amp * (0.6 * math.sin(f1 * t * L / 25 + p1) + 0.4 * math.sin(f2 * t * L / 25 + p2)) * env
            pts.append((x0 + (x1 - x0) * t + nx * o, y0 + (y1 - y0) * t + ny * o))
        if len(self._cache) > 6000:
            self._cache.clear()
        self._cache[key] = pts
        return pts

    def rgb(self, color):
        """Basis-INK durch die Panel-Tinte ersetzen; alle anderen Farben bleiben."""
        return self.ink if color == INK or color is None else color

    def _stroke(self, color, w, dash=None):
        cr = self.cr
        cr.set_source_rgb(*self.rgb(color))
        cr.set_line_width(w)
        if dash:
            cr.set_dash(dash)
        cr.stroke()
        if dash:
            cr.set_dash([])

    def _amp(self, L):
        return min(1.8, 0.4 + L * 0.008)

    def line(self, x0, y0, x1, y1, w=2.2, color=INK, amp=None, dash=None):
        amp = self._amp(math.hypot(x1 - x0, y1 - y0)) if amp is None else amp
        pts = self._wpts(x0, y0, x1, y1, amp)
        cr = self.cr
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        self._stroke(color, w, dash)

    def poly(self, pts, closed=False, w=2.2, color=INK, fill=None, amp=None):
        seq = list(pts) + ([pts[0]] if closed else [])
        cr = self.cr
        first = True
        for a, b in zip(seq, seq[1:]):
            amp_ = self._amp(math.hypot(b[0] - a[0], b[1] - a[1])) if amp is None else amp
            wp = self._wpts(a[0], a[1], b[0], b[1], amp_)
            if first:
                cr.move_to(*wp[0])
                first = False
            for p in wp[1:]:
                cr.line_to(*p)
        if closed:
            cr.close_path()
        if fill is not None:
            cr.set_source_rgb(*fill)
            cr.fill_preserve()
        self._stroke(color, w)

    def rect(self, x, y, w, h, lw=2.2, color=INK, fill=None):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True, w=lw, color=color, fill=fill)

    def circle(self, cx, cy, r, w=2.2, color=INK, fill=None, overshoot=0.35):
        rr = random.Random(_seed(round(cx), round(cy), round(r), self.boil))
        a0 = rr.uniform(0, 6.28)
        ph = rr.uniform(0, 6.28)
        n = max(12, int(r * 1.2))
        span = 2 * math.pi + (overshoot if fill is None else 0)
        cr = self.cr
        for i in range(n + 1):
            a = a0 + span * i / n
            k = 1 + 0.045 * math.sin(2 * a + ph) + (0.04 * i / n if fill is None else 0)
            x, y = cx + r * k * math.cos(a), cy + r * k * math.sin(a)
            (cr.move_to if i == 0 else cr.line_to)(x, y)
        if fill is not None:
            cr.close_path()
            cr.set_source_rgb(*fill)
            cr.fill_preserve()
        self._stroke(color, w)

    def arc(self, cx, cy, r, a0, a1, w=2.2, color=INK):
        n = max(6, int(abs(a1 - a0) * r / 6))
        cr = self.cr
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            (cr.move_to if i == 0 else cr.line_to)(cx + r * math.cos(a), cy + r * math.sin(a))
        self._stroke(color, w)

    def curve(self, pts, w=2.0, color=INK, dash=None):
        """Glatte Kurve durch Punkte (Catmull-Rom)."""
        cr = self.cr
        cr.move_to(*pts[0])
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1, p2 = pts[i], pts[i + 1]
            p3 = pts[min(len(pts) - 1, i + 2)]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            cr.curve_to(*c1, *c2, *p2)
        self._stroke(color, w, dash)

    def hatch(self, x, y, w, h, spacing=7, color=GRAY, lw=1.2, angle=45):
        cr = self.cr
        cr.save()
        cr.rectangle(x, y, w, h)
        cr.clip()
        d = w + h
        t = math.tan(math.radians(angle))
        i = -d
        while i < d:
            self.line(x + i, y + h, x + i + h / t, y, w=lw, color=color, amp=0.6)
            i += spacing
        cr.restore()

    # ------------------------------------------------------------------ Schrift
    def _font(self, size, bold=False, hand=False):
        self._size, self._bold, self._hand = size, bold, hand
        fam = self.hand if hand else self.font
        self.cr.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(size)
        self._fkey = (fam, round(size, 2), bold)

    def family_for(self, ch, hand=None):
        """Familie, die `ch` wirklich zeichnen kann: Comicschrift, dann Ersatz-Handschriften, dann Grundschrift."""
        hand = self._hand if hand is None else hand
        fams = [self.hand, *HAND_FALLBACK, self.font] if hand else [self.font, *HAND_FALLBACK]
        for fam in fams:
            if _glyph_probe(fam, ch):
                return fam
        return fams[-1]

    def _select(self, cr, ch, size=None, bold=None, hand=None):
        """Wählt für ein einzelnes Zeichen die passende Familie (Zeichen-Fallback) und setzt Größe/Gewicht."""
        size = self._size if size is None else size
        bold = self._bold if bold is None else bold
        hand = self._hand if hand is None else hand
        fam = self.family_for(ch, hand)
        cr.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        return fam

    def _adv(self, ch):
        """Vorschub eines Zeichens; Cache über alle Frames (Schrift ändert sich nicht)."""
        fam = self.family_for(ch)
        k = (fam, round(self._size, 2), self._bold, ch)
        v = _ADV.get(k)
        if v is None:
            self._select(self.cr, ch)
            v = self.cr.text_extents(ch).x_advance
            if len(_ADV) > 20000:
                _ADV.clear()
            _ADV[k] = v
        return v

    def text_width(self, s, size, bold=False, upper=True, hand=None):
        s = s.upper() if upper else s
        self._font(size, bold, bold if hand is None else hand)
        return sum(self._adv(ch) for ch in s)

    def fit(self, s, size, maxw, bold=False, upper=True, hand=None):
        """Kürzt s mit … auf maximale Breite."""
        if self.text_width(s, size, bold, upper, hand) <= maxw:
            return s
        while s and self.text_width(s + "…", size, bold, upper, hand) > maxw:
            s = s[:-1]
        return s.rstrip() + "…"

    def text(self, s, x, y, size=18, color=INK, align="left", bold=False, upper=True, jitter=1.0, maxw=None, hand=None):
        """Handschriftartige Zeile, jedes Zeichen leicht versetzt/gedreht.

        hand=None: fette Texte (Überschriften, Ausrufe) in der Comic-Handschrift, Rest in der Grundschrift."""
        s = str(s)
        hand = bold if hand is None else hand
        if hand:
            jitter *= 0.45                  # die Handschrift wackelt schon selbst
        if maxw:
            s = self.fit(s, size, maxw, bold, upper, hand)
        s = s.upper() if upper else s
        cr = self.cr
        self._font(size, bold, hand)
        width = sum(self._adv(ch) for ch in s)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        cr.set_source_rgb(*self.rgb(color))
        if self._text_cached(s, x, y, size, color, bold, hand, jitter, width):
            return width
        # Schrift „kocht“ nicht mit: ruhiger Text liest sich besser und flackert nicht (Seed ohne boil)
        for ch, gx, gy, rot, adv in self._laid_out(s, x, y, size, jitter, hand):
            if ch != " ":
                cr.save()
                self._select(cr, ch, size, bold, hand)
                cr.translate(gx, gy)
                cr.rotate(rot)
                cr.move_to(-adv / 2, 0)
                cr.show_text(ch)
                cr.restore()
        return width

    def _laid_out(self, s, x, y, size, jitter, hand):
        """Position, Versatz und Drehung je Zeichen. Die Comicschrift (hand) sitzt bewusst minimal
        unruhig auf der Grundlinie – wie die Unterzeile –, damit sie nicht wie gesetzt wirkt."""
        r = random.Random(_seed(len(s), round(x), round(y)))
        out, cx = [], x
        for ch in s:
            adv = self._adv(ch)
            dy = r.uniform(-0.9, 0.9) * jitter * size / 18
            if hand:
                dy += r.uniform(-HAND_WOBBLE, HAND_WOBBLE) * size / 18     # ruhige Handschrift-Grundlinie
            out.append((ch, cx + adv / 2, y + dy, r.uniform(-HAND_TILT, HAND_TILT) * jitter, adv))
            cx += adv
        return out

    def _text_cached(self, s, x, y, size, color, bold, hand, jitter, width) -> bool:
        """Fertig gesetzte Zeile als Alpha-Maske (Gerätepixel) zwischenspeichern und nur noch blitten.

        Die Schrift „kocht“ nicht mit (Seed ohne boil), eine Zeile sieht also immer gleich aus. Schlüssel enthält die
        Gerätematrix, die Position wird auf ganze Pixel gerundet (Teilpixel-Versatz bleibt in der Maske)."""
        if len(s) < 3 or _NOMASK:
            return False
        cr = self.cr
        m = cr.get_matrix()
        if abs(m.xy) > 1e-6 or abs(m.yx) > 1e-6:
            return False
        ds = cr.get_target().get_device_scale()[0] * HINT_SCALE
        mxx, myy = m.xx * ds, m.yy * ds
        dx, dy = (m.x0 + x * m.xx) * ds, (m.y0 + y * m.yy) * ds
        ix, iy = math.floor(dx), math.floor(dy)
        fx, fy = round((dx - ix) * 2) / 2, round((dy - iy) * 2) / 2
        key = (s, size, bold, hand, round(jitter, 2), self._fkey[0], round(mxx, 3), round(myy, 3), fx, fy, len(s))
        hit = _MASKS.get(key)
        if hit is None:
            asc = size * 1.4 * myy
            w_px = int(width * mxx + size * 1.2 * mxx + 8)
            h_px = int(size * 2.2 * myy + 8)
            if w_px > 4000 or h_px > 600:
                return False
            ox, oy = 4 + size * 0.3 * mxx, asc + 4
            surf = cairo.ImageSurface(cairo.FORMAT_A8, w_px, h_px)
            c2 = cairo.Context(surf)
            c2.translate(ox + fx, oy + fy)
            c2.scale(mxx, myy)
            fo = cr.get_font_options()
            c2.set_font_options(fo)
            c2.select_font_face(self._fkey[0], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
            c2.set_font_size(size)
            c2.set_source_rgb(0, 0, 0)
            self._glyphs(c2, s, 0.0, 0.0, size, jitter, x, y, hand)
            if len(_MASKS) > 3000:
                _MASKS.clear()
            hit = _MASKS[key] = (surf, ox, oy)
        surf, ox, oy = hit
        cr.save()
        cr.identity_matrix()
        cr.scale(1 / ds, 1 / ds)
        cr.set_source_rgb(*self.rgb(color))
        cr.mask_surface(surf, ix - ox, iy - oy)
        cr.restore()
        return True

    def _glyphs(self, cr, s, x0, y0, size, jitter, sx, sy, hand=False):
        r = random.Random(_seed(len(s), round(sx), round(sy)))
        cx = x0
        for ch in s:
            adv = self._adv(ch)
            if ch != " ":
                dy = r.uniform(-0.9, 0.9) * jitter * size / 18
                if hand:
                    dy += r.uniform(-HAND_WOBBLE, HAND_WOBBLE) * size / 18   # ruhige Handschrift-Grundlinie
                cr.save()
                self._select(cr, ch, size, self._bold, hand)
                cr.translate(cx + adv / 2, y0 + dy)
                cr.rotate(r.uniform(-HAND_TILT, HAND_TILT) * jitter)
                cr.move_to(-adv / 2, 0)
                cr.show_text(ch)
                cr.restore()
            cx += adv

    def wrap(self, text, size, maxw, bold=False, upper=True, hand=None) -> list[str]:
        """Zeilenumbruch an Wortgrenzen; überlange Wörter werden gekürzt."""
        rows, cur = [], ""
        for wd in str(text).split():
            cand = (cur + " " + wd).strip()
            if self.text_width(cand, size, bold, upper, hand) <= maxw or not cur:
                cur = cand
            else:
                rows.append(cur)
                cur = wd
        if cur:
            rows.append(cur)
        return [self.fit(r, size, maxw, bold, upper, hand) for r in rows]

    def text_block(self, text, maxw, maxh, size, min_size=11, max_lines=3, lh=1.2, bold=False, upper=False, hand=True):
        """Passt Text in einen Kasten: erst umbrechen, dann verkleinern, zuletzt mit … kürzen.

        Gibt (size, rows, breite, höhe) zurück; höhe = Zeilen * size * lh."""
        sz = size
        while True:
            rows = self.wrap(text, sz, maxw, bold, upper, hand)
            if (len(rows) <= max_lines and len(rows) * sz * lh <= maxh) or sz <= min_size:
                break
            sz -= 1
        fit_lines = max(1, min(max_lines, int(maxh // (sz * lh))))
        if len(rows) > fit_lines:
            rows = rows[:fit_lines]
            rows[-1] = self.fit(rows[-1] + " …", sz, maxw, bold, upper, hand)
        bw = max((self.text_width(r, sz, bold, upper, hand) for r in rows), default=0)
        return sz, rows, bw, len(rows) * sz * lh

    def draw_block(self, block, cx, cy, color=INK, bold=False, upper=False, hand=True, lh=1.2):
        """Zeichnet text_block()-Ergebnis zentriert um (cx, cy)."""
        sz, rows, _bw, bh = block
        y0 = cy - bh / 2 + sz * _BASELINE_EM.get(self.hand, 0.78)   # Oberlänge hängt von der Handschrift ab
        for i, row in enumerate(rows):
            self.text(row, cx, y0 + i * sz * lh, sz, color=color, align="center", bold=bold, upper=upper, hand=hand)

    def _circle_path(self, cx, cy, r):
        rr = random.Random(_seed(round(cx), round(cy), round(r), self.boil))
        a0, ph = rr.uniform(0, 6.28), rr.uniform(0, 6.28)
        n = max(12, int(r * 1.2))
        for i in range(n + 1):
            a = a0 + 2 * math.pi * i / n
            k = 1 + 0.045 * math.sin(2 * a + ph)
            (self.cr.move_to if i == 0 else self.cr.line_to)(cx + r * k * math.cos(a), cy + r * k * math.sin(a))
        self.cr.close_path()

    def cloud(self, cx, cy, a, b, color=INK, w=2.0):
        """Gedankenwolke: Bögen sitzen AUSSERHALB der Ellipse (a, b), das Innere bleibt frei für Text."""
        per = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
        n = max(8, round(per / 30))
        d = per / n
        rb = min(CLOUD_RB, d * 0.72)        # > d/2: Nachbarbögen schneiden sich außerhalb der Ellipse
        pts = [(cx + a * math.cos(2 * math.pi * (i + 0.3) / n), cy + b * math.sin(2 * math.pi * (i + 0.3) / n)) for i in range(n)]
        cr = self.cr
        cr.set_source_rgb(*self.rgb(color))          # Umriss der Vereinigung: dick umranden, dann innen weiß füllen
        for x, y in pts:
            self._circle_path(x, y, rb)
            cr.set_line_width(2 * w)
            cr.stroke()
        cr.set_source_rgb(*PAPER)
        for x, y in pts:
            self._circle_path(x, y, rb)
            cr.fill()
        cr.save()
        cr.translate(cx, cy)
        cr.scale(a, b)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
        return rb

    def think(self, text, cx, cy, maxw, maxh, tail, size=18, min_size=12, max_lines=3, color=INK, fixed=True):
        """Gedankenblase mit Text innerhalb von maxw×maxh (Außenmaß inkl. Bögen), Schwanz zu tail.

        fixed=True: Blase hat immer die volle Größe (wechselnder Text springt nicht)."""
        # Außenmaß = Ellipse + 2·Bogenradius; Bogenradius ≤ CLOUD_RB (siehe cloud())
        A, B = maxw / 2 - CLOUD_RB, maxh / 2 - CLOUD_RB
        inner_w, inner_h = A * 2 * 0.74, B * 2 * 0.68   # sicher im Inneren der Ellipse
        block = self.text_block(text, inner_w, inner_h, size, min_size, max_lines)
        if fixed:
            a, b = A, B
        else:
            a = max(A * 0.55, min(A, block[2] / 0.74 / 2 + 6))
            b = max(B * 0.55, min(B, block[3] / 0.68 / 2 + 6))
        rb = self.cloud(cx, cy, a, b, color=color)
        # Schwanz: kleiner werdende Kreise von der Wolke zum Kopf
        tx, ty = tail
        ang = math.atan2(ty - cy, tx - cx)
        sx, sy = cx + (a + rb * 0.8) * math.cos(ang), cy + (b + rb * 0.8) * math.sin(ang)
        for i, r in enumerate((7, 5, 3.4)):
            k = (i + 0.7) / 3.4
            self.circle(sx + (tx - sx) * k, sy + (ty - sy) * k, r, fill=PAPER, w=1.8, color=color)
        self.draw_block(block, cx, cy, color=color)
        geo = {"block": block, "cx": cx, "cy": cy, "a": a, "b": b, "rb": rb}
        self.bubbles.append(("think", geo))
        return geo

    def say(self, text, cx, cy, maxw, maxh, tail, size=18, min_size=12, max_lines=2, color=INK, bold=False, upper=False):
        """Sprechblase, an den Text angepasst (höchstens maxw×maxh), Spitze zeigt auf tail."""
        pad_x, pad_y = 16, 10
        bold = False                        # Comicschrift in Sprechblasen nie fett (Nutzerwunsch 0.6.0)
        block = self.text_block(text, maxw - 2 * pad_x, maxh - 2 * pad_y, size, min_size, max_lines, bold=bold, upper=upper)
        w = max(70, block[2] + 2 * pad_x)
        h = block[3] + 2 * pad_y
        x, y = cx - w / 2, cy - h / 2
        r = 12
        self.poly([(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)],
                  closed=True, fill=PAPER, color=color, w=2)
        # Spitze an der Unterkante, Richtung tail
        bx = min(max(tail[0] - 9, x + r + 2), x + w - r - 20)
        self.poly([(bx, y + h - 1), tail, (bx + 18, y + h - 1)], w=2, color=color)
        self.cr.move_to(bx + 2, y + h - 1.5)
        self.cr.line_to(bx + 16, y + h - 1.5)
        self.cr.set_source_rgb(*PAPER)
        self.cr.set_line_width(3)
        self.cr.stroke()
        self.draw_block(block, cx, cy, color=color, bold=bold, upper=upper)
        self.bubbles.append(("say", (x, y, w, h)))
        return (x, y, w, h)

    def bubbles_cover(self, px, py) -> bool:
        """Liegt der Punkt in einer der zuletzt gezeichneten Blasen (für die Reihenfolge des Fadens)?"""
        for kind, b in self.bubbles:
            if kind == "say":
                x, y, w, h = b
                if x - 2 <= px <= x + w + 2 and y - 2 <= py <= y + h + 2:
                    return True
            else:
                a, bb, rb = b["a"] + b["rb"], b["b"] + b["rb"], b["rb"]
                if ((px - b["cx"]) / a) ** 2 + ((py - b["cy"]) / bb) ** 2 <= 1.0:
                    return True
        return False

    def lines(self, text, x, y, size, maxw, max_lines=3, lh=1.25, **kw):
        """Einfacher Zeilenumbruch; gibt Anzahl gezeichneter Zeilen zurück."""
        words = str(text).split()
        rows, cur = [], ""
        for wd in words:
            cand = (cur + " " + wd).strip()
            if self.text_width(cand, size) <= maxw or not cur:
                cur = cand
            else:
                rows.append(cur)
                cur = wd
        if cur:
            rows.append(cur)
        if len(rows) > max_lines:
            rows = rows[:max_lines]
            rows[-1] = self.fit(rows[-1] + " …", size, maxw)
        for i, row in enumerate(rows):
            self.text(row, x, y + i * size * lh, size, maxw=maxw, **kw)
        return len(rows)

    # ------------------------------------------------------------------ Figur
    @staticmethod
    def _at(p, ang_deg, L):
        a = math.radians(ang_deg)
        return (p[0] + L * math.sin(a), p[1] + L * math.cos(a))

    @staticmethod
    def ik(root, target, L, bend):
        """Zwei gleich lange Glieder von root nach target. bend: Richtungsvektor, in den das Gelenk zeigt.

        Gibt absolute Winkel (oben, unten) in der Figur-Konvention zurück (0 = unten, + = rechts)."""
        dx, dy = target[0] - root[0], target[1] - root[1]
        d = max(1e-3, min(math.hypot(dx, dy), 2 * L * 0.999))
        base = math.degrees(math.atan2(dx, dy))
        alpha = math.degrees(math.acos(d / (2 * L)))
        best = None
        for sgn in (1, -1):
            up, lo = base + sgn * alpha, base - sgn * alpha
            a = math.radians(up)
            mx, my = L * math.sin(a), L * math.cos(a)
            # Gelenk relativ zur Verbindungslinie: Skalarprodukt mit bend
            score = (mx - dx / 2) * bend[0] + (my - dy / 2) * bend[1]
            if best is None or score > best[0]:
                best = (score, up, lo)
        return best[1], best[2]

    @classmethod
    def anchors(cls, x, y, s=1.0, lean=0.0, flip=False, look=0.0, head_dy=0.0):
        """Schulter, Hals, Kopf einer Figur berechnen, ohne zu zeichnen (für Zielpunkte der Hände)."""
        sg = -1 if flip else 1
        neck = cls._at((x, y), 180 + lean * sg, 48 * s)
        head = cls._at(neck, 180 + lean * sg + look * sg, 16 * s)
        return {"sh": cls._at((x, y), 180 + lean * sg, 40 * s), "neck": neck, "head": (head[0], head[1] + head_dy * s)}

    def figure(self, x, y, s=1.0, la=(20, 10), ra=(-20, -10), ll=(12, 0), rl=(-12, 0), lean=0.0,
               head_dy=0.0, color=INK, w=2.4, eyes=None, flip=False, hands=None, feet=None, look=0.0, splay=False):
        """Strichmännchen. (x, y) = Hüfte. Winkel in Grad, 0 = nach unten, positiv = nach rechts.
        la/ra = (Oberarm, Unterarm), ll/rl = (Oberschenkel, Unterschenkel); flip spiegelt diese Winkel.

        hands/feet = (links, rechts) absolute Zielpunkte (oder None je Glied): Gelenke per IK, Ellbogen
        zeigen nach unten/hinten, Knie nach vorn (vorn = rechts bei flip=True, sonst links).
        splay=True (Frontansicht, z. B. Tanz): Knie und Ellbogen zeigen nach außen, weg vom Körper.
        Gibt Hände, Füße, Knie, Kopf, Schulter, Hüfte zurück."""
        sg = -1 if flip else 1
        fwd = 1 if flip else -1             # Blickrichtung in x
        hip = (x, y)
        neck = self._at(hip, 180 + lean * sg, 48 * s)
        head = self._at(neck, 180 + lean * sg + look * sg, 16 * s)
        head = (head[0], head[1] + head_dy * s)
        sh = self._at(hip, 180 + lean * sg, 40 * s)

        def limb(root, ang, L1, L2, target=None, bend=(0, 1)):
            if target is not None:
                a0, a1 = self.ik(root, target, L1, bend)
            else:
                a0, a1 = ang[0] * sg, ang[1] * sg
            mid = self._at(root, a0, L1)
            end = self._at(mid, a1, L2)
            self.poly([root, mid, end], w=w, color=color, amp=0.5)
            return mid, end

        hands = hands or (None, None)
        feet = feet or (None, None)

        self.line(*hip, *neck, w=w, color=color, amp=0.6)
        self.circle(*head, 13 * s, w=w, color=color, fill=PAPER)
        elbow = (-fwd * 0.5, 1)              # Ellbogen hängen nach unten, leicht nach hinten
        knee = (fwd, -0.3)                   # Knie zeigen nach vorn/oben
        def out(root, target, side, down):
            if not splay or target is None:
                return None
            dx = target[0] - root[0]
            return (math.copysign(1.0, dx) if abs(dx) > 2 * s else side, down)
        _, hl = limb(sh, la, ARM * s, ARM * s, hands[0], out(sh, hands[0], 1, 0.6) or elbow)
        _, hr = limb(sh, ra, ARM * s, ARM * s, hands[1], out(sh, hands[1], -1, 0.6) or elbow)
        kl, fl = limb(hip, ll, LEG * s, LEG * s, feet[0], out(hip, feet[0], 1, -0.2) or knee)
        kr, fr = limb(hip, rl, LEG * s, LEG * s, feet[1], out(hip, feet[1], -1, -0.2) or knee)
        if eyes == "x":
            for dx in (-5, 4):
                ex, ey = head[0] + dx * s, head[1] - 2 * s
                self.line(ex - 2.5 * s, ey - 2.5 * s, ex + 2.5 * s, ey + 2.5 * s, w=1.6, color=color, amp=0)
                self.line(ex - 2.5 * s, ey + 2.5 * s, ex + 2.5 * s, ey - 2.5 * s, w=1.6, color=color, amp=0)
        elif eyes == "dots":
            for dx in (-4, 5):
                self.cr.arc(head[0] + dx * s * sg, head[1] - 2 * s, 1.6 * s, 0, 6.3)
                self.cr.set_source_rgb(*self.rgb(color))
                self.cr.fill()
        self.heads.append((hip, head))
        return {"hl": hl, "hr": hr, "head": head, "sh": sh, "hip": hip, "kl": kl, "kr": kr, "fl": fl, "fr": fr}

    @staticmethod
    def leg_drop(ll, rl, s=1.0) -> float:
        """Senkrechter Abstand Hüfte→tiefster Fuß für die Beinwinkel (unabhängig von flip)."""
        def drop(ang):
            return LEG * s * (math.cos(math.radians(ang[0])) + math.cos(math.radians(ang[1])))
        return max(drop(ll), drop(rl))

    # ------------------------------------------------------------------ Requisiten
    def desk(self, x, y, w, floor):
        self.line(x, y, x + w, y, w=2.6)
        self.line(x + 10, y, x + 12, floor)
        self.line(x + w - 10, y, x + w - 12, floor)

    def chair(self, x, y, floor, facing=1, s=1.0):
        """Seitenansicht. x = Sitzmitte, y = Sitzhöhe; facing=+1: Figur schaut nach rechts (Lehne links)."""
        hw = 22 * s
        self.line(x - hw, y, x + hw, y, w=2.6)
        self.line(x - hw + 3, y, x - hw + 1, floor)
        self.line(x + hw - 3, y, x + hw - 1, floor)
        bx = x - facing * hw
        self.line(bx, y, bx - facing * 7 * s, y - 50 * s, w=2.6)

    def laptop(self, x, y, s=1.0, glow=False):
        """x, y = Mitte der Unterkante; Bildschirm schaut nach links (zur Figur)."""
        self.line(x - 30 * s, y, x + 28 * s, y, w=2.6)
        self.line(x + 28 * s, y, x + 12 * s, y - 40 * s, w=2.6)
        if glow:
            for i in range(3):
                self.line(x + 6 * s - i * 6, y - 18 * s - i * 6, x - 14 * s - i * 9, y - 28 * s - i * 9, w=1, color=GRAY, amp=0.3)

    def hammer(self, hx, hy, ang):
        a = math.radians(ang)
        ex, ey = hx + 34 * math.sin(a), hy - 34 * math.cos(a)
        self.line(hx, hy, ex, ey, w=2.6)
        px, py = math.cos(a), math.sin(a)
        self.poly([(ex - 10 * px, ey - 10 * py), (ex + 12 * px, ey + 12 * py)], w=7)

    def pencil(self, hx, hy, ang, L=42):
        a = math.radians(ang)
        tx, ty = hx + L * 0.4 * math.sin(a), hy + L * 0.4 * math.cos(a)
        bx, by = hx - L * 0.6 * math.sin(a), hy - L * 0.6 * math.cos(a)
        px, py = math.cos(a) * 4, -math.sin(a) * 4
        self.poly([(bx + px, by + py), (tx + px * 0.6, ty + py * 0.6), (tx + 6 * math.sin(a), ty + 6 * math.cos(a)),
                   (tx - px * 0.6, ty - py * 0.6), (bx - px, by - py)], closed=True, w=1.8, fill=PAPER)

    def book(self, x, y, t=0.0, h=34.0, facing=-1):
        """Aufgeschlagenes Buch in Seitenansicht, der Leser schaut von der Seite drauf.

        (x, y) = Buchrücken (vom Leser weg), facing = Richtung zum Leser (-1 = links). Die Deckel bilden
        ein „>“, dazwischen fächern die Seiten; ab und zu blättert eine Seite um."""
        f = facing
        half = h / 2
        depth = h * 0.62
        top = (x + f * depth, y - half)                  # obere Deckelkante (zum Leser)
        bot = (x + f * depth * 0.9, y + half)            # untere Deckelkante
        self.poly([top, (x, y), bot], w=2.4, fill=None)
        # Seitenblock: leicht gewölbte Linien vom Rücken zum Leser
        for i in range(1, 4):
            k = i / 4
            ey = y - half + h * k
            ex = x + f * depth * (0.86 - 0.12 * abs(k - 0.5))
            self.poly([(x + f * 2, y), (x + f * depth * 0.5, (y + ey) / 2 - 2), (ex, ey)], w=0.9, color=GRAY, amp=0.2)
        # Umblättern: alle 3 s schwingt eine Seite von oben nach unten
        u = (t / 3.0) % 1.0
        if u < 0.25:
            k = u / 0.25
            ang = math.pi * k                             # 0 = oben, pi = unten
            ex = x + f * depth * 0.9 * math.cos(ang - math.pi / 2) ** 2 + f * 4
            ey = y - half * math.cos(ang)
            self.poly([(x, y), (x + f * depth * 0.55, (y + ey) / 2 - 3 * math.sin(ang)), (ex, ey)], w=1.2, color=INK, amp=0.2)

    def megaphone(self, hx, hy, t=0.0):
        self.poly([(hx, hy - 5), (hx + 30, hy - 16), (hx + 30, hy + 16), (hx, hy + 5)], closed=True, w=2, fill=PAPER)
        for i in range(3):
            r = 10 + i * 9 + 4 * ((t * 2) % 1)
            self.arc(hx + 32, hy, r, -0.6, 0.6, w=1.4, color=GRAY)

    def magnifier(self, hx, hy):
        self.line(hx, hy, hx + 12, hy - 12, w=3)
        self.circle(hx + 20, hy - 20, 10, w=2.2, fill=PAPER)

    def note(self, x, y, s=1.0, color=INK, double=False):
        """Musiknote (gezeichnet – die Schriften haben kein ♪). (x, y) = Notenkopf."""
        cr = self.cr
        cr.save()
        cr.translate(x, y)
        cr.rotate(-0.35)
        cr.scale(1.0, 0.72)
        cr.arc(0, 0, 4.2 * s, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(*self.rgb(color))
        cr.fill()
        top = y - 20 * s
        self.line(x + 3.6 * s, y - 1 * s, x + 3.6 * s, top, w=1.6 * s, color=color, amp=0)
        self.line(x + 3.6 * s, top, x + 10 * s, top + 6 * s, w=1.6 * s, color=color, amp=0)
        if double:
            self.line(x + 3.6 * s, top + 5 * s, x + 10 * s, top + 11 * s, w=1.6 * s, color=color, amp=0)

    def _fold_arc(self, x, y, W, H, r, a0, a1, seed, w, color=PINK):
        """Offener Windungsbogen (Gyrus): Teil eines Ringes mit leichter Welligkeit."""
        m = 40
        pts = []
        for i in range(m + 1):
            a = a0 + (a1 - a0) * i / m
            rr = r + 0.10 * r * (math.sin(4.3 * a + seed) * 0.6 + math.sin(7.1 * a + seed * 1.4) * 0.4)
            pts.append((x + W * math.cos(a) * rr, y + H * math.sin(a) * rr * 0.92))
        self.curve(pts, w=w, color=color)

    def _blob(self, cx, cy, rx, ry, seed, rot=0.0, n=12):
        """Rundlicher Knubbel (Kleinhirn) mit leicht welligem Rand."""
        cr = self.cr
        cr.new_path()
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            k = 1 + 0.12 * math.sin(3 * a + seed * 0.7) + 0.06 * math.sin(5 * a + seed)
            px = rx * k * math.cos(a) * math.cos(rot) - ry * k * math.sin(a) * math.sin(rot)
            py = rx * k * math.cos(a) * math.sin(rot) + ry * k * math.sin(a) * math.cos(rot)
            (cr.move_to if i == 0 else cr.line_to)(cx + px, cy + py)
        cr.close_path()

    def _cerebrum(self, x, y, W, H):
        """Grosshirnkontur: runde Kuppe mit sanften Lappenbuckeln, unterem Einschnitt fuers Kleinhirn."""
        cr = self.cr
        cr.new_path()
        n = 360
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            ct, st = math.cos(a), math.sin(a)
            bump = (1 + 0.048 * math.sin(9 * a + 0.4)
                    + 0.022 * math.sin(27 * a + 1.9) + 0.010 * math.sin(63 * a + 3.0))
            px = x + W * ct * bump
            py = y + H * st * bump
            px += W * 0.05 * (-ct)                       # vorn (links) etwas voller
            if ct > 0.12 and st < -0.02:                 # unten rechts ausschneiden fuers Kleinhirn
                k = (ct - 0.12) / 0.88 * ((-st - 0.02) / 0.98)
                px -= W * 0.26 * k
                py += H * 0.04 * k
            (cr.move_to if i == 0 else cr.line_to)(px, py)
        cr.close_path()

    def brain(self, x, y, s=1.0, color=PINK, fill=(1.0, 0.88, 0.93), seed=3):
        """Cartoon-Gehirn (pink) nahe den Vorlagen hirn1-3.

        Seitenansicht: Grosshirn aus wenigen dicken, in Boegen aufgeteilten Windungen (Gyri),
        geriffeltes Kleinhirn und Stiel unten rechts. (x, y) = Mitte; gibt die Stielspitze
        fuer den Modell-Faden zurueck."""
        coarse = s < 3.0                    # im Titel so klein, dass mehr Linien nur Matsch ergaeben
        W, H = 9.4 * s, 6.9 * s
        cr = self.cr
        w = max(1.0, 0.42 * s)
        # Kleinhirn zuerst (liegt unter dem Grosshirn)
        cx2, cy2 = x + W * 0.58, y + H * 0.70
        self._blob(cx2, cy2, 3.0 * s, 2.4 * s, seed + 9, rot=0.28)
        cr.set_source_rgb(*self.rgb(fill))
        cr.fill_preserve()
        cr.set_line_width(w * 1.1)
        cr.set_source_rgb(*self.rgb(color))
        cr.stroke()
        cr.save()
        self._blob(cx2, cy2, 3.0 * s, 2.4 * s, seed + 9, rot=0.28)
        cr.clip()
        for i in range(5):
            t = -1 + i * 0.5
            self.line(cx2 - 3.0 * s + 0.4 * s * t, cy2 + 0.5 * s + t * 0.85 * s,
                      cx2 + 2.8 * s + 0.4 * s * t, cy2 - 1.0 * s + t * 0.85 * s, w=w * 0.55, color=color, amp=0)
        cr.restore()
        stemx, stemy = cx2 + 0.2 * s, cy2 + 1.7 * s
        self.line(stemx, stemy, stemx - 0.8 * s, stemy + 4.2 * s, w=w * 1.3, color=color, amp=0)
        # Grosshirn
        self._cerebrum(x, y, W, H)
        cr.set_source_rgb(*self.rgb(fill))
        cr.fill_preserve()
        cr.set_line_width(w * 1.25)
        cr.set_source_rgb(*self.rgb(color))
        cr.stroke()
        cr.save()
        self._cerebrum(x, y, W, H)
        cr.clip()
        # wenige dicke Windungsboegen; jeder Ring in 2-3 Stuecke mit Luecken (Gyri)
        rings = ([(0.80, 2), (0.52, 3), (0.24, 2)] if coarse
                 else [(0.86, 2), (0.66, 3), (0.46, 2), (0.26, 3)])
        for ri, (r, pieces) in enumerate(rings):
            for q in range(pieces):
                a0 = 2 * math.pi * q / pieces + seed * 0.4 + ri * 0.9
                a1 = a0 + 2 * math.pi / pieces * (0.72 + 0.10 * (q % 2))
                self._fold_arc(x, y, W, H, r, a0, a1, seed + ri * 1.7 + q * 3.1, w, color=color)
        # Sylvische Furche
        self.curve([(x - W * 0.78, y + H * 0.10), (x - W * 0.28, y + H * 0.36),
                    (x + W * 0.20, y + H * 0.28), (x + W * 0.54, y - H * 0.04)], w=w * 1.15, color=color)
        cr.restore()
        return (stemx - 0.8 * s, stemy + 4.2 * s)

    def coin(self, x, y, r=7, color=INK, fill=(1.0, 0.93, 0.55)):
        self.circle(x, y, r, w=1.6, color=color, fill=fill)
        self.text("T", x, y + r * 0.45, r * 1.3, align="center", color=color, jitter=0)

    def smoke(self, x, y, t, n=4, color=GRAY, scale=1.0):
        for i in range(n):
            k = ((t * 0.6 + i / n) % 1)
            self.circle(x + 10 * scale * math.sin(k * 6 + i), y - k * 70 * scale, (5 + k * 14) * scale, w=1.6, color=color)

    def flame(self, x, y, t, h=26):
        pts = []
        for i in range(7):
            k = i / 6
            yy = y - (h if i % 2 else h * 0.4) * (1 - abs(k - 0.5) * 1.2) * (0.85 + 0.15 * math.sin(t * 9 + i))
            pts.append((x - 18 + 36 * k, yy))
        self.poly([(x - 18, y)] + pts + [(x + 18, y)], w=2, color=RED, fill=(1.0, 0.85, 0.6))

    def check(self, x, y, s=1.0, color=INK):
        self.poly([(x - 8 * s, y), (x - 2 * s, y + 7 * s), (x + 10 * s, y - 9 * s)], w=3, color=color)

    def tally(self, x, y, n, h=18, color=INK, maxn=25):
        """Strichliste: Viererbündel mit Querstrich."""
        cx = x
        for g in range(0, min(n, maxn), 5):
            k = min(5, n - g)
            for i in range(min(k, 4)):
                self.line(cx + i * 6, y, cx + i * 6 + 1, y - h, w=2, color=color)
            if k == 5:
                self.line(cx - 4, y - 4, cx + 24, y - h + 4, w=2, color=color)
            cx += 34
        if n > maxn:
            self.text(f"+{n - maxn}", cx, y, 14, color=color)
            cx += 30
        return cx - x
