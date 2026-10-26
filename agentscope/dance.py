"""Tanzschritte der Subagent-Minions (laufende Subagents tanzen bei der Arbeit).

Jeder Stil liefert pro Zeitpunkt Hüfte, Hand- und Fußziele (absolute Punkte) für `Pen.figure`, dazu
Neigung und Requisiten. Frontansicht nutzt `splay=True` (Knie/Ellbogen nach außen), Seitenansicht
(Twerk, Moonwalk) Knie nach vorn. Alle Größen skalieren mit s; Füße stehen auf `base`, solange nicht
gesprungen wird.
"""

from __future__ import annotations

import math

from .sketch import ARM, GRAY, INK, LEG, Pen

DANCES = ("disco", "gangnam", "twerk", "tap", "irish", "ymca", "floss", "moonwalk")
DANCE_SWITCH_S = 12.0     # jeder Minion wechselt so oft den Tanz


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _mix(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def pick(name: str, i: int, t: float) -> str:
    """Stabiler, aber wechselnder Tanz je Minion (Nachbarn tanzen verschieden)."""
    h = sum(ord(c) * (k + 1) for k, c in enumerate(name or "?"))
    return DANCES[(h + 3 * i + int(t / DANCE_SWITCH_S)) % len(DANCES)]


def pose(style: str, t: float, cx: float, base: float, s: float) -> dict:
    """Gelenkziele eines Tanzes. Gibt hip, hands, feet, lean, flip, splay, crouch und props zurück."""
    L, A = LEG * s, ARM * s
    lift, lean, flip, splay, look = 0.0, 0.0, False, True, 0.0
    props: list = []
    hx = cx
    if style == "disco":                         # Saturday Night Fever: Finger hoch – runter über Kreuz
        b = t * 2.0
        k = _ease(abs(((b % 2) - 1)))            # 1 = oben, 0 = unten
        hx += 2.5 * s * math.sin(math.pi * b)
        crouch = 2 * s * (1 - k)
        hy = base - 2 * L + crouch
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        hand_r = _mix((sh[0] - 0.9 * A, sh[1] + 1.4 * A), (sh[0] + 1.3 * A, sh[1] - 1.4 * A), k)
        hand_l = (sh[0] - 0.8 * A, sh[1] + 1.1 * A)          # Hand in der Hüfte
        tap = abs(math.sin(math.pi * b))
        feet = ((hx - 0.35 * L, base), (hx + 0.45 * L + 0.25 * L * tap, base - 0.15 * L * tap))
        lean = -6 * k + 3
    elif style == "gangnam":                     # Galopp-Hüpfer, Handgelenke gekreuzt / Lasso
        b = t * 2.6
        lift = abs(math.sin(math.pi * b)) * 0.28 * L
        hy = base - 2 * L - lift
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        up = int(b / 4) % 2 == 1
        if up:                                   # Lasso über dem Kopf
            w = t * 9
            hand_r = (sh[0] + 0.3 * A + 0.35 * A * math.cos(w), sh[1] - 1.55 * A + 0.15 * A * math.sin(w))
            hand_l = (sh[0] - 0.2 * A, sh[1] + 0.8 * A)
            props.append(("lasso", hand_r, 0.35 * A, w))
        else:                                    # gekreuzte Handgelenke vor der Brust
            hand_r = (sh[0] - 0.15 * A, sh[1] + 0.75 * A + 0.1 * A * math.sin(math.pi * b))
            hand_l = (sh[0] + 0.15 * A, sh[1] + 0.75 * A + 0.1 * A * math.sin(math.pi * b))
        alt = int(b) % 2
        fy = base - lift
        feet = ((hx - 0.35 * L, fy - (0.35 * L if alt else 0)), (hx + 0.35 * L, fy - (0 if alt else 0.35 * L)))
        props.append(("shades",))
    elif style == "twerk":                       # Seitenansicht: tief in der Hocke, Po wippt schnell
        flip, splay = False, False               # schaut nach links, Po zeigt nach rechts
        b = t * 5.0
        bounce = math.sin(2 * math.pi * b)
        crouch = 0.55 * L + 0.12 * L * bounce
        hx += 0.2 * L + 0.08 * L * bounce
        hy = base - 2 * L + crouch
        lean = 48 + 6 * bounce
        feet = ((hx - 0.55 * L, base), (hx - 0.3 * L, base))
        knee = (hx - 0.95 * L, hy + 0.25 * L)
        hand_l = hand_r = knee                   # Hände auf den Knien
        props.append(("wiggle", (hx + 0.35 * L, hy - 0.1 * L), bounce))
    elif style == "tap":                         # Stepptanz mit Zylinder und Stock
        b = t * 3.0
        hy = base - 2 * L + 1.5 * s * abs(math.sin(math.pi * b))
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        sw = math.sin(math.pi * b)
        hand_l = (sh[0] - 0.9 * A + 0.3 * A * sw, sh[1] + 1.5 * A)
        hand_r = (sh[0] + 1.1 * A, sh[1] + 1.0 * A - 0.3 * A * abs(sw))
        heel = int(b) % 2
        toe = abs(math.sin(math.pi * b * 2))
        feet = ((hx - 0.3 * L, base), (hx + 0.4 * L + 0.15 * L * heel, base - 0.25 * L * toe))
        props.append(("tophat",))
        props.append(("cane", hand_r, base))
        if toe > 0.97:
            props.append(("tap", feet[1]))
    elif style == "irish":                       # Riverdance: Arme steif, Oberkörper still, Beine fliegen
        b = t * 3.2
        lift = abs(math.sin(math.pi * b)) * 0.18 * L
        hy = base - 2 * L - lift
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        hand_l, hand_r = (sh[0] - 0.22 * A, sh[1] + 1.95 * A), (sh[0] + 0.22 * A, sh[1] + 1.95 * A)
        kick = _ease(abs(math.sin(math.pi * b / 2)))
        side = 1 if int(b / 2) % 2 else -1
        fy = base - lift
        plant = (hx - side * 0.1 * L, fy)
        fly = (hx + side * (0.25 + 0.65 * kick) * L, fy - kick * 0.9 * L)
        feet = (fly, plant) if side < 0 else (plant, fly)
    elif style == "ymca":                        # Buchstaben mit den Armen
        letters = "YMCA"
        n = int(t / 0.7) % 4
        ch = letters[n]
        hy = base - 2 * L + 1.5 * s * abs(math.sin(t * 4.5))
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        hd = Pen.anchors(hx, hy, s=s)["head"]
        if ch == "Y":
            hand_l, hand_r = (sh[0] - 1.25 * A, sh[1] - 1.4 * A), (sh[0] + 1.25 * A, sh[1] - 1.4 * A)
        elif ch == "M":
            hand_l, hand_r = (hd[0] - 0.4 * A, hd[1] - 0.7 * A), (hd[0] + 0.4 * A, hd[1] - 0.7 * A)
        elif ch == "C":
            hand_l, hand_r = (sh[0] - 1.2 * A, sh[1] - 1.0 * A), (sh[0] - 1.1 * A, sh[1] + 0.9 * A)
        else:
            hand_l, hand_r = (hd[0] - 0.12 * A, hd[1] - 0.95 * A), (hd[0] + 0.12 * A, hd[1] - 0.95 * A)
        feet = ((hx - 0.4 * L, base), (hx + 0.4 * L, base))
        props.append(("letter", ch, (hx + 1.9 * A, hd[1] - 0.4 * A)))
    elif style == "floss":                       # Arme pendeln vor/hinter dem Körper, Hüfte gegenläufig
        b = t * 3.4
        k = math.sin(math.pi * b)
        hx -= 3 * s * k
        hy = base - 2 * L
        sh = Pen.anchors(hx, hy, s=s)["sh"]
        dx = 1.15 * A * k
        hand_l = (sh[0] + dx - 0.15 * A, sh[1] + 1.55 * A)
        hand_r = (sh[0] + dx + 0.15 * A, sh[1] + 1.6 * A)
        feet = ((cx - 0.3 * L, base), (cx + 0.3 * L, base))
        lean = -4 * k
    else:                                        # moonwalk: gleitet rückwärts, Fersen wechseln
        flip, splay = False, False               # schaut nach links, gleitet nach rechts
        period = 2.4
        u = (t / period) % 1
        hx += -0.8 * L + 1.6 * L * u
        b = t * 2.5
        alt = int(b) % 2
        hy = base - 2 * L + 1.0 * s
        sh = Pen.anchors(hx, hy, s=s, lean=-3)["sh"]
        flat, heel = (hx - 0.1 * L, base), (hx + 0.35 * L, base - 0.22 * L)
        feet = (flat, heel) if alt else ((heel[0] - 0.45 * L, heel[1]), (flat[0] + 0.45 * L, flat[1]))
        hand_l, hand_r = (sh[0] - 0.7 * A, sh[1] + 1.3 * A), (sh[0] + 0.5 * A, sh[1] + 1.5 * A)
        lean = -3
        props.append(("glove", hand_r))
    hip = (hx, hy)
    return {"style": style, "hip": hip, "hands": (hand_l, hand_r), "feet": feet, "lean": lean,
            "flip": flip, "splay": splay, "look": look, "props": props}


def draw(p: Pen, style: str, t: float, cx: float, base: float, s: float, color=INK) -> dict:
    """Zeichnet einen tanzenden Minion samt Requisiten; gibt das Figurergebnis zurück."""
    d = pose(style, t, cx, base, s)
    f = p.figure(*d["hip"], s=s, lean=d["lean"], flip=d["flip"], hands=d["hands"], feet=d["feet"],
                 splay=d["splay"], look=d["look"], color=color)
    head = f["head"]
    for pr in d["props"]:
        kind = pr[0]
        if kind == "shades":
            p.line(head[0] - 9 * s, head[1] - 2 * s, head[0] + 9 * s, head[1] - 2 * s, w=4 * s, color=INK, amp=0)
        elif kind == "lasso":
            (x, y), r, w = pr[1], pr[2], pr[3]
            p.cr.save()
            p.cr.translate(x, y - 2 * s)
            p.cr.scale(1.0, 0.35)
            p.cr.arc(0, 0, r + 6 * s, 0, 2 * math.pi)
            p.cr.restore()
            p.cr.set_source_rgb(*GRAY)
            p.cr.set_line_width(1.2)
            p.cr.stroke()
        elif kind == "tophat":
            p.rect(head[0] - 6 * s, head[1] - 13 * s - 14 * s, 12 * s, 14 * s, lw=1.8, fill=INK)
            p.line(head[0] - 11 * s, head[1] - 13 * s, head[0] + 11 * s, head[1] - 13 * s, w=2.2, amp=0)
        elif kind == "cane":
            (x, y), b = pr[1], pr[2]
            p.line(x, y, x + 6 * s, b, w=2, amp=0.2)
            p.arc(x - 3 * s, y, 3 * s, math.pi, 2 * math.pi, w=2)
        elif kind == "tap":
            x, y = pr[1]
            p.text("tap!", x + 6 * s, y - 2, 10, color=GRAY, hand=True, upper=False)
        elif kind == "wiggle":
            (x, y), k = pr[1], pr[2]
            for i in range(2):
                r = (8 + 6 * i) * s
                p.arc(x, y, r, -0.9, 0.9, w=1.3, color=GRAY)
        elif kind == "letter":
            ch, (x, y) = pr[1], pr[2]
            p.text(ch, x, y, 18, align="center", bold=True, color=GRAY)
        elif kind == "glove":
            x, y = pr[1]
            p.circle(x, y, 3.2 * s, w=1.4, fill=(1, 1, 1))
    return f
