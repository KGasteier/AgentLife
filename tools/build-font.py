"""steel-umlaut-city.regular.ttf: Steel City Comic + Umlaute/ß im gleichen Stil.
Die leeren Umlaut-Slots werden mit den Basis-Konturen plus zwei Punkten gefüllt;
ß wird aus drei monoline-Baendern (Stamm, Haken, Schleife) gezeichnet."""
import math
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen

SRC = "/home/kg/Work/omarchy-agentscope/agentscope/fonts/SteelCityComic-Regular.ttf"
DST = "/home/kg/Work/omarchy-agentscope/agentscope/fonts/steel-umlaut-city.regular.ttf"

R = 84.0        # Punktradius (Durchmesser ~168 = Strichstaerke)
HALF = 84.0     # halbe Bandbreite fuer das ß

font = TTFont(SRC)
glyf = font["glyf"]
gs = font.getGlyphSet()


def dot(pen, cx, cy, r, wob, seed):
    k = r
    def w(i):
        return wob * math.sin(seed * 2.7 + i * 1.9)
    pts = [(cx + r, cy), (cx, cy - r), (cx - r, cy), (cx, cy + r)]
    pts = [(px + w(i), py + w(i + 1)) for i, (px, py) in enumerate(pts)]
    pen.moveTo(pts[0])
    pen.qCurveTo((cx + k, cy - k), pts[1])
    pen.qCurveTo((cx - k, cy - k), pts[2])
    pen.qCurveTo((cx - k, cy + k), pts[3])
    pen.qCurveTo((cx + k, cy + k), pts[0])
    pen.closePath()


UM = {
    "Adieresis": ("A", 300, 600, 1730),
    "Odieresis": ("O", 470, 850, 1730),
    "Udieresis": ("U", 340, 700, 1730),
    "adieresis": ("a", 265, 590, 1130),
    "odieresis": ("o", 265, 590, 1130),
    "udieresis": ("u", 225, 530, 1130),
}
for name, (base, x1, x2, y) in UM.items():
    pen = TTGlyphPen(gs)
    gs[base].draw(pen)
    dot(pen, x1, y, R, 3.0, 1)
    dot(pen, x2, y, R, 3.0, 2)
    glyf[name] = pen.glyph()
    glyf[name].recalcBounds(glyf)


def band(pen, path, half):
    """Monoline-Band entlang eines Mittelpfads (Catmull-Rom -> dichte Folge)."""
    P = [path[0]] + list(path) + [path[-1]]
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(16):
            t = j / 16; t2 = t * t; t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            dense.append((x, y))
    dense.append(P[-2])
    nrm = []
    for i, p in enumerate(dense):
        a = dense[max(0, i - 1)]; b = dense[min(len(dense) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1
        nrm.append((-dy / L, dx / L))
    left = [(p[0] + n[0] * half, p[1] + n[1] * half) for p, n in zip(dense, nrm)]
    right = [(p[0] - n[0] * half, p[1] - n[1] * half) for p, n in zip(dense, nrm)]
    pen.moveTo(left[0])
    for p in left[1:]:
        pen.lineTo(p)
    for p in reversed(right):
        pen.lineTo(p)
    pen.closePath()


pen = TTGlyphPen(gs)
band(pen, [(150, 120), (150, 1150), (150, 1420)], 86)                                   # Stamm
band(pen, [(150, 1400), (330, 1500), (480, 1430), (500, 1280), (400, 1120), (300, 1060)], 80)   # Haken
band(pen, [(300, 1060), (470, 1000), (650, 860), (720, 600), (680, 320), (520, 120), (320, 70), (220, 140)], 84)  # Schleife
glyf["germandbls"] = pen.glyph()
glyf["germandbls"].recalcBounds(glyf)

# Eigener Familienname, damit beide Schriften nebeneinander registriert werden koennen
# (sonst greift fontconfig womoeglich die leere Originaldatei mit gleichem Namen).
FAMILY = "Steel Umlaut City"
FULL = "Steel Umlaut City Regular"
PS = "SteelUmlautCity-Regular"
for rec in font["name"].names:
    if rec.nameID in (1, 4):
        rec.string = FAMILY
    elif rec.nameID == 6:
        rec.string = PS
    elif rec.nameID == 3:
        rec.string = FULL
    elif rec.nameID in (16, 17):
        rec.string = FAMILY if rec.nameID == 16 else "Regular"

font["post"].italicAngle = 0.0
font.save(DST)
print("gespeichert:", DST, "als", FAMILY)
