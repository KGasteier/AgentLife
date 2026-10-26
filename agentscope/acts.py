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


# ====================================================================== Besuch (0.6.0)
def _arrive(u):
    """Besucher läuft 0–3 s ein, steht bis 11 s, geht 11–14 s. → (x, geht?, blickt nach rechts?)"""
    if u < 3:
        return 24 + 86 * _ease(u / 3.0), True, True
    if u < 11:
        return 110, False, True
    return 110 - 100 * _ease((u - 11) / 3.0), True, False

def _visitor(p, vx, t, walking, flip, hands_fn=None, color=BLUE):
    s = 0.9
    hip_y = FLOOR - 2 * LEG * s + 0.5
    feet = _walk_feet(vx, t * 6, stance=8 * s, step=11 * s, lift=6) if walking else ((vx - 8, FLOOR), (vx + 8, FLOOR))
    sh = Pen.anchors(vx, hip_y, s=s, flip=flip)["sh"]
    hands = hands_fn(sh) if hands_fn else ((sh[0] + 8, sh[1] + 32), (sh[0] + 2, sh[1] + 34))
    return p.figure(vx, hip_y, s=s, flip=flip, feet=feet, hands=hands, color=color), sh

def _sitter(p, a, c, turn):
    S.seated(p, c.hip, lean=-8, look=-turn, hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    return S.seated_at(c.hip, lean=-8, look=-turn)["head"]

GUESTS = [("Claude", "von nebenan"), ("Claude", "aus dem Nachbarpanel"), ("Claude", "vom Stockwerk drüber")]
GUEST_TALK = [
    ("Hallo, ich bin {n} {w}.", "Hallo! Ich bin hier der mit dem vollen Kontext."),
    ("Hast du mal 'n Token übrig?", "Nur wenn du mir einen Bug abnimmst."),
    ("Bei uns drüben läuft gerade alles.", "Bei mir auch. Nur nicht gut."),
    ("Darf ich kurz bei dir kompaktieren?", "Mach's dir bequem. Bring Kaffee mit."),
]

def idle_guest(p, a, t, c):
    """Ein zweiter Agent (blau, mit Namensschild) stellt sich vor und plaudert."""
    u = t % IDLE_SLOT_S
    n = int(t / IDLE_SLOT_S)
    name, where = GUESTS[(kh(a.key) + n) % len(GUESTS)]
    la, lb = GUEST_TALK[(kh(a.key) + n) % len(GUEST_TALK)]
    vx, walking, flip = _arrive(u)
    shake = 4.5 <= u < 7.5
    def hf(sh):
        if 3 <= u < 4.2:
            return ((sh[0] + 18, sh[1] - 34 + 6 * math.sin(t * 8)), (sh[0] + 4, sh[1] + 32))
        if shake:
            return ((sh[0] + 30, sh[1] + 16 + 5 * math.sin(t * 9)), (sh[0] + 4, sh[1] + 32))
        return ((sh[0] + 8, sh[1] + 32), (sh[0] + 2, sh[1] + 34))
    vf, sh = _visitor(p, vx, t, walking, flip, hf)
    p.rect(vx - 14, sh[1] + 10, 28, 12, lw=1.2, color=BLUE, fill=PAPER)
    p.text(name, vx, sh[1] + 12, 9, align="center", color=BLUE, hand=True, upper=False, bold=True)
    hd = _sitter(p, a, c, 18 if 3 <= u < 11 else 0)
    if 3 <= u < 4.2:
        S.say_at(p, vf["head"], "Hallo!", w=150, h=60, dx=40, color=BLUE)
    elif 4.2 <= u < 7.5:
        S.say_at(p, vf["head"], la.format(n=name, w=where), w=290, h=90, size=17, dx=70, color=BLUE)
    elif 7.5 <= u < 11:
        S.say_at(p, hd, lb, w=290, h=90, size=17, dx=40)
    return f"{name} {where} schaut kurz vorbei"

def _envelope(p, x, y, w=22, h=15, color=INK):
    p.rect(x - w / 2, y - h / 2, w, h, lw=1.6, color=color, fill=PAPER)
    p.line(x - w / 2, y - h / 2, x, y + 1, w=1.2, color=color, amp=0)
    p.line(x + w / 2, y - h / 2, x, y + 1, w=1.2, color=color, amp=0)

def _postman_fig(p, vx, t, walking, flip, hands_fn=None):
    vf, sh = _visitor(p, vx, t, walking, flip, hands_fn, color=RED)
    hx, hy = vf["head"]
    p.poly([(hx - 11, hy - 6), (hx + 11, hy - 6), (hx + 8, hy - 15), (hx - 8, hy - 15)], closed=True, w=1.8, color=RED, fill=(1.0, 0.85, 0.85))
    p.line(hx + 4 * (1 if flip else -1), hy - 6, hx + 16 * (1 if flip else -1), hy - 4, w=1.8, color=RED, amp=0)
    d = -1 if flip else 1
    p.rect(vx + d * 12 - 8, sh[1] + 16, 16, 20, lw=1.8, color=RED, fill=(1.0, 0.9, 0.9))
    p.line(sh[0], sh[1] + 2, vx + d * 14, sh[1] + 16, w=1.4, color=RED, amp=0)
    return vf, sh

def idle_postman(p, a, t, c):
    """Der Postbote bringt einen Brief mit Tokens; beim Öffnen springen Münzen heraus."""
    u = t % IDLE_SLOT_S
    n = int(t / IDLE_SLOT_S)
    amount = (3 + (kh(a.key) + n) % 7) * 4
    vx, walking, flip = _arrive(u)
    holding = u < 5.2
    def hf(sh):
        if 3 <= u < 5.2:
            return ((sh[0] + 30, sh[1] + 18), (sh[0] + 4, sh[1] + 32))
        if u < 3:
            return ((sh[0] + 10, sh[1] + 24), (sh[0] + 2, sh[1] + 34))
        return ((sh[0] + 8, sh[1] + 32), (sh[0] + 2, sh[1] + 34))
    vf, sh = _postman_fig(p, vx, t, walking, flip, hf)
    if u < 5.2 and u >= 3:
        _envelope(p, vx + 36, sh[1] + 16, color=RED)
    got = 5.2 <= u
    hd_pos = S.seated_at(c.hip, lean=-6, look=-14)["head"]
    lap = (c.cx + 26, c.hip[1] - 5)
    if 5.2 <= u < 8.5:
        hand = (c.cx + 40, c.hip[1] - 16 - 6 * math.sin((u - 5.2) * 5))
    else:
        hand = lap
    _sitter_hand = (hand, (c.cx + 30, c.hip[1] - 4))
    S.seated(p, c.hip, lean=-6, look=-14 if 3 <= u < 11 else 0, hands=_sitter_hand)
    if 3 <= u < 5.2:
        S.say_at(p, vf["head"], "Post für dich!", w=230, h=70, dx=60, color=RED)
    if 5.2 <= u < 8.5:
        _envelope(p, hand[0] + 4, hand[1] - 8)
    if 6.4 <= u < 11:
        k = u - 6.4
        for i in range(5):
            kk = k - i * 0.25
            if kk > 0:
                p.coin(hand[0] + 4 + 14 * (i - 2) * min(1, kk), hand[1] - 20 - 62 * min(kk, 1.6) + 18 * kk * kk, r=6, color=INK)
        p.text(f"+{amount}k tok", hand[0] + 30, hand[1] - 100, 20, align="center", color=BLUE, hand=True, upper=False, bold=True)
    if 8.5 <= u < 11:
        S.say_at(p, hd_pos, "Danke! Quittung?", w=230, h=70, dx=40)
    elif 5.2 <= u < 6.4:
        S.say_at(p, hd_pos, "Oh, Tokens!", w=200, h=64, dx=40)
    return f"Postbote liefert {amount}k Tokens"

def _postman_walk(p, x, d, t):
    s = 0.7
    hip_y = FLOOR - 2 * LEG * s + 0.5
    feet = _walk_feet(x, t * 7, stance=7 * s, step=10 * s, lift=5)
    sh = Pen.anchors(x, hip_y, s=s, flip=d > 0)["sh"]
    f = p.figure(x, hip_y, s=s, flip=d > 0, feet=feet, hands=((sh[0] + d * 14, sh[1] + 20), (sh[0] - d * 6, sh[1] + 26)), color=RED)
    hx, hy = f["head"]
    p.poly([(hx - 8, hy - 4), (hx + 8, hy - 4), (hx + 6, hy - 11), (hx - 6, hy - 11)], closed=True, w=1.5, color=RED, fill=(1.0, 0.85, 0.85))
    p.rect(x - d * 9 - 6, sh[1] + 10, 12, 15, lw=1.5, color=RED, fill=(1.0, 0.9, 0.9))
    _envelope(p, sh[0] + d * 17, sh[1] + 18, 14, 10, color=RED)

def _drone(p, x, y, t):
    p.rect(x - 11, y - 4, 22, 8, lw=1.8, fill=PAPER)
    for e in (-1, 1):
        p.line(x + e * 11, y - 4, x + e * 11, y - 9, w=1.4, amp=0)
        w = 12 * math.cos(t * 30)
        p.line(x + e * 11 - w, y - 9, x + e * 11 + w, y - 9, w=1.6, amp=0)
    p.line(x - 5, y + 4, x - 5, y + 14, w=1.0, color=GRAY, amp=0)
    p.line(x + 5, y + 4, x + 5, y + 14, w=1.0, color=GRAY, amp=0)
    p.rect(x - 9, y + 14, 18, 13, lw=1.8, fill=(0.93, 0.85, 0.7))
    p.text("tok", x, y + 15, 9, align="center", color=GRAY, hand=True, upper=False)

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


# ====================================================================== Mehr Varianten (0.5.1)
def _mouth(c, lean, look):
    hd = S.seated_at(c.hip, lean=lean, look=look)["head"]
    return hd, (hd[0] + 12, hd[1] + 4)

def _fly(p, x, y, t):
    p.circle(x, y, 2.2, w=1.4, fill=INK)
    w = 3 + 2 * math.sin(t * 60)
    p.line(x, y, x - 4, y - w, w=1.0, color=GRAY, amp=0)
    p.line(x, y, x + 3, y - w, w=1.0, color=GRAY, amp=0)

def idle_fly(p, a, t, c):
    """Eine lange Zunge schnellt hervor und verspeist eine Fliege."""
    u = t % 10.0
    lean, look = -6, 6
    hd, mouth = _mouth(c, lean, look)
    ox, oy = hd[0] + 80, hd[1] - 14
    def fp(v):
        return (ox + 55 * math.sin(v * 2.1) + 14 * math.sin(v * 7), oy + 30 * math.sin(v * 3.1))
    TS, TE = 4.0, 4.5                                          # Zunge schnellt: TS…TE, zieht zurück bis TE+0.5
    target = fp(TS)
    S.seated(p, c.hip, lean=lean, look=look, hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    if u < TS:
        fx, fy = fp(u)
        _fly(p, fx, fy, t)
        if u > TS - 1.2:                                         # er hat sie im Blick, Mund geht auf
            p.circle(mouth[0], mouth[1], 3, w=1.8, fill=INK)
    elif u < TE + 0.5:
        k = _ease((u - TS) / 0.12) if u < TS + 0.12 else (1.0 if u < TE else 1 - _ease((u - TE) / 0.5))
        tip = (mouth[0] + (target[0] - mouth[0]) * k, mouth[1] + (target[1] - mouth[1]) * k)
        pts = [(mouth[0] + (tip[0] - mouth[0]) * j / 6, mouth[1] + (tip[1] - mouth[1]) * j / 6 + 3 * math.sin(j + t * 20) * k) for j in range(7)]
        p.curve(pts, w=4.5, color=(0.9, 0.35, 0.45))
        p.circle(tip[0], tip[1], 4, w=1.6, color=(0.9, 0.35, 0.45), fill=(1.0, 0.6, 0.65))
        if u >= TE:
            _fly(p, tip[0], tip[1], t)
        elif u < TS + 0.3:
            p.text("schnapp!", (mouth[0] + tip[0]) / 2, mouth[1] - 20, 16, align="center", color=RED, hand=True, upper=False)
    elif u < 8.0:
        p.text("schmatz", mouth[0] + 30, mouth[1] - 24, 15, color=GRAY, hand=True, upper=False)
        if 6.3 < u < 7.6:
            p.text("(Proteine!)", mouth[0] + 46, mouth[1] - 44, 13, color=GRAY, hand=True, upper=False)
    else:
        fx, fy = fp(u + 20)                                       # nächste Fliege kommt an
        _fly(p, fx, fy, t)
    return "frisst eine Fliege – die Zunge war schneller"

def idle_desksleep(p, a, t, c):
    """Der Kopf liegt schlafend auf der Notebooktastatur."""
    lean, look = 54, 18
    h = S.seated(p, c.hip, lean=lean, look=look, eyes="dots",
                 hands=((c.cx + 52, c.desk_y - 3), (c.cx + 44, c.desk_y - 3)))
    hx, hy = h["head"]
    breath = 1.5 * math.sin(t * 1.6)
    p.line(c.lap_x - 40, c.desk_y - 1 - breath * 0.2, c.lap_x - 20, c.desk_y - 1, w=1.2, color=GRAY, amp=0)
    for i in range(3):
        k = (t * 0.4 + i / 3) % 1
        p.text("z", hx + 10 + k * 40, hy - 24 - k * 80, 14 + k * 20, color=GRAY, hand=True)
    p.text("zzzzzzzzzzzz", c.lap_x + 4, c.desk_y - 30, 8, color=GRAY, hand=True, upper=False, jitter=0.2)   # Tastatur-Abdruck auf dem Bildschirm
    p.circle(hx + 12, hy + 12 + 1.5 * math.sin(t), 2.5 + 1.2 * math.sin(t * 0.7), w=1.2, color=BLUE, fill=(0.85, 0.92, 1.0))
    return "Nickerchen auf der Tastatur"

def idle_paperball(p, a, t, c):
    """Papierkugel knüllen und in den Eimer werfen – manchmal daneben."""
    u = t % 8.0
    n = int(t / 8.0)
    hit = (kh(a.key) + n) % 3 != 0
    lean = 4
    hd = S.seated_at(c.hip, lean=lean, look=6)["head"]
    bin_x = 420
    p.poly([(bin_x - 16, FLOOR - 34), (bin_x - 12, FLOOR), (bin_x + 12, FLOOR), (bin_x + 16, FLOOR - 34)], w=2.2)
    shx, shy = S.seated_at(c.hip, lean=lean)["sh"]
    lap = (c.cx + 26, c.hip[1] - 5)
    start = (shx + 26, shy + 4)
    hold = (shx + 22, shy - 10)
    hand = _seq(u, [(0, lap), (1.2, lap), (2.0, start), (3.2, start), (3.6, hold), (3.9, (shx + 34, shy - 6)), (5.0, lap), (8, lap)])
    S.seated(p, c.hip, lean=lean, look=6, hands=(hand, (c.cx + 30, c.hip[1] - 4)))
    tgt = (bin_x + (0 if hit else -30), FLOOR - 36 if hit else FLOOR - 4)
    if u < 3.8:
        r = 2 + 6 * _ease((u - 1.2) / 1.6) if u > 1.2 else 0
        if u < 2.0 and u > 1.2:
            p.poly([(hand[0] - 9, hand[1] - 2), (hand[0] + 9, hand[1] - 5), (hand[0] + 8, hand[1] + 6)], closed=True, w=1.2, fill=PAPER)
        elif u >= 2.0:
            p.circle(hand[0], hand[1] - 5, 5.5, w=1.8, fill=PAPER)
    elif u < 4.9:
        k = (u - 3.8) / 1.1
        x = hand[0] + (tgt[0] - hand[0]) * k
        y = hand[1] + (tgt[1] - hand[1]) * k - 90 * math.sin(k * math.pi)
        p.circle(x, y, 5.5, w=1.8, fill=PAPER)
    else:
        if not hit:
            p.circle(tgt[0], tgt[1], 5.5, w=1.8, fill=PAPER)
        if u < 6.8:
            p.text("Treffer! 2 Punkte" if hit else "daneben…", bin_x - 50, FLOOR - 62, 15, align="center", color=BLUE if hit else RED, hand=True, upper=False)
    for i in range(min(4, n // 2)):
        p.circle(c.cx + 60 + 11 * i, FLOOR - 5, 5, w=1.4, fill=PAPER)
    return "Papierkugel-Basketball"

def idle_spin(p, a, t, c):
    """Dreht sich auf dem Bürostuhl."""
    u = t % 9.0
    spinning = 2.0 < u < 6.0
    flip = (int(t * 3.5) % 2 == 0) if spinning else True
    hip = c.hip
    feet = ((hip[0] + LEG + 3, FLOOR - (6 if spinning else 0)), (hip[0] + LEG - 5, FLOOR - (6 if spinning else 0)))
    arms = (160, 200) if spinning else (-60, -40)
    lean = 8 * math.sin(t * 7) if spinning else -4
    p.figure(hip[0], hip[1], la=arms, ra=(-arms[0], -arms[1]) if spinning else (-60, -40), lean=lean, flip=flip,
             hands=(None, None), feet=feet, splay=spinning, eyes="dots" if spinning else None)
    if spinning:
        for i in range(3):
            ang = t * 8 + i * 2.1
            p.arc(hip[0], hip[1] - 20, 60 + 8 * i, ang, ang + 1.0, w=1.3, color=GRAY)
        p.text("wiiiii!", hip[0] + 40, hip[1] - 110, 20, align="center", color=BLUE, hand=True, upper=False)
    return "Bürostuhl-Karussell"

def idle_stretch(p, a, t, c):
    """Streckt sich und gähnt."""
    fx = 125
    u = (t % 9.0) / 9.0
    k = math.sin(math.pi * min(1.0, u * 1.6)) if u < 0.62 else 0.0
    sway = 10 * math.sin(t * 1.4) * k
    an = Pen.anchors(fx, _stand_hip(), lean=sway * 0.5)
    sh, hd = an["sh"], an["head"]
    up = 1.9 * 24 * k + 0.9 * 24 * (1 - k)
    hands = ((sh[0] - 8 * k - 14 * (1 - k), sh[1] - up * k + 36 * (1 - k)), (sh[0] + 8 * k + 14 * (1 - k), sh[1] - up * k + 36 * (1 - k)))
    h = p.figure(fx, _stand_hip(), lean=sway * 0.5, hands=hands, splay=True, feet=((fx - 10, FLOOR), (fx + 10, FLOOR)), eyes="dots")
    if k > 0.5:
        p.circle(h["head"][0] + 1, h["head"][1] + 5, 4.2, w=1.6, fill=INK)
        p.text("gääähn", h["head"][0] + 60, h["head"][1] - 20, 18, align="center", color=GRAY, hand=True, upper=False)
    return "reckt sich nach dem Stillsitzen"

def idle_phone(p, a, t, c):
    """Scrollt durchs Handy, der Daumen wischt."""
    lean = 14
    hd = S.seated_at(c.hip, lean=lean, look=14)["head"]
    ph = (hd[0] + 22, hd[1] + 22)
    sw = (t * 2.2) % 1
    S.seated(p, c.hip, lean=lean, look=14, hands=((ph[0] - 4, ph[1] + 12), (ph[0] + 2, ph[1] + 8)))
    p.rect(ph[0] - 7, ph[1] - 14, 14, 26, lw=1.8, fill=PAPER)
    for i in range(3):
        y = ph[1] - 10 + ((i * 8 + sw * 8) % 24)
        p.line(ph[0] - 4, y, ph[0] + 4, y, w=1, color=GRAY, amp=0)
    p.text("nur noch ein Post…", ph[0] + 50, ph[1] - 36, 14, align="center", color=GRAY, hand=True, upper=False)
    return "Doomscrolling in der Wartezeit"

def idle_spider(p, a, t, c):
    """Eine Spinne seilt sich ab, der Agent schaut ihr zu."""
    d = _ease(((t % 10) - 0.5) / 3.0) * (1 - _ease(((t % 10) - 7.0) / 2.5))
    lean = -8
    hd = S.seated_at(c.hip, lean=lean, look=-6)["head"]
    S.seated(p, c.hip, lean=lean, look=-6, hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    sx, sy = hd[0] + 4, 60 + (hd[1] - 62 - 60) * d
    p.line(sx, 46, sx, sy, w=1.0, color=GRAY, amp=0)
    p.circle(sx, sy + 4, 4, w=1.6, fill=INK)
    for i in range(4):
        for e in (-1, 1):
            p.line(sx, sy + 4, sx + e * 9, sy + 1 + i * 2.5 - 3, w=1.0, amp=0)
    if d > 0.9:
        S.say_at(p, hd, "Hallo, Mitbewohner.", w=200, h=64, dx=60)
    return "bekommt Besuch von der Spinne"

def think_chew(p, a, t, c):
    """Kaut nachdenklich am Stift."""
    hd = S.seated_at(c.hip, lean=-6, look=8)["head"]
    mouth = (hd[0] + 12, hd[1] + 5)
    S.seated(p, c.hip, lean=-6, look=8, hands=((mouth[0] - 2, mouth[1] + 14), (c.cx + 26, c.hip[1] - 5)))
    p.pencil(mouth[0] + 1, mouth[1] + 2 + 1.5 * math.sin(t * 6), 100 + 8 * math.sin(t * 6), L=36)
    S.think_at(p, hd, _frag(a, t))
    return "kaut am Bleistift, bis die Idee kommt"

def stream_sweat(p, a, t, c):
    """Tippt so schnell, dass es spritzt."""
    hl, hr, lean, look = S.typing_hands(t * 1.8, max(a.rate, 80), c.keys)
    h = S.seated(p, c.hip, lean=lean + 4, look=look, hands=(hl, hr))
    hx, hy = h["head"]
    for i in range(3):
        k = (t * 1.3 + i / 3) % 1
        p.circle(hx - 8 - 14 * k, hy - 12 + 36 * k * k, 2.4 - k, w=1.2, color=BLUE, fill=(0.85, 0.92, 1.0))
    for i in range(3):
        p.line(hl[0] - 14 - 6 * i, hl[1] - 4 + 4 * i, hl[0] - 24 - 6 * i, hl[1] - 4 + 4 * i, w=1.2, color=GRAY, amp=0)
    return "tippt, dass die Tasten qualmen"

def error_headdesk(p, a, t, c):
    """Haut verzweifelt den Kopf auf den Tisch."""
    u = (t * 0.9) % 1.0
    k = 1.0 if 0.7 < u < 0.82 else _ease(1 - abs(u - 0.4) / 0.4) * 0.0
    lean = 10 + 44 * (_ease((u - 0.55) / 0.15) if u < 0.72 else 1 - _ease((u - 0.72) / 0.25))
    h = S.seated(p, c.hip, lean=lean, look=14, eyes="x", hands=((c.cx + 52, c.desk_y - 3), (c.cx + 44, c.desk_y - 3)))
    if lean > 48:
        p.text("bonk!", h["head"][0] + 20, h["head"][1] - 26, 18, align="center", color=RED, hand=True, upper=False)
        for i in (-1, 0, 1):
            p.line(h["head"][0] + 10, h["head"][1] - 10, h["head"][0] + 10 + 14 * i, h["head"][1] - 24, w=1.3, color=GRAY, amp=0)
    return a.last_error or "Fehler"

NEW_IDLE = [idle_guest, idle_postman, idle_fly, idle_desksleep, idle_paperball, idle_spin, idle_stretch, idle_phone, idle_spider]

# ====================================================================== Tabellen
ACTS = {
    "thinking": [None, think_pace, think_back, think_yoyo, think_chew],
    "streaming": [None, stream_coffee, stream_groove, stream_sweat],
    "compacting": [None, compact_suitcase],
    "error": [None, error_run, error_extinguisher, error_headdesk],
    "retrying": [None, retry_bell, retry_peek],
    "bash": [None, bash_terminal, bash_crank],
    "read": [None, read_scroll, read_aloud],
    "write": [None, write_tablet, write_board],
    "subagent": [None, sub_flag, sub_bell],
    "other": [None, other_binoculars],
    "idle": [None, idle_news, idle_coffee, idle_juggle, idle_plant, idle_plane, idle_visitor, idle_bird, idle_yoga] + NEW_IDLE,
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
    kind = int(h * 8)                       # 6, 7 = ruhiger Slot
    u = t - slot * AMBIENT_SLOT_S - 3 - 4 * _perm_pos(key, slot)
    if kind > 5 or u < 0:
        return
    d = 1 if slot % 2 else -1
    if kind == 0 and u < 16:
        x = (30 + 410 * u / 16) if d > 0 else (440 - 410 * u / 16)
        _cat(p, x, d, t)
    elif kind == 1 and u < 11:
        k = u / 11
        x = (-10 + 460 * k) if d > 0 else (450 - 460 * k)
        _bird(p, x, 84 + 10 * math.sin(k * 9), t, d)
    elif kind == 2 and u < 20:
        k = u / 20
        _balloon(p, 40 + 360 * ((kh(key) + slot) % 7) / 7, FLOOR - 20 - (FLOOR - 90) * k, t)
    elif kind == 3 and u < 24:
        _snail(p, 40 + 90 * u / 24 + 200 * (slot % 2), t)
    elif kind == 4 and u < 14:
        k = u / 14
        _postman_walk(p, 20 + 420 * k if d > 0 else 440 - 420 * k, d, t)
    elif kind == 5 and u < 12:
        k = u / 12
        x = (-10 + 460 * k) if d > 0 else (450 - 460 * k)
        _drone(p, x, 74 + 8 * math.sin(k * 11), t)

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
