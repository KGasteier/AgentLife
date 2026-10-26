"""xkcd-artige Zeichenprimitive auf Cairo: wackelige Linien, Handschrift, Strichmännchen, Requisiten.

Alle Koordinaten sind logische Einheiten im aktuellen Cairo-Koordinatensystem.
Das Wackeln ist deterministisch (Seed aus Koordinaten + `boil`), damit Linien nicht
flimmern; `boil` wechselt langsam und erzeugt den typischen "lebendigen" Strich.
"""

from __future__ import annotations

import math
import random
import subprocess
from functools import lru_cache

import cairo

INK = (0.07, 0.07, 0.07)
RED = (0.82, 0.12, 0.10)
BLUE = (0.16, 0.36, 0.74)
GRAY = (0.6, 0.6, 0.6)
LIGHT = (0.86, 0.86, 0.86)
PAPER = (1.0, 1.0, 1.0)

FONT_CANDIDATES = ["xkcd Script", "xkcd", "Humor Sans", "Comic Neue", "URW Gothic"]


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


_ADV: dict = {}


def _seed(*k) -> int:
    return hash(tuple(round(v, 1) if isinstance(v, float) else v for v in k)) & 0xFFFFFFFF


class Pen:
    def __init__(self, cr: cairo.Context, boil: int = 0, font: str | None = None):
        self.cr = cr
        self.boil = boil
        self.font = font or pick_font()
        self._cache: dict = {}
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

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

    def _stroke(self, color, w, dash=None):
        cr = self.cr
        cr.set_source_rgb(*color)
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
    def _font(self, size, bold=False):
        self.cr.select_font_face(self.font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(size)
        self._fkey = (round(size, 2), bold)

    def _adv(self, ch):
        """Vorschub eines Zeichens; Cache über alle Frames (Schrift ändert sich nicht)."""
        k = (self._fkey, ch)
        v = _ADV.get(k)
        if v is None:
            v = self.cr.text_extents(ch).x_advance
            if len(_ADV) > 20000:
                _ADV.clear()
            _ADV[k] = v
        return v

    def text_width(self, s, size, bold=False, upper=True):
        s = s.upper() if upper else s
        self._font(size, bold)
        return sum(self._adv(ch) for ch in s)

    def fit(self, s, size, maxw, bold=False, upper=True):
        """Kürzt s mit … auf maximale Breite."""
        if self.text_width(s, size, bold, upper) <= maxw:
            return s
        while s and self.text_width(s + "…", size, bold, upper) > maxw:
            s = s[:-1]
        return s + "…"

    def text(self, s, x, y, size=18, color=INK, align="left", bold=False, upper=True, jitter=1.0, maxw=None):
        """Handschriftartige Zeile: Großbuchstaben, jedes Zeichen leicht versetzt/gedreht."""
        s = str(s)
        if maxw:
            s = self.fit(s, size, maxw, bold, upper)
        s = s.upper() if upper else s
        cr = self.cr
        self._font(size, bold)
        width = sum(self._adv(ch) for ch in s)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        cr.set_source_rgb(*color)
        r = random.Random(_seed(len(s), round(x), round(y), self.boil))
        cx = x
        for ch in s:
            adv = self._adv(ch)
            if ch != " ":
                cr.save()
                cr.translate(cx + adv / 2, y + r.uniform(-0.9, 0.9) * jitter * size / 18)
                cr.rotate(r.uniform(-0.05, 0.05) * jitter)
                cr.move_to(-adv / 2, 0)
                cr.show_text(ch)
                cr.restore()
            cx += adv
        return width

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

    def figure(self, x, y, s=1.0, la=(20, 10), ra=(-20, -10), ll=(12, 0), rl=(-12, 0), lean=0.0,
               head_dy=0.0, color=INK, w=2.4, eyes=None, flip=False):
        """Strichmännchen. (x, y) = Hüfte. Winkel in Grad, 0 = nach unten, positiv = nach rechts.
        la/ra = (Oberarm, Unterarm), ll/rl = (Oberschenkel, Unterschenkel). Gibt Hände/Kopf zurück."""
        sg = -1 if flip else 1
        hip = (x, y)
        neck = self._at(hip, 180 + lean * sg, 48 * s)
        head = self._at(neck, 180 + lean * sg, 16 * s)
        head = (head[0], head[1] + head_dy * s)
        sh = self._at(hip, 180 + lean * sg, 40 * s)

        def limb(root, ang, L1, L2):
            mid = self._at(root, ang[0] * sg, L1)
            end = self._at(mid, ang[1] * sg, L2)
            self.poly([root, mid, end], w=w, color=color, amp=0.5)
            return end

        self.line(*hip, *neck, w=w, color=color, amp=0.6)
        self.circle(*head, 13 * s, w=w, color=color, fill=PAPER)
        hl = limb(sh, la, 20 * s, 20 * s)
        hr = limb(sh, ra, 20 * s, 20 * s)
        limb(hip, ll, 24 * s, 24 * s)
        limb(hip, rl, 24 * s, 24 * s)
        if eyes == "x":
            for dx in (-5, 4):
                ex, ey = head[0] + dx * s, head[1] - 2 * s
                self.line(ex - 2.5 * s, ey - 2.5 * s, ex + 2.5 * s, ey + 2.5 * s, w=1.6, color=color, amp=0)
                self.line(ex - 2.5 * s, ey + 2.5 * s, ex + 2.5 * s, ey - 2.5 * s, w=1.6, color=color, amp=0)
        elif eyes == "dots":
            for dx in (-4, 5):
                self.cr.arc(head[0] + dx * s * sg, head[1] - 2 * s, 1.6 * s, 0, 6.3)
                self.cr.set_source_rgb(*color)
                self.cr.fill()
        return {"hl": hl, "hr": hr, "head": head, "sh": sh, "hip": hip}

    # ------------------------------------------------------------------ Requisiten
    def bubble(self, x, y, w, h, tail, kind="speech", color=INK):
        if kind == "thought":
            cx, cy = x + w / 2, y + h / 2
            n = 11
            for i in range(n):
                a = 2 * math.pi * i / n
                self.circle(cx + (w / 2 - 6) * math.cos(a), cy + (h / 2 - 6) * math.sin(a), min(w, h) * 0.2, fill=PAPER, color=color, w=2)
            self.rect(x + 8, y + 8, w - 16, h - 16, lw=0, color=PAPER, fill=PAPER)
            self.cr.rectangle(x + 6, y + 6, w - 12, h - 12)
            self.cr.set_source_rgb(*PAPER)
            self.cr.fill()
            tx, ty = tail
            for i, rr in enumerate((7, 5, 3.5)):
                k = (i + 1) / 4
                self.circle(cx + (tx - cx) * (0.55 + k * 0.5), y + h + (ty - y - h) * k * 1.2, rr, fill=PAPER, w=1.8)
        else:
            r = 10
            self.poly([(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)],
                      closed=True, fill=PAPER, color=color, w=2)
            bx = min(max(tail[0], x + 25), x + w - 45)
            self.poly([(bx, y + h - 1), tail, (bx + 22, y + h - 1)], w=2, color=color)
            self.cr.move_to(bx + 2, y + h - 2)
            self.cr.line_to(bx + 20, y + h - 2)
            self.cr.set_source_rgb(*PAPER)
            self.cr.set_line_width(3)
            self.cr.stroke()

    def desk(self, x, y, w, floor):
        self.line(x, y, x + w, y, w=2.6)
        self.line(x + 10, y, x + 12, floor)
        self.line(x + w - 10, y, x + w - 12, floor)

    def chair(self, x, y, floor):
        self.line(x - 22, y, x + 22, y, w=2.4)
        self.line(x - 20, y, x - 22, floor)
        self.line(x + 18, y, x + 20, floor)
        self.line(x - 22, y, x - 28, y - 55, w=2.4)

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

    def book(self, hx, hy, t=0.0):
        flap = 3 * math.sin(t * 3)
        self.poly([(hx - 26, hy - 18 + flap), (hx, hy - 12), (hx + 26, hy - 18 - flap), (hx + 26, hy + 4 - flap), (hx, hy + 10), (hx - 26, hy + 4 + flap)],
                  closed=True, w=2, fill=PAPER)
        self.line(hx, hy - 12, hx, hy + 10, w=1.6)
        for i in range(3):
            self.line(hx - 21, hy - 10 + i * 6, hx - 5, hy - 6 + i * 6, w=0.9, color=GRAY, amp=0.2)
            self.line(hx + 5, hy - 6 + i * 6, hx + 21, hy - 10 + i * 6, w=0.9, color=GRAY, amp=0.2)

    def megaphone(self, hx, hy, t=0.0):
        self.poly([(hx, hy - 5), (hx + 30, hy - 16), (hx + 30, hy + 16), (hx, hy + 5)], closed=True, w=2, fill=PAPER)
        for i in range(3):
            r = 10 + i * 9 + 4 * ((t * 2) % 1)
            self.arc(hx + 32, hy, r, -0.6, 0.6, w=1.4, color=GRAY)

    def magnifier(self, hx, hy):
        self.line(hx, hy, hx + 12, hy - 12, w=3)
        self.circle(hx + 20, hy - 20, 10, w=2.2, fill=PAPER)

    def coin(self, x, y, r=7, color=INK):
        self.circle(x, y, r, w=1.6, color=color, fill=(1.0, 0.93, 0.55))
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
