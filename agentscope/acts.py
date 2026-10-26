"""Abwechslung für den Hauptagenten: Varianten je Phase, Siegestanz, Idle-Miniszenen, Besucher.

Jede Phase hat mehrere Varianten (Index 0 = die klassische Pose in scene.py). Welche läuft, entscheidet
`variant()`: deterministisch aus Agent und Zeit, wechselt alle VARIANT_S Sekunden, wiederholt nie
direkt dieselbe. Ist ein Prozess fertig geworden (`Agent.idle_for` < FINALE_S), tanzt der Agent auf dem
Tisch. Alles hier ist beweglich (dynamische Ebene); nichts davon ist zwischengespeichert.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

from . import dance
from . import scene as S
from .sketch import BLUE, GRAY, INK, LEG, PAPER, RED, Pen

VARIANT_S = 10.0       # so lange läuft eine Variante einer Phase
IDLE_SLOT_S = 14.0     # so lange läuft eine Idle-Szene
FINALE_S = 15.0        # so lange tanzt der Agent nach getaner Arbeit
FORCE: dict = {}       # Vorschau/Tests: {"variant": n} erzwingt eine Variante

FLOOR = S.FLOOR

def kh(s: str) -> int:
    """Stabiler String-Hash (Python-hash() ist je Start zufällig)."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(s or "?"))

def _perm(key: str, name: str, rnd: int, n: int) -> list[int]:
    return sorted(range(n), key=lambda i: (S._hash01(kh(key), kh(name), rnd, i), i))

def variant(key: str, name: str, t: float, n: int, period: float = VARIANT_S) -> int:
    """Variante 0…n-1 zum Zeitpunkt t: in jeder Runde eine neue Mischung, nie zweimal hintereinander gleich."""
    if n <= 1:
        return 0
    if FORCE.get("variant") is not None:
        return FORCE["variant"] % n
    slot = int(t / period)
    if n == 2:
        return (slot + kh(key)) % 2
    rnd, i = divmod(slot, n)
    perm = _perm(key, name, rnd, n)
    if rnd > 0 and perm[0] == _perm(key, name, rnd - 1, n)[-1]:
        perm[0], perm[1] = perm[1], perm[0]
    return perm[i]

def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def _mix(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)

def _seq(u: float, keys):
    """Hand-Weg: keys = [(zeit, punkt), …] aufsteigend; dazwischen weich überblendet."""
    if u <= keys[0][0]:
        return keys[0][1]
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if u < t1:
            return _mix(p0, p1, _ease((u - t0) / (t1 - t0)))
    return keys[-1][1]

def _frag(a, t):
    words = (a.prompt or "hmm…").split()
    k = int(t * 0.5) * 7 % max(1, len(words))
    return (" ".join(words[k:k + 9]) or "…") + " " + "." * (1 + int(t * 2) % 3)

def _mug(p: Pen, x, y, steam_t=None):
    """Tasse, (x, y) = Mitte des Bodens."""
    p.poly([(x - 6, y - 14), (x - 5, y), (x + 5, y), (x + 6, y - 14)], w=2, fill=PAPER)
    p.arc(x + 6, y - 8, 4.5, -1.5, 1.5, w=1.8)
    if steam_t is not None:
        p.smoke(x, y - 16, steam_t, n=2, scale=0.35)

def _plane(p: Pen, x, y, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    def r(dx, dy):
        return (x + dx * ca - dy * sa, y + dx * sa + dy * ca)
    p.poly([r(13, 0), r(-10, -6), r(-6, 0), r(-10, 3)], closed=True, w=1.6, fill=PAPER)
    p.line(*r(13, 0), *r(-6, 0), w=1.2, amp=0)

def _walk_feet(fx, w, stance=9, step=13, lift=7):
    return ((fx - stance + step * math.sin(w), FLOOR - lift * max(0, math.cos(w))),
            (fx + stance - step * math.sin(w), FLOOR - lift * max(0, -math.cos(w))))

def _stand_hip():
    return FLOOR - 2 * LEG + 0.5

# ====================================================================== Denken
def think_pace(p, a, t, c):
    ph = t * 0.55
    fx = 100 + 60 * math.sin(ph)
    flip = math.cos(ph) > 0
    an = Pen.anchors(fx, _stand_hip(), flip=flip)
    side = 1 if flip else -1
    chin = (an["head"][0] + side * 9, an["head"][1] + 15)
    back = (an["sh"][0] - side * 12, an["sh"][1] + 34)
    h = p.figure(fx, _stand_hip(), flip=flip, feet=_walk_feet(fx, t * 4.2), hands=(chin, back))
    S.think_at(p, h["head"], _frag(a, t))
    return "läuft grübelnd auf und ab"

def think_back(p, a, t, c):
    lean = -24 + 2 * math.sin(t * 0.8)
    hd = S.seated_at(c.hip, lean=lean, look=-18)["head"]
    h = S.seated(p, c.hip, lean=lean, look=-18, hands=((hd[0] - 13, hd[1] + 8), (hd[0] - 17, hd[1] + 17)))
    hx, hy = h["head"]
    if t % 7 < 1.8:                                           # Geistesblitz
        bx, by = hx + 34, hy - 48
        p.circle(bx, by, 10, w=2, fill=(1.0, 0.93, 0.55))
        p.line(bx - 4, by + 10, bx + 4, by + 10, w=2, amp=0)
        p.line(bx - 3, by + 14, bx + 3, by + 14, w=2, amp=0)
        for i in range(6):
            ang = i * math.pi / 3 + t
            p.line(bx + 15 * math.cos(ang), by + 15 * math.sin(ang), bx + 22 * math.cos(ang), by + 22 * math.sin(ang), w=1.4, color=GRAY, amp=0)
    else:
        S.think_at(p, h["head"], _frag(a, t))
    return "Hände hinterm Kopf, Blick zur Decke"

def think_yoyo(p, a, t, c):
    sh = S.seated_at(c.hip, lean=0)["sh"]
    d = abs(math.sin(t * 3.2))
    hand = (sh[0] + 18, sh[1] + 16 - 5 * (1 - d))
    h = S.seated(p, c.hip, lean=0, look=14, hands=(hand, (c.cx + 26, c.hip[1] - 5)))
    yo = (hand[0] + 3, hand[1] + 14 + 44 * d)
    p.line(hand[0], hand[1], yo[0], yo[1], w=1.0, color=GRAY, amp=0)
    p.circle(yo[0], yo[1], 7, w=1.8, fill=PAPER)
    S.think_at(p, h["head"], _frag(a, t))
    return "spielt Jo-Jo, während der Gedanke reift"

# ====================================================================== Tippen
def stream_coffee(p, a, t, c):
    hl, hr, lean, look = S.typing_hands(t, a.rate, c.keys)
    u = t % 10
    hd = S.seated_at(c.hip, lean=lean, look=look)["head"]
    mouth = (hd[0] + 11, hd[1] + 9)
    rest = (c.cx + 34, c.desk_y)                               # Tasse steht links auf dem Tisch
    grab = (rest[0], rest[1] - 8)
    pos = _seq(u, [(0, hr), (6.0, hr), (6.8, grab), (7.4, grab), (8.3, mouth), (9.0, mouth), (9.7, grab), (10.0, hr)])
    holding = 7.2 < u < 9.7
    h = S.seated(p, c.hip, lean=lean, look=look, hands=(hl, pos if u > 6.0 else hr))
    if holding:
        _mug(p, pos[0] + 4, pos[1] + 5, steam_t=t)
    else:
        _mug(p, rest[0], rest[1], steam_t=t)
    return "tippt, trinkt und tippt weiter"

def stream_groove(p, a, t, c):
    hl, hr, lean, look = S.typing_hands(t, a.rate, c.keys)
    bob = 5 * math.sin(t * 5.5)
    h = S.seated(p, c.hip, lean=lean + bob, look=look + bob * 0.6, hands=(hl, hr))
    hx, hy = h["head"]
    p.arc(hx, hy, 15, math.pi, 2 * math.pi, w=2.4)
    for dx in (-15, 15):
        p.circle(hx + dx, hy + 2, 5, w=1.8, fill=INK)
    for i in range(3):
        k = (t * 0.4 + i / 3) % 1
        p.note(hx + 6 + 18 * math.sin(k * 5 + i), hy - 24 - k * 70, 0.8, color=GRAY, double=i == 1)
    return "tippt mit Kopfhörern im Takt"

# ====================================================================== Kontext packen
def compact_suitcase(p, a, t, c):
    cx0, cw, ch = 40, 70, 42
    press = abs(math.sin(t * 3.0))
    top = FLOOR - ch - 7 * (1 - press)
    p.rect(cx0, top, cw, FLOOR - top, lw=2.6, fill=PAPER)
    p.line(cx0 + 6, top + 14, cx0 + cw - 6, top + 14, w=1.2, color=GRAY)
    p.rect(cx0 + cw / 2 - 8, top - 5, 16, 6, lw=1.8)
    # eine Socke hängt raus
    p.curve([(cx0 + 18, top + 2), (cx0 + 14, top - 8 - 4 * (1 - press)), (cx0 + 22, top - 14 - 4 * (1 - press))], w=2.2)
    fx, crouch = 128, 10 + 8 * press
    sh = S.standing_at(fx, lean=24, crouch=crouch)["sh"]
    tgt = (cx0 + cw - 18, top - 3)
    h = S.standing(p, fx, lean=24, crouch=crouch, hands=(tgt, (tgt[0] + 14, tgt[1] + 1)))
    S.say_at(p, h["head"], "Passt… gleich… passt!", w=250, dx=70)
    return "setzt sich auf den Koffer, damit er zugeht"

# ====================================================================== Fehler
def error_run(p, a, t, c):
    ph = t * 1.5
    fx = 100 + 70 * math.sin(ph)
    flip = math.cos(ph) > 0
    sw = math.sin(t * 9)
    h = p.figure(fx, _stand_hip(), flip=flip, feet=_walk_feet(fx, t * 10, step=16, lift=10),
                 la=(150 + 25 * sw, 190), ra=(-150 - 25 * sw, -190), eyes="dots")
    S.say_at(p, h["head"], "ES BRENNT!", w=190, h=70, size=24, color=RED, bold=True, dx=0)
    return a.last_error or "Fehler"

def error_extinguisher(p, a, t, c):
    fx = 135
    an = Pen.anchors(fx, _stand_hip(), flip=True)
    sh = an["sh"]
    hand = (sh[0] + 30, sh[1] + 12)
    h = p.figure(fx, _stand_hip(), flip=True, feet=((fx - 9, FLOOR), (fx + 9, FLOOR)), hands=(hand, (hand[0] - 8, hand[1] + 14)), eyes="dots")
    hx, hy = h["hl"]
    p.rect(hx - 6, hy - 6, 12, 34, lw=2.2, fill=RED)
    nz = (hx + 8, hy - 8)
    p.line(hx, hy - 6, nz[0], nz[1], w=2, amp=0)
    tgt = (c.lap_x + 6, c.desk_y - 40)
    for i in range(9):
        k = (t * 1.6 + i / 9) % 1
        x = nz[0] + (tgt[0] - nz[0]) * k
        y = nz[1] + (tgt[1] - nz[1]) * k - 14 * math.sin(k * math.pi) + 5 * math.sin(i * 7 + t * 5)
        p.circle(x, y, 2.5 + 7 * k, w=1.3, color=GRAY, fill=PAPER)
    S.say_at(p, h["head"], "Pssssst!", w=170, h=64, size=22, dx=-10)
    return a.last_error or "Fehler"

# ====================================================================== Wiederholen (Tür)
DOOR_X = 320

def _door(p, label=True):
    dx = DOOR_X
    p.rect(dx, FLOOR - 190, 84, 190, lw=2.6, fill=PAPER)
    p.circle(dx + 14, FLOOR - 95, 4, w=2)
    p.text("API", dx + 42, FLOOR - 158, 22, align="center", bold=True)

def retry_bell(p, a, t, c):
    dx = DOOR_X
    _door(p)
    by = FLOOR - 124
    p.rect(dx - 22, by - 9, 14, 18, lw=2, fill=PAPER)                    # Klingelschild
    p.circle(dx - 15, by, 3.5, w=1.8, fill=INK)
    fx = dx - 62
    sh = S.standing_at(fx, flip=True)["sh"]
    press = abs(math.sin(t * 2.2)) > 0.8
    hand = (dx - 18 - (6 if not press else 0), by + 2)
    h = S.standing(p, fx, flip=True, hands=(hand, (fx + 4, sh[1] + 40)))
    if press:
        for i, d in enumerate((-1, 1)):
            p.arc(dx - 15, by, 18 + 7 * i, -0.9 + 3.14 * (d < 0), 0.9 + 3.14 * (d < 0), w=1.3, color=GRAY)
        p.text("dingdong", dx - 15, by - 24, 14, align="center", color=GRAY, hand=True, upper=False)
    r = a.retry or {}
    S.say_at(p, h["head"], f"Versuch {r.get('attempt', '?')} von {r.get('max', '?')}…", dx=-120, w=220)
    return r.get("error") or "Anbieter sagt nein"

def retry_peek(p, a, t, c):
    dx = DOOR_X
    _door(p)
    ky = FLOOR - 86
    p.circle(dx + 20, ky, 4, w=1.8)
    p.line(dx + 20, ky + 3, dx + 20, ky + 10, w=1.8, amp=0)
    fx = dx - 40
    sway = 2 * math.sin(t * 1.5)
    h = p.figure(fx, FLOOR - 2 * LEG + 8, flip=True, lean=38, look=12,
                 feet=((fx - 14, FLOOR), (fx + 6, FLOOR)),
                 hands=((fx + 4, FLOOR - 50), (fx + 16, FLOOR - 56 + sway)))
    S.say_at(p, h["head"], "Ich sehe… nichts. Nochmal?", w=250, dx=-90)
    r = a.retry or {}
    return r.get("error") or "Anbieter sagt nein"

# ====================================================================== Werkzeuge
def _terminal(p, t, label):
    x, y, w, h = 292, 96, 140, 120
    p.rect(x, y, w, h, lw=2.4, fill=PAPER)
    p.line(x, y + 16, x + w, y + 16, w=1.6)
    p.text("bash", x + 8, y + 12, 11, color=GRAY, upper=False)
    n = int(t * 7)
    lines = [label[:18]] + ["ok", "kompiliere…", "[####......]", "warnung: egal", "ok ok ok", "42 Tests"]
    for i in range(6):
        k = n - 5 + i
        txt = lines[k % len(lines)] if k > 0 else ""
        if txt:
            p.text("$ " + txt if k % 4 == 0 else txt, x + 8, y + 34 + i * 14, 10, color=INK if i == 5 else GRAY, upper=False, jitter=0.3, maxw=w - 14)
    if int(t * 3) % 2:
        p.rect(x + 8, y + 36 + 5 * 14 - 8, 6, 10, lw=1, fill=INK)

def bash_terminal(p, a, t, c):
    tool = a.tools[0]
    hl, hr, lean, look = S.typing_hands(t, 90, c.keys)
    S.seated(p, c.hip, lean=lean, look=look, hands=(hl, hr))
    _terminal(p, t, tool.get("label", ""))

def bash_crank(p, a, t, c):
    bx, bw_, bh = 22, 70, 74
    p.rect(bx, FLOOR - bh, bw_, bh, lw=2.4, fill=PAPER)
    p.text(">_", bx + bw_ / 2, FLOOR - 30, 22, align="center", bold=True, hand=False)
    cx0, cy0 = bx + bw_ + 4, FLOOR - 60
    w = t * 4
    hand_pos = (cx0 + 18 + 14 * math.cos(w), cy0 + 14 * math.sin(w))
    p.circle(cx0, cy0, 3, w=2, fill=INK)
    p.line(cx0, cy0, *hand_pos, w=3, amp=0)
    fx = cx0 + 40
    S.standing(p, fx, flip=False, lean=16, stance=11, hands=(hand_pos, (fx + 4, FLOOR - 2 * LEG - 20)))
    for i in range(3):
        k = (t * 0.8 + i / 3) % 1
        p.circle(bx + 14 + i * 22, FLOOR - bh - 8 - k * 40, 3 + 4 * k, w=1.2, color=GRAY)

def read_scroll(p, a, t, c):
    hd = S.seated_at(c.hip, lean=-4, look=10)["head"]
    top = (hd[0] + 36, hd[1] + 6)
    sway = 3 * math.sin(t * 1.4)
    S.seated(p, c.hip, lean=-4, look=10, hands=((top[0] - 6, top[1] + 4), (top[0] + 6, top[1] + 2)))
    p.line(top[0] - 9, top[1], top[0] + 9, top[1], w=3, amp=0)
    p.poly([(top[0] - 7, top[1]), (top[0] - 8 + sway * 0.3, top[1] + 90), (top[0] + 8 + sway * 0.3, top[1] + 96), (top[0] + 7, top[1])], w=1.8, fill=PAPER)
    for i in range(9):
        p.line(top[0] - 4 + sway * 0.1 * i / 4, top[1] + 10 + i * 9, top[0] + 5 + 3 * math.sin(i * 2.1), top[1] + 10 + i * 9, w=1, color=GRAY, amp=0.2)

QUOTES = ["…und dann sagte der Compiler: nein.", "Kapitel 7: Warum alles ein Provisorium ist.", "Hier steht: einfach neu starten.",
          "Fußnote 12 widerspricht Fußnote 11.", "Und der Butler war ein Merge-Konflikt."]

def read_aloud(p, a, t, c):
    S.draw_tool_pose(p, "read", a.tools[0], c.hip, c.cx, c.desk_y, FLOOR, t, c.keys)
    hd = S.seated_at(c.hip, lean=-8, look=12)["head"]
    S.say_at(p, hd, QUOTES[(kh(a.key) + int(t / 5)) % len(QUOTES)], w=300, h=84, size=17, dx=40)

def write_tablet(p, a, t, c):
    tx, ty, tw, th = 28, FLOOR - 128, 86, 128
    p.poly([(tx, FLOOR), (tx, ty + 14), (tx + 14, ty), (tx + tw - 14, ty), (tx + tw, ty + 14), (tx + tw, FLOOR)], w=2.6, fill=PAPER)
    n = int(t / S.HAMMER_PERIOD)
    for i in range(min(8, n % 12)):
        p.line(tx + 16, ty + 28 + i * 11, tx + tw - 18 - (i % 3) * 8, ty + 28 + i * 11, w=1.8, color=GRAY, amp=0.4)
    fx = tx + tw + 52
    target = (tx + tw - 4, FLOOR - 62)
    sp = S.hammer_swing(t)
    sh = S.standing_at(fx, flip=False, lean=sp["lean"], crouch=sp["crouch"])["sh"]
    hand, ang = S.hammer_grip(sh, target, sp)
    aim = sp["aim"]
    free = (sh[0] - 36 * aim - 4 * (1 - aim), sh[1] + 36 - 10 * aim)
    S.standing(p, fx, flip=False, lean=sp["lean"], crouch=sp["crouch"], stance=11, hands=(free, hand))
    p.hammer(hand[0], hand[1], ang)
    p.line(target[0] - 2, target[1] - 4, target[0] - 14, target[1] + 6, w=3, amp=0)           # Meißel
    if sp["impact"] > 0:
        for i in range(4):
            p.line(target[0] - 8, target[1], target[0] - 8 - 10 * sp["impact"] * (1 + i * 0.4), target[1] - 8 - 7 * i * sp["impact"], w=1.2, color=GRAY, amp=0)

def write_board(p, a, t, c):
    bx, by, bw_, bh = 26, FLOOR - 190, 150, 105
    p.rect(bx, by, bw_, bh, lw=2.6, fill=PAPER)
    p.line(bx + 20, by + bh, bx + 14, FLOOR, w=2.4)
    p.line(bx + bw_ - 20, by + bh, bx + bw_ - 14, FLOOR, w=2.4)
    n = int(t * 2.2)
    for i in range(6):
        if n // 3 % 8 > i:
            p.line(bx + 12, by + 18 + i * 15, bx + 12 + 60 + 50 * math.sin(i * 1.7) ** 2, by + 18 + i * 15, w=1.6, color=GRAY, amp=0.4)
    cur = n // 3 % 8
    fx = bx + bw_ + 40
    row = min(5, cur)
    wx = bx + 12 + 40 + 36 * ((n % 3) / 3)
    wy = by + 18 + row * 15
    sh = S.standing_at(fx, flip=False, lean=6)["sh"]
    S.standing(p, fx, flip=False, lean=6, hands=((wx, wy), (fx - 4, sh[1] + 36)))
    p.pencil(wx, wy - 6, 200, L=22)

def sub_flag(p, a, t, c):
    shx, shy = S.seated_at(c.hip, lean=2)["sh"]
    hand = (shx + 26, shy - 6 + 4 * math.sin(t * 4))
    h = S.seated(p, c.hip, lean=2, hands=(hand, (shx + 20, shy + 12)))
    top = (hand[0], hand[1] - 62)
    p.line(hand[0], hand[1] + 6, top[0], top[1], w=2.4, amp=0)
    pts = [(top[0], top[1])]
    for i in range(1, 6):
        pts.append((top[0] + i * 8, top[1] + 3 * math.sin(t * 7 - i) * i / 2))
    low = [(x, y + 20) for x, y in reversed(pts)]
    p.poly(pts + low, closed=True, w=1.8, fill=PAPER)
    p.text("go!", top[0] + 22, top[1] + 14, 12, align="center", bold=True)
    S.say_at(p, h["head"], "Marsch, Marsch!", w=190, h=64, dx=50)

def sub_bell(p, a, t, c):
    shx, shy = S.seated_at(c.hip, lean=2)["sh"]
    sw = math.sin(t * 9)
    hand = (shx + 28 + 6 * sw, shy - 14)
    h = S.seated(p, c.hip, lean=2, look=6, hands=(hand, (shx + 20, shy + 12)))
    bx, by = hand
    p.poly([(bx - 9, by - 2), (bx - 6, by - 16), (bx + 6, by - 16), (bx + 9, by - 2)], closed=True, w=2, fill=PAPER)
    p.circle(bx, by + 1, 2.4, w=1.6, fill=INK)
    for i, d in enumerate((-1, 1)):
        p.line(bx + d * 14, by - 14 - i * 3, bx + d * 22, by - 18 - i * 6, w=1.4, color=GRAY, amp=0)
    S.say_at(p, h["head"], "Kling! Alle mal herhören!", w=270, h=70, dx=60)

def other_binoculars(p, a, t, c):
    look = 6 + 6 * math.sin(t * 0.8)
    lean = -2
    hd = S.seated_at(c.hip, lean=lean, look=look)["head"]
    eye = (hd[0] + 10, hd[1] - 2)
    h = S.seated(p, c.hip, lean=lean, look=look, hands=((eye[0] + 2, eye[1] + 6), (eye[0] - 6, eye[1] + 8)))
    p.circle(eye[0] + 10, eye[1] - 2, 6, w=2.2, fill=INK)
    p.circle(eye[0] + 10, eye[1] + 8, 6, w=2.2, fill=INK)
    p.line(eye[0] + 6, eye[1] + 3, eye[0] + 8, eye[1] + 3, w=3, amp=0)

# ====================================================================== Siegestanz
FINALE_TEXT = ["GESCHAFFT!", "Läuft!", "Fertig!", "Und tschüss, Bugs!"]
FINALE_CAPS = {"hopak": "Kosakentanz auf dem Tisch", "robot": "Roboter-Tanz auf dem Tisch", "cheer": "Siegerhüpfer auf dem Tisch"}

def finale_style(a) -> str:
    return dance.FINALE_ORDER[(kh(a.key) + a.turn) % len(dance.FINALE_ORDER)]

def finale(p, a, t, c):
    age = a.idle_for or 0.0
    st = finale_style(a)
    f = dance.draw(p, st, age, c.cx + 150, c.desk_y, 0.85)
    for i in range(3):
        k = (age * 0.5 + i / 3) % 1
        p.note(c.cx + 112 + 76 * i, c.desk_y - 60 - k * 80 - 90, 0.8, color=GRAY, double=i == 1)
    S.say_at(p, f["head"], FINALE_TEXT[int(age / 4) % len(FINALE_TEXT)], w=240, h=70, size=24, bold=True, dx=-90)
    return "Runde fertig – " + FINALE_CAPS[st]

# ====================================================================== Leerlauf
def idle_news(p, a, t, c):
    hd = S.seated_at(c.hip, lean=-6)["head"]
    px, top = hd[0] + 30, hd[1] - 18
    rustle = 3 * math.sin(t * 9) if (t % 6) < 0.8 else 0.0
    S.seated(p, c.hip, lean=-6, hands=((px - 12, top + 52), (px - 10, top + 40)))
    p.poly([(px - 12, top), (px + 16 + rustle, top - 2), (px + 16 + rustle, top + 60), (px - 12, top + 62)], closed=True, w=2, fill=PAPER)
    p.text("EXTRA", px + 2, top + 14, 10, align="center", bold=True)
    for i in range(6):
        p.line(px - 8, top + 22 + i * 6, px + 12 + rustle, top + 22 + i * 6, w=1, color=GRAY, amp=0.2)
    return "liest die Zeitung von gestern"

def idle_coffee(p, a, t, c):
    lean = -12
    hd = S.seated_at(c.hip, lean=lean)["head"]
    mouth = (hd[0] + 11, hd[1] + 9)
    lap = (c.cx + 26, c.hip[1] - 6)
    u = t % 7
    pos = _seq(u, [(0, lap), (1.0, lap), (2.0, mouth), (4.2, mouth), (5.2, lap), (7, lap)])
    S.seated(p, c.hip, lean=lean, hands=(pos, (c.cx + 30, c.hip[1] - 4)))
    _mug(p, pos[0] + 4, pos[1] + 5, steam_t=t)
    if 2.6 < u < 4.0:
        p.text("schlürf", mouth[0] + 30, mouth[1] - 20, 15, color=GRAY, hand=True, upper=False)
    return "Kaffeepause"

def idle_juggle(p, a, t, c):
    fx = 130
    sh = S.standing_at(fx)["sh"]
    xl, xr, yh = sh[0] - 22, sh[0] + 22, sh[1] + 26
    w = t * 1.3 * math.pi
    hl = (xl, yh - 7 * max(0, math.sin(w)))
    hr = (xr, yh - 7 * max(0, -math.sin(w)))
    h = S.standing(p, fx, hands=(hl, hr), splay=True, eyes="dots")
    for i in range(3):
        s = t * 1.3 + i * 2 / 3
        n, k = int(s), s - int(s)
        x0, x1 = (xl, xr) if n % 2 == 0 else (xr, xl)
        p.circle(x0 + (x1 - x0) * k, yh - 10 - 78 * 4 * k * (1 - k), 5.5, w=1.8, fill=INK)
    return "jongliert, bis jemand klingelt"

def idle_plant(p, a, t, c):
    px = 90
    grow = (t % 18) / 18
    p.poly([(px - 14, FLOOR - 24), (px - 10, FLOOR), (px + 10, FLOOR), (px + 14, FLOOR - 24)], closed=True, w=2.4, fill=PAPER)
    ht = 24 + 56 * grow
    sw = 3 * math.sin(t * 1.2)
    p.curve([(px, FLOOR - 24), (px + sw * 0.4, FLOOR - 24 - ht / 2), (px + sw, FLOOR - 24 - ht)], w=2.4)
    for i in range(3 + int(grow * 3)):
        yy = FLOOR - 24 - ht * (0.3 + 0.7 * i / 6)
        d = 1 if i % 2 else -1
        p.poly([(px + sw * i / 8, yy), (px + d * 18 + sw * i / 8, yy - 6), (px + d * 6 + sw * i / 8, yy + 4)], closed=True, w=1.6, fill=PAPER)
    if grow > 0.75:
        fx_, fy_ = px + sw, FLOOR - 24 - ht - 6
        for i in range(5):
            ang = i * 1.2566
            p.circle(fx_ + 7 * math.cos(ang), fy_ + 7 * math.sin(ang), 4, w=1.4, fill=PAPER)
        p.circle(fx_, fy_, 3.5, w=1.4, fill=INK)
    fx = 156
    sh = S.standing_at(fx, flip=False, lean=4)["sh"]
    tilt = _ease(((t % 8) - 1) / 1.2) * (1 - _ease(((t % 8) - 5.5) / 1.0))
    hand = (sh[0] - 26, sh[1] + 20)
    S.standing(p, fx, flip=False, lean=4, hands=(hand, (fx + 6, sh[1] + 40)))
    ca = tilt * 0.6
    cxn, cyn = hand
    p.poly([(cxn - 9, cyn - 8), (cxn + 9, cyn - 8), (cxn + 9, cyn + 8), (cxn - 9, cyn + 8)], closed=True, w=2, fill=PAPER)
    sp = (cxn - 9 - 22, cyn - 6 + 14 * ca)
    p.line(cxn - 9, cyn + 2, sp[0], sp[1], w=2.2, amp=0)
    if tilt > 0.2:
        for i in range(5):
            k = (t * 2.2 + i / 5) % 1
            p.circle(sp[0] - 2 - 3 * k, sp[1] + 3 + (FLOOR - 30 - sp[1]) * k * k, 1.8, w=1.2, color=BLUE)
    return "gießt die Pflanze (sie wächst sichtbar)"

def idle_plane(p, a, t, c):
    u = t % 7.5
    lean = -4
    hd = S.seated_at(c.hip, lean=lean, look=6)["head"]
    hold = (hd[0] + 16, hd[1] + 2 + 2 * math.sin(t * 3))
    cock = (hd[0] - 8, hd[1] - 8)
    thr = (hd[0] + 36, hd[1] + 12)
    lap = (c.cx + 26, c.hip[1] - 5)
    hand = _seq(u, [(0, hold), (2.0, hold), (2.5, cock), (2.75, thr), (3.5, lap), (7.5, lap)])
    S.seated(p, c.hip, lean=lean, look=6, hands=(hand, (c.cx + 30, c.hip[1] - 4)))
    if u < 2.75:
        _plane(p, hand[0] + 6, hand[1] - 4, -0.3 if u > 2 else 0.0)
    else:
        k = (u - 2.75) / 3.6
        if k < 1:
            x = thr[0] + 6 + 190 * k
            y = thr[1] - 56 * math.sin(k * math.pi * 0.8) + 38 * k * k
            ang = math.atan2(-56 * 0.8 * math.pi * math.cos(k * math.pi * 0.8) + 76 * k, 190)
            _plane(p, x, y, ang)
    return "faltet Papierflieger und fliegt sie"

VISITS = [("Läuft's?", "Läuft. Frag nicht wie."), ("Kaffee?", "Immer."), ("Schon Feierabend?", "Der Kontext sagt nein."),
          ("Ich hab dir einen Bug mitgebracht.", "Stell ihn zu den anderen."), ("Was machst du da?", "Token verbrennen. Und du?")]

def idle_visitor(p, a, t, c):
    u = t % IDLE_SLOT_S
    n = int(t / IDLE_SLOT_S)
    vx = 24 + 86 * _ease(u / 3.0) if u < 11 else 110 - 100 * _ease((u - 11) / 3.0)
    walking = u < 3 or u > 11
    flip = not (u > 11)
    s = 0.9
    hip_y = FLOOR - 2 * LEG * s + 0.5
    wave = 25 * math.sin(t * 8) if 3 <= u < 4.2 else 0.0
    feet = _walk_feet(vx, t * 6, stance=8 * s, step=11 * s, lift=6) if walking else ((vx - 8, FLOOR), (vx + 8, FLOOR))
    vsh = Pen.anchors(vx, hip_y, s=s, flip=flip)["sh"]
    if 3 <= u < 4.2:
        vh = (vsh[0] + 18, vsh[1] - 34 + 6 * math.sin(t * 8))
        vhands = (vh, (vsh[0] + 4, vsh[1] + 32))
    else:
        vhands = ((vsh[0] + 8, vsh[1] + 32), (vsh[0] + 2, vsh[1] + 34))
    vf = p.figure(vx, hip_y, s=s, flip=flip, feet=feet, hands=vhands, color=BLUE)
    talking = 4.2 <= u < 11
    turn = 18 if 3 <= u < 11 else 0
    S.seated(p, c.hip, lean=-8, look=-turn, hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    hd = S.seated_at(c.hip, lean=-8, look=-turn)["head"]
    line_a, line_b = VISITS[(kh(a.key) + n) % len(VISITS)]
    if 3 <= u < 4.2:
        S.say_at(p, vf["head"], "Hallo!", w=150, h=60, dx=40)
    elif talking:
        if u < 7.5:
            S.say_at(p, vf["head"], line_a, w=270, h=84, size=17, dx=70, color=BLUE)
        else:
            S.say_at(p, hd, line_b, w=280, h=84, size=17, dx=40)
    return "Besuch von einem Kollegen"

def idle_bird(p, a, t, c):
    bx = 350 + 40 * math.sin(t * 0.6)
    face = 1 if math.cos(t * 0.6) > 0 else -1
    peck = max(0.0, math.sin(t * 6)) if (t % 4) < 2.5 else 0.0
    S.seated(p, c.hip, lean=14, look=12, hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    y = c.desk_y
    hop = 3 * abs(math.sin(t * 2.5)) if peck == 0 else 0
    p.circle(bx, y - 12 - hop, 8, w=2, fill=PAPER)
    hx_, hy_ = bx + face * 9, y - 17 - hop + 9 * peck
    p.circle(hx_, hy_, 4.5, w=2, fill=PAPER)
    p.poly([(hx_ + face * 4, hy_ - 1), (hx_ + face * 10, hy_ + 1), (hx_ + face * 4, hy_ + 2)], closed=True, w=1.6, fill=(1.0, 0.85, 0.5))
    p.line(bx - face * 7, y - 12 - hop, bx - face * 17, y - 18 - hop, w=2, amp=0)
    for dx in (-2, 3):
        p.line(bx + dx, y - 5 - hop, bx + dx, y, w=1.4, amp=0)
    for i in range(4):
        p.circle(bx + face * 16 + 7 * i - 20, y - 1.5, 1.3, w=1, fill=INK)
    if peck > 0.8:
        p.text("pick", bx + face * 20, y - 30, 12, color=GRAY, hand=True, upper=False)
    return "füttert einen Vogel auf dem Tisch"

def idle_yoga(p, a, t, c):
    fx = 130
    sway = 2.5 * math.sin(t * 0.9)
    an = Pen.anchors(fx + sway, _stand_hip())
    hd = an["head"]
    foot_up = (fx + sway + 13, FLOOR - 1.05 * LEG)
    h = p.figure(fx + sway, _stand_hip(), splay=True, feet=((fx + sway - 3, FLOOR), foot_up),
                 hands=((fx + sway - 3, hd[1] - 42), (fx + sway + 3, hd[1] - 44)), eyes="dots")
    for i in range(3):
        k = (t * 0.35 + i / 3) % 1
        p.arc(fx + 50, h["head"][1] - 10, 10 + k * 26, -0.6, 0.6, w=1.3, color=GRAY)
    p.text("ommm", fx + 100, h["head"][1] - 30, 16, align="center", color=GRAY, hand=True, upper=False)
    return "Yoga zwischen zwei Prompts"

# ====================================================================== Tabellen
ACTS = {
    "thinking": [None, think_pace, think_back, think_yoyo],
    "streaming": [None, stream_coffee, stream_groove],
    "compacting": [None, compact_suitcase],
    "error": [None, error_run, error_extinguisher],
    "retrying": [None, retry_bell, retry_peek],
    "bash": [None, bash_terminal, bash_crank],
    "read": [None, read_scroll, read_aloud],
    "write": [None, write_tablet, write_board],
    "subagent": [None, sub_flag, sub_bell],
    "other": [None, other_binoculars],
    "idle": [None, idle_news, idle_coffee, idle_juggle, idle_plant, idle_plane, idle_visitor, idle_bird, idle_yoga],
}

def draw(p: Pen, a, ph: str, kind: str | None, t: float, c) -> str | None:
    """Zeichnet die gewählte Variante. None = klassische Pose in scene.py; sonst die Bildunterschrift ('' = Standard)."""
    if ph == "idle":
        if a.idle_for is not None and a.idle_for < FINALE_S:
            return finale(p, a, t, c)
        name, period = "idle", IDLE_SLOT_S
    else:
        name, period = (kind if ph == "tool" else ph), VARIANT_S
    table = ACTS.get(name)
    if not table:
        return None
    v = variant(a.key, name, t, len(table), period)
    if v == 0:
        return None
    return table[v](p, a, t, c) or ""

def context(cx, floor, desk_y, seat_y, hip, lap_x, keys):
    return SimpleNamespace(cx=cx, floor=floor, desk_y=desk_y, seat_y=seat_y, hip=hip, lap_x=lap_x, keys=keys)

# ====================================================================== Umgebung
def _cat(p, x, d, t):
    y = FLOOR
    w = t * 9
    p.curve([(x - 16 * d, y - 13), (x - 2 * d, y - 17), (x + 11 * d, y - 13)], w=2.4)
    for i, off in enumerate((-13, -7, 6, 11)):
        sw = 4 * math.sin(w + i * 1.6)
        p.line(x + off * d, y - 13, x + off * d + sw, y, w=1.8, amp=0)
    p.circle(x + 17 * d, y - 21, 6.5, w=2, fill=PAPER)
    for e in (-1, 1):
        p.poly([(x + 17 * d + e * 5, y - 25), (x + 17 * d + e * 5, y - 32), (x + 17 * d + e * 1, y - 27)], w=1.5, amp=0)
    p.curve([(x - 16 * d, y - 13), (x - 26 * d, y - 22 + 3 * math.sin(t * 3)), (x - 24 * d, y - 34 + 4 * math.sin(t * 3 + 1))], w=2.2)

def _bird(p, x, y, t, d):
    f = math.sin(t * 12)
    p.line(x - 8 * d, y, x + 8 * d, y, w=1.6, amp=0)
    p.line(x, y, x - 6 * d, y - 10 * f, w=1.8, amp=0)
    p.line(x, y, x + 6 * d, y - 10 * f, w=1.8, amp=0)
    p.circle(x + 9 * d, y - 1, 3, w=1.6, fill=PAPER)

def _balloon(p, x, y, t):
    p.circle(x, y, 12, w=2, color=RED, fill=(1.0, 0.85, 0.85))
    p.curve([(x, y + 12), (x + 4 * math.sin(t * 2), y + 30), (x - 2, y + 48)], w=1.2, color=GRAY)

def _snail(p, x, t):
    y = FLOOR
    p.circle(x, y - 8, 7, w=2, fill=PAPER)
    p.arc(x, y - 8, 3, 0.5, 5.0, w=1.2)
    p.curve([(x - 9, y), (x + 14, y)], w=2.2)
    p.line(x + 14, y, x + 15, y - 7, w=1.6, amp=0)
    p.line(x + 14, y, x + 18, y - 7, w=1.6, amp=0)

AMBIENT_SLOT_S = 30.0

def ambient(p: Pen, key: str, t: float):
    """Gelegentlich geht etwas durchs Bild (Katze, Vogel, Ballon, Schnecke) – in jedem Panel zu anderer Zeit."""
    slot = int(t / AMBIENT_SLOT_S)
    h = S._hash01(kh(key), slot, 99)
    kind = int(h * 5)
    u = t - slot * AMBIENT_SLOT_S - 3 - 4 * _perm_pos(key, slot)
    if kind > 3 or u < 0:
        return
    if kind == 0 and u < 16:
        d = 1 if slot % 2 else -1
        x = (30 + 410 * u / 16) if d > 0 else (440 - 410 * u / 16)
        _cat(p, x, d, t)
    elif kind == 1 and u < 11:
        d = 1 if slot % 2 else -1
        k = u / 11
        x = (-10 + 460 * k) if d > 0 else (450 - 460 * k)
        _bird(p, x, 84 + 10 * math.sin(k * 9), t, d)
    elif kind == 2 and u < 20:
        k = u / 20
        _balloon(p, 40 + 360 * ((kh(key) + slot) % 7) / 7, FLOOR - 20 - (FLOOR - 90) * k, t)
    elif kind == 3 and u < 24:
        _snail(p, 40 + 90 * u / 24 + 200 * (slot % 2), t)

def _perm_pos(key, slot):
    return S._hash01(kh(key), slot, 5)

# ====================================================================== Leer-Szenen
EMPTY_SCENES = 4
EMPTY_SLOT_S = 22.0

def empty_scene(p: Pen, t: float) -> bool:
    """Alternative zur Hängematte, wenn gar kein Agent läuft. False = Hängematte zeichnen."""
    v = variant("leer", "szene", t, EMPTY_SCENES, EMPTY_SLOT_S)
    if v == 0:
        return False
    if v == 1:                                              # Angeln
        p.line(180, 372, 560, 372, w=2.6)
        for x in (210, 330, 450):
            p.line(x, 372, x, 410, w=2.2)
        for i in range(5):
            y = 392 + i * 14
            p.curve([(560 + j * 40, y + 4 * math.sin(t * 1.4 + j + i)) for j in range(9)], w=1.4, color=GRAY)
        hip = (350, 369)
        p.figure(*hip, flip=True, lean=6, look=10, feet=((hip[0] + 32, 416), (hip[0] + 46, 414)), hands=((hip[0] + 40, 322), (hip[0] + 52, 330)))
        tip = (560, 190)
        p.line(hip[0] + 46, 326, *tip, w=2.2, amp=0.3)
        bob = (600, 400 + 3 * math.sin(t * 2.4))
        p.line(*tip, *bob, w=1.0, color=GRAY, amp=0)
        p.circle(*bob, 5, w=1.8, color=RED, fill=(1.0, 0.8, 0.8))
        k = (t % 11) / 11
        if k < 0.25:
            u = k / 0.25
            p.poly([(700 + 70 * u - 14, 400 - 90 * math.sin(u * math.pi)), (700 + 70 * u + 14, 400 - 90 * math.sin(u * math.pi) - 6),
                    (700 + 70 * u + 22, 400 - 90 * math.sin(u * math.pi) + 4)], closed=True, w=1.8, fill=PAPER)
        p.text("Heute beißt keiner.", 640, 330, 16, color=GRAY, hand=True, upper=False)
    elif v == 2:                                            # Lagerfeuer
        p.line(80, 444, 920, 444, w=2)
        p.flame(540, 440, t, h=70)
        p.line(500, 442, 580, 428, w=4, amp=0.3)
        p.line(500, 428, 580, 442, w=4, amp=0.3)
        hip = (400, 440)
        stick_tip = (516, 395 + 4 * math.sin(t * 1.5))
        p.figure(*hip, flip=True, lean=4, look=8, feet=((hip[0] + 34, 444), (hip[0] + 48, 442)), hands=((hip[0] + 46, 400), (hip[0] + 38, 408)))
        p.line(hip[0] + 40, 405, *stick_tip, w=2, amp=0.2)
        p.circle(stick_tip[0] + 4, stick_tip[1] - 3, 5, w=1.6, fill=(1.0, 0.95, 0.85))
        for i in range(4):
            k = (t * 0.3 + i / 4) % 1
            p.circle(530 + 30 * math.sin(k * 5 + i), 360 - k * 150, 1.6, w=1.2, color=RED)
        for i in range(12):
            tw = 0.5 + 0.5 * math.sin(t * 1.3 + i * 2.1)
            p.circle(120 + (i * 137) % 800, 70 + (i * 61) % 150, 1.4 + tw, w=1, color=GRAY)
        for i in range(2):
            k = (t * 0.4 + i / 2) % 1
            p.note(300 + 30 * i, 330 - k * 60, 0.9, color=GRAY, double=bool(i))
    else:                                                   # Sterne gucken
        p.line(80, 444, 920, 444, w=2)
        for i in range(24):
            tw = 0.5 + 0.5 * math.sin(t * 1.7 + i * 2.3)
            p.circle(90 + (i * 197) % 820, 50 + (i * 83) % 250, 1.2 + tw * 1.3, w=1, color=INK if tw > 0.6 else GRAY)
        k = (t % 9) / 9
        if k < 0.18:
            u = k / 0.18
            p.line(760 - 140 * u, 80 + 70 * u, 760 - 140 * u + 46, 80 + 70 * u - 22, w=1.8, color=GRAY, amp=0)
        fx = 380
        tele_base = (fx + 62, 380)
        ang = math.radians(48)
        end = (tele_base[0] + 150 * math.sin(ang), tele_base[1] - 150 * math.cos(ang) * 1.0)
        p.line(*tele_base, *end, w=7, amp=0.2)
        p.line(tele_base[0] - 6, tele_base[1] + 6, tele_base[0] - 24, 444, w=2.4, amp=0)
        p.line(tele_base[0] + 6, tele_base[1] + 6, tele_base[0] + 22, 444, w=2.4, amp=0)
        sh = Pen.anchors(fx, 444 - 2 * LEG + 0.5, flip=True)["sh"]
        p.figure(fx, 444 - 2 * LEG + 0.5, flip=True, lean=-6, look=-8, feet=((fx - 9, 444), (fx + 9, 444)), hands=((tele_base[0] - 8, tele_base[1] + 2), (tele_base[0] - 2, tele_base[1] - 10)))
    return True
