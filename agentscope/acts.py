"""Abwechslung für den Hauptagenten: Varianten je Phase, Siegestanz, Idle-Miniszenen, Besucher.

Jede Phase hat mehrere Varianten (Index 0 = die klassische Pose in scene.py). Welche läuft, entscheidet
`variant()`: deterministisch aus Agent und Zeit, wechselt alle VARIANT_S Sekunden, wiederholt nie
direkt dieselbe. Ist ein Prozess fertig geworden (`Agent.idle_for` < FINALE_S), tanzt der Agent auf dem
Tisch. Alles hier ist beweglich (dynamische Ebene); nichts davon ist zwischengespeichert.
"""

from __future__ import annotations

import math
import random

from . import quips
from types import SimpleNamespace

from . import dance
from . import scene as S
from .sketch import BLUE, GRAY, INK, LEG, PAPER, RED, Pen

VARIANT_S = 10.0       # so lange läuft eine Variante einer Phase
IDLE_SLOT_S = 14.0     # so lange läuft eine Idle-Szene
FINALE_S = 15.0        # so lange tanzt der Agent nach getaner Arbeit
FORCE: dict = {}       # Vorschau/Tests: {"variant": n} erzwingt eine Variante

# Pro Programmlauf neu: Szenen und Varianten laufen nie in derselben Reihenfolge wie beim letzten Mal.
# Innerhalb eines Laufs bleibt die Folge stabil (kein Flackern), nur die Reihenfolge ist jedes Mal anders.
RUN_SEED = random.randrange(1 << 30)

FLOOR = S.FLOOR

def kh(s: str) -> int:
    """Stabiler String-Hash (Python-hash() ist je Start zufällig)."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(s or "?"))

def _perm(key: str, name: str, rnd: int, n: int) -> list[int]:
    return sorted(range(n), key=lambda i: (S._hash01(kh(key), kh(name), rnd, i, RUN_SEED), i))

def variant(key: str, name: str, t: float, n: int, period: float = VARIANT_S) -> int:
    """Variante 0…n-1 zum Zeitpunkt t: in jeder Runde eine neue Mischung, nie zweimal hintereinander gleich."""
    if n <= 1:
        return 0
    if FORCE.get("variant") is not None:
        return FORCE["variant"] % n
    slot = int(t / period)
    if n == 2:
        return (slot + kh(key) + RUN_SEED) % 2
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
    p.bubbles.append(("say", (x, y, w, h)))       # Faden soll dahinter verschwinden

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
    return dance.FINALE_ORDER[(kh(a.key) + a.turn + RUN_SEED) % len(dance.FINALE_ORDER)]

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
    p.text(name, vx, sh[1] + 12, 9, align="center", color=BLUE, hand=True, upper=False)
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
        p.text(f"+{amount}k tok", hand[0] + 30, hand[1] - 100, 20, align="center", color=BLUE, hand=True, upper=False)
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
    _drool(p, hx + 11, hy + 8, c.desk_y - 2, ((t % IDLE_SLOT_S) - 2.0) / 5.0)
    return "Nickerchen auf der Tastatur (sabber)"

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

# ====================================================================== Popkultur, Besuch, Sport (0.6.0)
PINK = (0.85, 0.25, 0.5)
GREEN = (0.30, 0.48, 0.26)
GOLD = (1.0, 0.85, 0.3)

def _in(u, a, b):
    return a <= u < b

def _slot(a, t):
    return t % IDLE_SLOT_S, int(t / IDLE_SLOT_S)

def _actor(p, x, t, *, s=0.9, flip=False, color=BLUE, walking=False, hands=None, feet=None, lean=0.0, eyes=None, hip_dy=0.0, w=2.4):
    """Stehende Nebenfigur. hands: None | ((x,y),(x,y)) | Funktion(Schulter) -> Hände. → (Figur, Schulter)."""
    hip_y = FLOOR - 2 * LEG * s + 0.5 + hip_dy
    if feet is None:
        feet = _walk_feet(x, t * 6, stance=8 * s, step=11 * s, lift=6) if walking else ((x - 8 * s, FLOOR), (x + 8 * s, FLOOR))
    sh = Pen.anchors(x, hip_y, s=s, flip=flip, lean=lean)["sh"]
    if callable(hands):
        hands = hands(sh)
    elif hands is None:
        hands = ((sh[0] + 8 * s, sh[1] + 32 * s), (sh[0] + 2 * s, sh[1] + 34 * s))
    f = p.figure(x, hip_y, s=s, flip=flip, feet=feet, hands=hands, color=color, lean=lean, eyes=eyes, w=w)
    return f, sh

def _host(p, c, *, lean=-6, look=0, hands=None, eyes=None):
    hands = hands or ((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4))
    S.seated(p, c.hip, lean=lean, look=look, hands=hands, eyes=eyes)
    return S.seated_at(c.hip, lean=lean, look=look)["head"]

def _sparkle(p, x, y, r, color=GRAY):
    p.line(x - r, y, x + r, y, w=1.2, color=color, amp=0)
    p.line(x, y - r, x, y + r, w=1.2, color=color, amp=0)

def _heart(p, x, y, r, color=RED):
    pts = []
    for i in range(25):
        a = i / 24 * 2 * math.pi
        pts.append((x + 16 * math.sin(a) ** 3 * r / 16,
                    y - (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) * r / 16))
    p.poly(pts, closed=True, w=1.5, color=color, fill=(1.0, 0.86, 0.9), amp=0)

def _blush(p, head):
    for i in range(3):
        p.line(head[0] + 3 + 3 * i, head[1] + 3, head[0] + 1 + 3 * i, head[1] + 8, w=1.3, color=RED, amp=0)

def _saber(p, base, tip, color):
    light = tuple(0.55 + 0.45 * ch for ch in color)
    p.line(*base, *tip, w=8, color=light, amp=0)
    p.line(*base, *tip, w=3.4, color=color, amp=0)
    p.line(*base, *tip, w=1.2, color=PAPER, amp=0)

def _drool(p, mx, my, bottom_y, k):
    """Sabber: läuft vom Mundwinkel nach unten (k 0…1), unten sammelt sich ein Tropfen/Pfütze."""
    k = max(0.0, min(1.0, k))
    end = my + (bottom_y - my) * k
    col = (0.45, 0.65, 0.95)
    p.line(mx, my, mx + 1.5, end, w=1.8, color=col, amp=0)
    p.circle(mx + 1.5, end + 2, 2.2, w=1.3, color=col, fill=(0.85, 0.92, 1.0))
    if k >= 0.98:
        p.curve([(mx - 10, bottom_y), (mx + 1, bottom_y - 3), (mx + 12, bottom_y)], w=1.4, color=col)

# ---------------------------------------------------------------- Star Trek
def idle_trek(p, a, t, c):
    """Ein Vulkanier grüßt, wird nicht verstanden und lässt sich hochbeamen."""
    u, _ = _slot(a, t)
    vx, walking, flip = _arrive(u) if u < 11 else (110, False, True)
    salute = _in(u, 3.2, 7.2)
    def hf(sh):
        return ((sh[0] + 22, sh[1] - 16), (sh[0] + 4, sh[1] + 32)) if salute else None
    beam = max(0.0, min(1.0, (u - 11.0) / 2.6))
    cr = p.cr
    cr.save()
    if beam > 0:
        cr.rectangle(0, FLOOR - 120 + beam * 125, 400, 200)
        cr.clip()
    f, sh = _actor(p, vx, t, walking=walking, flip=flip, hands=hf, color=BLUE)
    hx, hy = f["head"]
    for e in (-1, 1):
        p.poly([(hx + e * 12, hy - 2), (hx + e * 19, hy - 12), (hx + e * 10, hy - 8)], closed=True, w=1.4, color=BLUE, fill=PAPER, amp=0)
    p.line(hx - 12, hy - 7, hx + 12, hy - 7, w=3.2, color=BLUE, amp=0)
    p.rect(vx - 10, sh[1] + 12, 20, 6, lw=1.0, color=BLUE, fill=(0.8, 0.88, 1.0))      # Uniform-Streifen
    if salute:
        hnd = f["hl"]
        p.line(hnd[0], hnd[1], hnd[0] - 3, hnd[1] - 8, w=1.4, color=BLUE, amp=0)
        p.line(hnd[0], hnd[1], hnd[0] + 3, hnd[1] - 8, w=1.4, color=BLUE, amp=0)
    cr.restore()
    if u >= 10.6:
        for i in range(16):
            ph = (t * 0.9 + i * 0.37) % 1
            sx = vx - 18 + 36 * S._hash01(i, int(t * 3), 4)
            sy = FLOOR - 4 - 110 * ph
            if sy > FLOOR - 120 + beam * 125 - 10:
                _sparkle(p, sx, sy, 2.5 + 2 * (1 - ph), color=BLUE if i % 2 else GRAY)
    hd = _host(p, c, lean=-6, look=-14 if _in(u, 3, 11) else 0,
               hands=((c.cx + 40, c.hip[1] - 40), (c.cx + 30, c.hip[1] - 4)) if _in(u, 6.4, 8.4) else None)
    if _in(u, 3.2, 6.4):
        S.say_at(p, f["head"], quips.line("spock_greeting", a.key, int(t / IDLE_SLOT_S)), w=300, h=80, size=17, dx=70, color=BLUE)
    elif _in(u, 6.4, 9.2):
        S.say_at(p, hd, quips.line("spock_reply", a.key, int(t / IDLE_SLOT_S)), w=320, h=84, size=16, dx=40)
    elif _in(u, 9.2, 11.4):
        S.say_at(p, f["head"], quips.line("spock_beam", a.key, int(t / IDLE_SLOT_S), 2), w=280, h=80, size=17, dx=70, color=BLUE)
    return "Raumschiff Strichmännchen: Beam me up"

# ---------------------------------------------------------------- Zombies
def idle_zombies(p, a, t, c):
    """Zwei Zombies wollen Hirn. Der Agent bietet den Cache an."""
    u, _ = _slot(a, t)
    e = max(0.0, min(1.0, min(u / 3.5, (IDLE_SLOT_S - u) / 3.0)))
    moving = u < 3.5 or u >= 11
    x1 = -30 + 150 * e
    x2 = -50 + 105 * e
    sway = 0 if moving else 2.5 * math.sin(t * 1.3)
    heads = []
    for i, x in enumerate((x1, x2)):
        x += sway * (1 if i else -1)
        f, sh = _actor(p, x, t * 0.45, s=0.9, flip=True, color=GREEN, lean=14, eyes="x", walking=moving,
                       hands=lambda sh: ((sh[0] + 31, sh[1] + 1 + 3 * math.sin(t * 2)), (sh[0] + 27, sh[1] + 10)))
        heads.append(f["head"])
    p.curve([(x2 - 8, FLOOR - 1), (x2 - 2, FLOOR - 4), (x2 + 6, FLOOR - 1)], w=1.6, color=GREEN)    # schleift ein Bein nach
    scared = _in(u, 3.5, 11)
    hd = _host(p, c, lean=-12 if scared else -6, look=-12 if scared else 0, eyes="dots" if scared else None,
               hands=((c.cx + 34, c.hip[1] - 62), (c.cx + 24, c.hip[1] - 64)) if scared else None)
    if _in(u, 3.5, 7.2):
        S.say_at(p, heads[0], quips.line("zombie", a.key, int(t / IDLE_SLOT_S)), w=250, h=70, size=18, dx=60, color=GREEN)
    elif _in(u, 7.2, 11):
        S.say_at(p, hd, quips.line("zombie_reply", a.key, int(t / IDLE_SLOT_S)), w=320, h=84, size=16, dx=40)
    return "Zombie-Apokalypse im Kontextfenster"

# ---------------------------------------------------------------- Star Wars
def idle_starwars(p, a, t, c):
    """Der Agent als Sith-Lord im Lichtschwertduell mit einem Jedi."""
    u, _ = _slot(a, t)
    e = max(0.0, min(1.0, min(u / 2.0, (IDLE_SLOT_S - u) / 2.5)))
    jx = -20 + 90 * e
    vx = 172
    fight = _in(u, 2.2, 11.5)
    ang_j = (35 + 28 * math.sin(t * 4.6)) if fight else 12
    ang_v = (35 + 28 * math.sin(t * 4.6 + math.pi)) if fight else 12
    # Umhang
    p.poly([(vx + 4, FLOOR - 2 * LEG + 0.5 - 40 + 40), (vx + 30, FLOOR - 8), (vx + 12, FLOOR - 6)], closed=True, w=1.6, color=INK, fill=(0.8, 0.8, 0.8), amp=0)
    fv, shv = _actor(p, vx, t, s=1.0, flip=False, color=INK, hands=lambda sh: ((sh[0] - 26, sh[1] + 8), (sh[0] - 16, sh[1] + 16)))
    hx, hy = fv["head"]
    p.circle(hx, hy, 14.5, w=1.6, fill=INK)
    p.poly([(hx - 10, hy + 6), (hx + 10, hy + 6), (hx + 6, hy + 16), (hx - 6, hy + 16)], closed=True, w=1.2, fill=INK, amp=0)
    p.line(hx - 7, hy - 2, hx - 1, hy + 1, w=2.0, color=PAPER, amp=0)
    fj, shj = _actor(p, jx, t, s=0.9, flip=True, color=BLUE, walking=e < 1 and u < 11,
                     hands=lambda sh: ((sh[0] + 24, sh[1] + 6), (sh[0] + 14, sh[1] + 14)))
    bj, bv = fj["hl"], fv["hl"]
    _saber(p, bj, (bj[0] + 46 * math.sin(math.radians(ang_j)), bj[1] - 46 * math.cos(math.radians(ang_j))), BLUE)
    _saber(p, bv, (bv[0] - 46 * math.sin(math.radians(ang_v)), bv[1] - 46 * math.cos(math.radians(ang_v))), RED)
    if fight and math.cos(t * 4.6 * 2) > 0.8:
        mx, my = (bj[0] + bv[0]) / 2, min(bj[1], bv[1]) - 28
        for k in range(6):
            r = k * math.pi / 3 + t
            p.line(mx + 5 * math.cos(r), my + 5 * math.sin(r), mx + 13 * math.cos(r), my + 13 * math.sin(r), w=1.4, color=GOLD, amp=0)
    if _in(u, 0, 2.2):
        p.text("kchh… kchh…", vx - 10, hy - 26, 14, align="center", color=GRAY, hand=True, upper=False)
    elif _in(u, 3.5, 6.8):
        S.say_at(p, fv["head"], quips.line("vader", a.key, int(t / IDLE_SLOT_S)), w=270, h=74, size=17, dx=-20, color=INK)
    elif _in(u, 6.8, 10.8):
        S.say_at(p, fj["head"], quips.line("jedi", a.key, int(t / IDLE_SLOT_S)), w=320, h=90, size=16, dx=60, color=BLUE)
    return "Möge der Merge mit dir sein"

# ---------------------------------------------------------------- Herr der Ringe
def idle_lotr(p, a, t, c):
    """Der Agent verfällt dem einen Ring; ein Zauberer verbietet das Vorbeikommen."""
    u, _ = _slot(a, t)
    vx, walking, flip = _arrive(u) if u < 11 else (110, False, True)
    slam = _in(u, 4.4, 5.2)
    lift = 22 * math.sin((u - 4.4) / 0.8 * math.pi) if slam else 0
    def hf(sh):
        return ((sh[0] + 22, sh[1] + 20), (sh[0] + 8, sh[1] + 26))
    f, sh = _actor(p, vx, t, s=0.95, walking=walking, flip=flip, color=(0.35, 0.35, 0.4), hands=hf)
    col = (0.35, 0.35, 0.4)
    hx, hy = f["head"]
    p.poly([(sh[0] - 6, sh[1]), (sh[0] + 6, sh[1]), (vx + 17, FLOOR - 4), (vx - 17, FLOOR - 4)], closed=True, w=1.5, color=col, fill=(0.93, 0.93, 0.95), amp=0)
    p.poly([(hx - 14, hy - 9), (hx + 14, hy - 9), (hx + 3, hy - 54)], closed=True, w=1.6, color=col, fill=(0.85, 0.85, 0.9), amp=0)
    p.line(hx - 19, hy - 9, hx + 19, hy - 9, w=2.0, color=col, amp=0)
    p.poly([(hx - 7, hy + 8), (hx + 7, hy + 8), (hx + 1, hy + 36)], closed=True, w=1.4, color=col, fill=PAPER, amp=0)
    stx = f["hl"][0]
    top = f["hl"][1] - 70
    p.line(stx, FLOOR - lift, stx, top, w=2.6, color=(0.45, 0.3, 0.15), amp=0.3)
    p.circle(stx, top - 3, 4.5, w=1.4, color=col, fill=(1.0, 0.97, 0.8))
    if slam or _in(u, 5.2, 5.7):
        for k in range(8):
            r = math.pi * (0.1 + 0.8 * k / 7)
            p.line(stx + 8 * math.cos(r), FLOOR - 2 - 8 * math.sin(r), stx + 26 * math.cos(r), FLOOR - 2 - 26 * math.sin(r), w=1.4, color=GOLD, amp=0)
    ring = _in(u, 0, 4.6)
    hd = _host(p, c, lean=-6, look=-14 if _in(u, 3, 11) else 0, eyes="dots" if ring else None,
               hands=((c.cx + 40, c.hip[1] - 66 + 3 * math.sin(t * 3)), (c.cx + 30, c.hip[1] - 4)) if ring else None)
    if ring:
        rx, ry = c.cx + 42, c.hip[1] - 78 + 3 * math.sin(t * 3)
        p.circle(rx, ry, 4.2, w=2.2, color=(0.8, 0.6, 0.1), fill=PAPER)
        _sparkle(p, rx + 7, ry - 7, 3, color=GOLD)
        if u < 3.2:
            S.say_at(p, hd, "Mein Schaaatz…", w=220, h=64, size=19, dx=40)
    if _in(u, 4.4, 8.4):
        S.say_at(p, f["head"], quips.line("gandalf", a.key, int(t / IDLE_SLOT_S)), w=300, h=80, size=19, dx=70, color=col)
    elif _in(u, 8.4, 11):
        S.say_at(p, hd, quips.line("gandalf_reply", a.key, int(t / IDLE_SLOT_S)), w=320, h=90, size=16, dx=40)
    return "Der Herr der Token"

# ---------------------------------------------------------------- Kaffee zu zweit
def idle_coffeeduo(p, a, t, c):
    """Gast setzt sich auf einen zweiten Stuhl; gemeinsame Kaffeepause mit Anstoßen."""
    u, n = _slot(a, t)
    gx = 118
    seated = u >= 3.2 and u < 12
    if seated or u >= 3.2:
        p.chair(gx, c.seat_y, c.floor, facing=1)
    sip = _in(u, 3.8, 6.0) or _in(u, 9.0, 11.0)
    clink = _in(u, 6.0, 8.2)
    mug_y = c.hip[1] - 34
    cl = (156, mug_y - 4)
    if seated:
        gh = (gx, c.seat_y - 3)
        gsh = Pen.anchors(*gh, lean=-4, flip=True)["sh"]
        hand = cl if clink else ((gsh[0] + 8, gsh[1] - 20 + 3 * math.sin(t * 5)) if sip else (gsh[0] + 18, mug_y + 8))
        gf = p.figure(gx, gh[1], lean=-4, flip=True, color=BLUE, hands=(None, hand),
                      feet=((gx + LEG + 3, FLOOR), (gx + LEG - 5, FLOOR)), la=(-60, -40))
        ghd = gf["head"]
        ghand = gf["hr"]
        _mug(p, ghand[0], ghand[1] + 10, steam_t=t)
    else:
        vx, walking, flip = _arrive(u) if u < 3.2 else (118, False, True)
        gf, _sh = _actor(p, vx, t, walking=walking, flip=flip)
        ghd = gf["head"]
    hhand = (cl[0] + 6, cl[1]) if clink else ((c.cx - 4, c.hip[1] - 44 + 3 * math.sin(t * 5)) if sip else (c.cx + 24, c.hip[1] - 6))
    hd = _host(p, c, lean=-6, look=-18 if u >= 3 else 0, hands=(hhand, (c.cx + 30, c.hip[1] - 4)))
    if u >= 3:
        _mug(p, hhand[0], hhand[1] + 10, steam_t=t + 1)
    if clink and 6.8 < u < 7.4:
        _sparkle(p, 160, mug_y - 12, 5, color=GOLD)
    if _in(u, 4.0, 6.0):
        S.say_at(p, ghd, "Pause! Die Tokens laufen nicht weg.", w=280, h=84, size=17, dx=40, color=BLUE)
    elif _in(u, 6.0, 8.2):
        S.say_at(p, hd, "Prost! Auf unseren Kontext.", w=270, h=80, size=17, dx=40)
    elif _in(u, 8.2, 11.6):
        S.say_at(p, ghd, "Gleich nochmal kompaktieren?", w=270, h=80, size=17, dx=40, color=BLUE)
    return "Kaffeepause zu zweit"

# ---------------------------------------------------------------- Flirt
def idle_flirt(p, a, t, c):
    """Eine Agentin kommt herein, zwinkert und flirtet. Der Agent wird rot."""
    u, _ = _slot(a, t)
    vx, walking, flip = _arrive(u) if u < 11 else (110, False, True)
    lean = 8 if _in(u, 5, 10) else 0
    wave = _in(u, 11.3, 13.5)
    def hf(sh):
        if wave:
            return ((sh[0] + 20, sh[1] - 20 + 8 * math.sin(t * 9)), (sh[0] + 14, sh[1] + 10))
        return ((sh[0] + 14, sh[1] + 22), (sh[0] + 14, sh[1] + 20))        # Hand in der Hüfte
    f, sh = _actor(p, vx + 2 * math.sin(t * 2) * (not walking), t, walking=walking, flip=flip, color=PINK, hands=hf, lean=lean)
    hx, hy = f["head"]
    hip = f["hip"]
    p.poly([(hip[0], hip[1] - 4), (hip[0] - 17, hip[1] + 24), (hip[0] + 17, hip[1] + 24)], closed=True, w=1.6, color=PINK, fill=(1.0, 0.9, 0.93), amp=0)
    for e in (-1, 1):
        p.curve([(hx + e * 11, hy - 6), (hx + e * 16, hy + 8), (hx + e * 12 + math.sin(t * 2) * 2, hy + 22)], w=2.0, color=PINK)
    p.line(hx - 12, hy - 8, hx + 12, hy - 8, w=2.4, color=PINK, amp=0)
    p.circle(hx - 9, hy - 14, 3.5, w=1.4, color=PINK, fill=(1.0, 0.8, 0.88))                  # Schleife
    p.curve([(hx + 5, hy + 6), (hx + 9, hy + 8), (hx + 13, hy + 6)], w=2.2, color=RED)          # Lippen
    if _in(u, 3.4, 4.4):
        p.line(hx + 4, hy - 3, hx + 9, hy - 3, w=1.6, color=PINK, amp=0)                         # Zwinkern
    if u >= 3.4 and u < 11:
        for i in range(4):
            k = (t * 0.35 + i / 4) % 1
            _heart(p, hx + 18 + 16 * math.sin(i * 2 + t), hy - 22 - k * 70, 5 + 2 * (1 - k), color=RED if i % 2 else PINK)
    hd = _host(p, c, lean=-4, look=-18 if _in(u, 3, 11) else 0, eyes="dots" if _in(u, 4.6, 11) else None)
    if _in(u, 5, 11):
        _blush(p, hd)
        p.text("*", hd[0] - 18, hd[1] - 16, 16, color=BLUE, hand=True)
    if _in(u, 3.4, 7.0):
        S.say_at(p, f["head"], "Na du? Kommst du öfter in Kontexte?", w=300, h=90, size=17, dx=70, color=PINK)
    elif _in(u, 7.0, 10.8):
        S.say_at(p, hd, "Äh… ich hab gleich einen Deploy!", w=300, h=84, size=17, dx=40)
    elif wave:
        S.say_at(p, f["head"], "Ruf mich an!", w=190, h=60, size=17, dx=60, color=PINK)
    return "Besuch: eine Agentin flirtet"

# ---------------------------------------------------------------- Kinder
def idle_kids(p, a, t, c):
    """Zwei Kinder toben durchs Büro und gehen dem Agenten auf die Nerven."""
    u, _ = _slot(a, t)
    e = max(0.0, min(1.0, min(u / 2.5, (IDLE_SLOT_S - u) / 2.5)))
    heads = []
    for i, col in enumerate((BLUE, RED)):
        xp = 80 + 55 * math.sin(t * (0.9 + 0.3 * i) + i * 2.1)
        x = -20 + (xp + 20) * e
        flip = math.cos(t * (0.9 + 0.3 * i) + i * 2.1) > 0
        jump = 7 * abs(math.sin(t * 5 + i))
        f, sh = _actor(p, x, t * 1.2, s=0.55, flip=flip, color=col, walking=True,
                       hands=lambda sh, i=i: ((sh[0] + 12, sh[1] - 14 + 6 * math.sin(t * 9 + i)), (sh[0] - 12, sh[1] - 12 + 6 * math.sin(t * 9 + i + 2))),
                       hip_dy=-jump)
        heads.append(f["head"])
    k = ((t - 2.5) * 0.12) % 1
    if u > 2.5:
        _plane(p, 20 + 300 * k, 120 + 30 * math.sin(k * 8), -0.2)
    mad = _in(u, 4, 11)
    hd0 = S.seated_at(c.hip, lean=-6, look=-10)["head"]
    hd = _host(p, c, lean=-6, look=-10 if u > 2 else 0, eyes="x" if _in(u, 8, 10) else None,
               hands=((hd0[0] + 13, hd0[1] + 2), (hd0[0] - 13, hd0[1] + 2)) if mad else None)
    if mad:
        zx, zy = hd[0] + 2, hd[1] - 26
        p.poly([(zx - 8, zy - 5), (zx - 2, zy - 1), (zx - 6, zy + 3), (zx + 2, zy + 6)], w=2.2, color=RED, amp=0)
        p.poly([(zx + 6, zy - 8), (zx + 12, zy - 4), (zx + 8, zy), (zx + 15, zy + 3)], w=2.2, color=RED, amp=0)
    if _in(u, 2.6, 5.2):
        S.say_at(p, heads[0], "Sind wir bald fertig?", w=250, h=70, size=17, dx=60, color=BLUE)
    elif _in(u, 5.2, 7.8):
        S.say_at(p, heads[1], "Mir ist so langweilig!", w=250, h=70, size=17, dx=60, color=RED)
    elif _in(u, 7.8, 10.6):
        S.say_at(p, hd, "Pssst! Papa kompaktiert!", w=270, h=70, size=17, dx=40)
    return "Kinder im Büro: Konzentration ist relativ"

# ---------------------------------------------------------------- No-AI-Demo
SIGNS = ["KEINE KI!", "MENSCHEN STATT MASCHINEN", "MEIN PROMPT, MEIN RECHT", "NO AI!"]

def idle_protest(p, a, t, c):
    """Drei Demonstranten mit Schildern ziehen gegen KI durchs Büro."""
    u, n = _slot(a, t)
    e = max(0.0, min(1.0, min(u / 3.0, (IDLE_SLOT_S - u) / 3.0)))
    moving = u < 3 or u >= 11
    heads = []
    for i in range(3):
        xp = 55 + 52 * i
        x = -30 - 40 * i + (xp + 30 + 40 * i) * e
        hold = lambda sh, i=i: ((sh[0] + 8, sh[1] - 16 + 4 * math.sin(t * 4 + i)), (sh[0] - 4, sh[1] - 12 + 4 * math.sin(t * 4 + i)))
        f, sh = _actor(p, x, t, s=0.85, flip=True, color=RED, walking=moving, hands=hold)
        hx, hy = f["head"]
        txt = SIGNS[(kh(a.key) + n + i) % len(SIGNS)]
        bx, by = f["hl"][0] - 22, f["hl"][1] - 48 + 4 * math.sin(t * 4 + i)
        p.line(f["hl"][0], f["hl"][1], f["hl"][0] - 1, by + 34, w=2.0, color=INK, amp=0)
        p.rect(bx - 12, by, 62, 34, lw=1.8, color=RED, fill=PAPER)
        p.text(txt, bx + 19, by + 14, 8, align="center", color=RED, maxw=58)
        if len(txt) > 12:
            p.text("", bx + 19, by + 26, 8)
        heads.append(f["head"])
    hd = _host(p, c, lean=-8, look=-10 if u > 2 else 0, eyes="dots" if _in(u, 8, 11) else None,
               hands=((c.cx + 24, c.hip[1] - 6), (c.cx + 30, c.hip[1] - 4)))
    if _in(u, 3.2, 7.4):
        S.say_at(p, heads[1], "Hey hey, ho ho, die KI muss weg!", w=300, h=84, size=17, dx=70, color=RED)
    elif _in(u, 7.4, 10.8):
        S.say_at(p, hd, quips.line("protest_reply", a.key, int(t / IDLE_SLOT_S)), w=320, h=84, size=16, dx=40)
    return "Demo: Menschen gegen Maschinen"

# ---------------------------------------------------------------- Cosplay / LARP
def idle_cosplay(p, a, t, c):
    """LARP-Pause: Eimer-Helm, Umhang, Schaumstoffschwert gegen einen Pappdrachen."""
    u, _ = _slot(a, t)
    sw = max(0.0, math.sin(t * 3.0)) if _in(u, 2, 10) else 0.0
    hx0 = 150
    hit = sw > 0.9
    dsh = 3 * math.sin(t * 20) if hit else 0
    dead = u >= 10
    # Drache aus Pappe
    dx0 = 62 + dsh
    tip = max(0.0, min(1.0, (u - 10) / 1.4))
    ang = -1.45 * _ease(tip)
    cr = p.cr
    if ang:
        cr.save()
        cr.translate(dx0 + 25, FLOOR)
        cr.rotate(ang)
        cr.translate(-(dx0 + 25), -FLOOR)
    p.rect(dx0, FLOOR - 34, 54, 34, lw=2.0, fill=(0.82, 0.72, 0.55))
    p.rect(dx0 + 50, FLOOR - 54, 24, 20, lw=2.0, fill=(0.82, 0.72, 0.55))
    p.poly([(dx0 + 8, FLOOR - 34), (dx0 + 20, FLOOR - 68), (dx0 + 34, FLOOR - 34)], closed=True, w=1.6, fill=(0.9, 0.8, 0.6))
    p.circle(dx0 + 62, FLOOR - 46, 2.2, w=1.2, fill=INK)
    p.curve([(dx0, FLOOR - 20), (dx0 - 14, FLOOR - 26 + 3 * math.sin(t * 4)), (dx0 - 20, FLOOR - 40)], w=2.0)
    if not dead:
        for i in range(4):
            fk = (t * 1.4 + i / 4) % 1
            p.curve([(dx0 + 74, FLOOR - 44), (dx0 + 82 + 10 * fk, FLOOR - 48 - 3 * fk), (dx0 + 92 + 14 * fk, FLOOR - 44 + 4 * math.sin(i + t * 9))], w=1.6, color=RED)
    if ang:
        cr.restore()
    if dead:
        p.text("plumps!", dx0 + 44, FLOOR - 66, 14, color=GRAY, hand=True, upper=False)
    p.text("Pappe", dx0 + 27, FLOOR - 12, 11, align="center", color=GRAY, hand=True, upper=False)
    # Ritter
    def hands(sh):
        return ((sh[0] - 26 - 16 * sw, sh[1] - 4 + 28 * sw), (sh[0] - 10, sh[1] + 16))
    cape_x = hx0 + 8
    p.poly([(cape_x, FLOOR - 2 * LEG - 38 + 40), (cape_x + 22 + 3 * math.sin(t * 3), FLOOR - 12), (cape_x + 8, FLOOR - 4)], closed=True, w=1.6, color=RED, fill=(1.0, 0.85, 0.85), amp=0)
    f, sh = _actor(p, hx0, t, s=1.0, flip=False, color=INK, hands=hands, lean=-6 * sw, hip_dy=0)
    hx, hy = f["head"]
    p.poly([(hx - 12, hy - 4), (hx + 12, hy - 4), (hx + 10, hy + 14), (hx - 10, hy + 14)], closed=True, w=1.8, fill=(0.88, 0.88, 0.9), amp=0)   # Eimer
    p.line(hx - 9, hy + 4, hx + 9, hy + 4, w=2.4, color=INK, amp=0)
    hnd = f["hl"]
    tip = (hnd[0] - 40 * math.cos(0.5 - 0.9 * sw), hnd[1] - 40 * math.sin(0.5 - 0.9 * sw) * (1 if sw < 0.5 else 0.2) - 4)
    p.line(*hnd, *tip, w=5, color=(0.6, 0.6, 0.65), amp=0)
    p.line(*hnd, *tip, w=1.6, color=INK, amp=0)
    p.line(hnd[0] - 2, hnd[1] - 7, hnd[0] + 2, hnd[1] + 7, w=3.0, amp=0)
    p.circle(f["hr"][0] + 4, f["hr"][1] + 2, 12, w=2.0, fill=(0.9, 0.9, 1.0))                       # Schild
    if hit:
        p.text("BOING!", dx0 + 60, FLOOR - 78, 18, align="center", color=RED, hand=True)
    if _in(u, 1, 4):
        S.say_at(p, f["head"], "Für Rohan! Äh… für den Merge!", w=280, h=84, size=17, dx=0)
    elif dead and u < 13:
        S.say_at(p, f["head"], "Der Drache ist besiegt!", w=240, h=70, size=17, dx=0)
    return "LARP-Pause: Ritter gegen Pappdrache"

# ---------------------------------------------------------------- Tai Chi
def idle_taichi(p, a, t, c):
    """Tai Chi: tiefe Hocke, langsam fließende Arme um eine Qi-Kugel."""
    fx = 130
    ph = t * 0.7
    hip_y = _stand_hip() + 9
    sh = Pen.anchors(fx, hip_y)["sh"]
    hl = (fx - 22 + 18 * math.cos(ph), sh[1] + 20 + 16 * math.sin(ph))
    hr = (fx - 22 + 18 * math.cos(ph + math.pi * 0.8), sh[1] + 20 + 16 * math.sin(ph + math.pi * 0.8))
    f = p.figure(fx, hip_y, hands=(hl, hr), feet=((fx - 24, FLOOR), (fx + 24, FLOOR)), eyes="dots", splay=True)
    bx, by = fx - 22, sh[1] + 20
    p.arc(bx, by, 12 + 2 * math.sin(ph), 0, 6.2, w=1.3, color=BLUE)
    for i in range(3):
        k = (t * 0.3 + i / 3) % 1
        p.arc(bx, by, 14 + k * 24, ph, ph + 1.2, w=1.0, color=GRAY)
    word = "einatmen…" if math.sin(ph) > 0 else "ausatmen…"
    p.text(word, fx + 54, f["head"][1] - 26, 15, align="center", color=GRAY, hand=True, upper=False)
    return "Tai Chi: Kontext fließen lassen"

# ---------------------------------------------------------------- Karate
def idle_karate(p, a, t, c):
    """Karate: Stirnband, Kiai und ein Brett, das beim Tritt zerbricht."""
    cyc = t % 4.5
    fx = 135
    hip_y = _stand_hip() + 5
    bx = 52
    kick = _in(cyc, 1.6, 2.5)
    broken = cyc >= 2.15
    kk = _ease(min(1.0, max(0.0, (cyc - 1.6) / 0.9)))      # 0…1 über den Tritt
    sh = Pen.anchors(fx, hip_y)["sh"]
    if kick:
        foot = (fx - 26 - 46 * kk, hip_y + 10 - 26 * kk)
        feet = ((fx - 6, FLOOR - 6 * (1 - kk)), foot)
        hands = ((sh[0] - 30, sh[1] + 4), (sh[0] + 12, sh[1] + 18))
    else:
        feet = ((fx - 22, FLOOR), (fx + 20, FLOOR))
        hands = ((sh[0] - 22, sh[1] - 6 + 3 * math.sin(t * 6)), (sh[0] - 10, sh[1] + 10))
    f = p.figure(fx, hip_y, hands=hands, feet=feet, eyes="dots" if kick else None, lean=-4 if kick else 4)
    hx, hy = f["head"]
    p.line(hx - 13, hy - 5, hx + 13, hy - 5, w=2.6, color=RED, amp=0)                                 # Stirnband
    p.line(hx + 13, hy - 5, hx + 22, hy - 1 + 3 * math.sin(t * 6), w=2.0, color=RED, amp=0)
    p.line(fx - 5, hip_y - 20, fx + 5, hip_y - 14, w=3.4, amp=0)                                      # schwarzer Gürtel
    # Brett auf zwei Blöcken
    p.rect(bx - 22, FLOOR - 16, 14, 16, lw=1.8, fill=PAPER)
    p.rect(bx + 8, FLOOR - 16, 14, 16, lw=1.8, fill=PAPER)
    if not broken:
        p.line(bx - 26, FLOOR - 19, bx + 26, FLOOR - 19, w=5, color=(0.7, 0.5, 0.3), amp=0)
    else:
        d = min(1.0, (cyc - 2.15) / 0.6)
        p.line(bx - 26, FLOOR - 19, bx - 2, FLOOR - 19 + 10 * d, w=5, color=(0.7, 0.5, 0.3), amp=0)
        p.line(bx + 26, FLOOR - 19, bx + 2, FLOOR - 19 + 10 * d, w=5, color=(0.7, 0.5, 0.3), amp=0)
    if kick and kk > 0.6:                                   # Bewegungsbogen des Fußes
        p.arc(fx - 34, hip_y + 6, 40, -0.5, 0.5 * kk, w=1.4, color=GRAY)
    if _in(cyc, 2.0, 3.6):
        p.text("KIAI!", fx - 10, hy - 34, 22, align="center", color=RED, hand=True)
    if _in(cyc, 2.2, 3.4):
        p.text("krach!", bx, FLOOR - 40, 14, align="center", color=GRAY, hand=True, upper=False)
    return "Karate: Brett statt Bug"

# ---------------------------------------------------------------- Unordnung und Wildwuchs
def _grow(a, t):
    """0…1: wächst mit der Zeit, die der Agent schon untätig ist (unbekannt: mittel)."""
    forced = FORCE.get("grow")
    if forced is not None:
        return forced
    if a.phase != "idle":
        return 0.0
    ifor = a.idle_for
    if ifor is None:
        return 0.3
    return max(0.0, min(1.0, (ifor - FINALE_S) / 240.0))

def _leaf(p, x, y, ang, r, color=GREEN):
    ex, ey = x + r * math.cos(ang), y + r * math.sin(ang)
    mx, my = (x + ex) / 2, (y + ey) / 2
    nx, ny = -math.sin(ang) * r * 0.35, math.cos(ang) * r * 0.35
    p.poly([(x, y), (mx + nx, my + ny), (ex, ey), (mx - nx, my - ny)], closed=True, w=1.2, color=color, fill=(0.85, 0.95, 0.8), amp=0)

def _web(p, x, y, dx, dy, r, t):
    """Spinnennetz in einer Ecke; (dx, dy) = ±1 Richtung ins Bild hinein. r skaliert Fäden und Bogen."""
    n = 5
    r = max(6.0, r)
    pts = []
    for i in range(n):
        a = (math.pi / 2) * i / (n - 1)
        pts.append((x + dx * r * math.cos(a), y + dy * r * math.sin(a)))
        p.line(x, y, *pts[-1], w=1.0, color=GRAY, amp=0)
    for rr in (0.35, 0.65, 1.0):
        prev = None
        for i in range(n):
            a = (math.pi / 2) * i / (n - 1)
            q = (x + dx * r * rr * math.cos(a), y + dy * r * rr * math.sin(a) * 1.0)
            if prev:
                p.curve([prev, ((prev[0] + q[0]) / 2 - dx * 2, (prev[1] + q[1]) / 2 - dy * 2), q], w=0.9, color=GRAY)
            prev = q


def _vine(p, x0, y0, x1, y1, t, n, amp=9, seed=0, leaf=1.0):
    pts = []
    for i in range(n + 1):
        k = i / n
        pts.append((x0 + (x1 - x0) * k + amp * 0.4 * math.sin(k * 9 + seed), y0 + (y1 - y0) * k + amp * math.sin(k * 7 + seed * 2)))
    p.curve(pts, w=2.0, color=GREEN)
    for i in range(1, n + 1, 2):
        x, y = pts[i]
        _leaf(p, x, y, -1.0 - 0.6 * math.sin(i + t * 0.8 * 0 + seed), 9 * leaf)
        _leaf(p, x, y, 2.4 + 0.5 * math.cos(i + seed), 8 * leaf)

def overgrowth(p, a, t, c):
    """Chaos auf Tisch und Boden (immer ein bisschen, wächst bei Leerlauf), Spinnweben und Pflanzen (nur bei Leerlauf)."""
    g = _grow(a, t)
    mess = max(0.35, g)
    dk, fl = c.desk_y, c.floor
    # Tisch: Tassen, Papiere, Pizzakarton
    items = []
    if mess > 0.05:
        _mug(p, 338, dk)
    if mess > 0.3:
        p.rect(356, dk - 6, 34, 6, lw=1.4, fill=PAPER)
        p.rect(360, dk - 11, 28, 5, lw=1.4, fill=PAPER)
    if mess > 0.45:
        p.rect(396, dk - 8, 38, 8, lw=1.6, fill=(0.92, 0.82, 0.62))
        p.line(396, dk - 8, 410, dk - 14, w=1.6, amp=0)
    if mess > 0.65:
        _mug(p, 316, dk)
        _mug(p, 408, dk - 8)
    if mess > 0.85:
        p.rect(326, dk - 18, 14, 18, lw=1.4, fill=(0.8, 0.9, 0.8))
        p.circle(366, dk - 17, 5, w=1.2, fill=PAPER)
    # Boden: Papierknäuel, Socke, Flaschen
    if mess > 0.05:
        p.circle(48, fl - 5, 5, w=1.4, fill=PAPER)
    if mess > 0.4:
        p.circle(84, fl - 4, 4, w=1.4, fill=PAPER)
        p.poly([(110, fl - 2), (122, fl - 2), (124, fl - 9), (118, fl - 11), (112, fl - 7)], closed=True, w=1.4, fill=PAPER, amp=0)
    if mess > 0.7:
        p.rect(402, fl - 20, 8, 20, lw=1.4, fill=(0.8, 0.9, 0.8))
        p.circle(428, fl - 5, 5, w=1.4, fill=PAPER)
        p.circle(36, fl - 4, 4, w=1.4, fill=PAPER)
    if a.phase != "idle" and g <= 0:
        return
    # Spinnweben (erst klein, wachsen mit der Unordnung)
    if g > 0.12:
        r = 14 + 46 * g
        _web(p, 20, 50, 1, 1, r, t)
        if g > 0.5:
            _web(p, 438, 50, -1, 1, r * 0.8, t)
        if g > 0.7:
            _web(p, 218, dk, 1, -1, 28, t)
    # Pflanzen (frühe Stufe: kurze Ranke und kleine Blätter)
    if g > 0.18:
        p.poly([(24, fl), (48, fl), (45, fl - 20), (27, fl - 20)], closed=True, w=1.8, fill=PAPER, amp=0)
        for i, ang in enumerate((-1.9, -1.4, -1.0)):
            L = 24 + 90 * g * (0.7 + 0.3 * i)
            _vine(p, 36, fl - 20, 36 + 20 * math.cos(ang) * L / 24, fl - 20 + L * math.sin(ang), t, max(2, int(L / 16)), amp=5, seed=i, leaf=min(1.0, L / 60))
    if g > 0.35:
        n = int(4 + 18 * g)
        _vine(p, 50, fl - 3, 50 + 380 * min(1, g * 1.1), fl - 3, t, n, amp=6, seed=3, leaf=min(1.0, g * 2.2))
    if g > 0.55:
        _vine(p, 426, fl, 428, dk - 4, t, 6, amp=4, seed=5)
    if g > 0.75:
        _vine(p, 428, dk, 296, dk - 4, t, 10, amp=4, seed=6)
        _vine(p, 160, fl - 3, 160, fl - 48, t, 5, amp=3, seed=8)
    if g > 0.9:
        _vine(p, 24, 52, 24 + 160 * (g - 0.9) * 10, 52 + 8, t, 8, amp=4, seed=9)

# ---------------------------------------------------------------- Memes
def idle_67(p, a, t, c):
    """Meme „6-7": zwei flache Hände wippen im Takt, dazu der Sprechchor."""
    u, _ = _slot(a, t)
    beat = math.sin(t * 3.2)
    vx, walking, flip = _arrive(u) if u < 3 else (140, False, True)

    def hf(sh):
        return ((sh[0] + 10 - 7 * beat, sh[1] - 8), (sh[0] + 12 + 7 * beat, sh[1] + 2))

    f, sh = _actor(p, vx, t, flip=flip, walking=walking, color=BLUE, hands=hf, eyes="dots")
    hd = _host(p, c, lean=-2, look=-8, eyes="dots",
               hands=((c.cx + 24, c.hip[1] - 26 + 16 * beat), (c.cx + 32, c.hip[1] - 4)))
    p.text("6-7", 218 + 8 * beat, 118, 46, align="center", bold=True, color=BLUE)
    if _in(u, 2, 6):
        S.say_at(p, f["head"], quips.line("67", a.key, int(t / IDLE_SLOT_S)), w=250, h=70, size=18, dx=40, color=BLUE)
    elif _in(u, 6, 10.4):
        S.say_at(p, hd, quips.line("67_reply", a.key, int(t / IDLE_SLOT_S)), w=270, h=74, size=17, dx=40)
    return "Meme: 6-7"


def idle_thisisfine(p, a, t, c):
    """Meme „This is fine": rundherum brennt es, der Agent trinkt gemütlich Kaffee."""
    for fx, h in ((72, 42), (150, 56), (252, 44), (332, 62), (408, 38)):
        p.flame(fx, FLOOR - 6, t + fx * 0.01, h=h)
        p.smoke(fx + 4, FLOOR - 6 - h, t + fx * 0.02, n=2, scale=0.7)
    mug = (c.cx + 46, c.desk_y - 2)
    hd = _host(p, c, lean=2, look=6, eyes="dots",
               hands=((mug[0] - 6, mug[1] - 20), (mug[0] - 4, mug[1] - 8)))
    _mug(p, mug[0], mug[1], steam_t=t)
    S.say_at(p, hd, quips.line("fine", a.key, int(t / IDLE_SLOT_S)), w=260, h=70, size=17, dx=40)
    return "Meme: This is fine"


def idle_distracted(p, a, t, c):
    """Meme „Distracted Boyfriend": der Agent schaut der vorbeigehenden Agentin nach."""
    u, _ = _slot(a, t)
    gx, bx0 = 96, 186
    ox = 300 + 22 * math.sin(t * 0.8)
    watching = _in(u, 1.5, 11)
    fg, _ = _actor(p, gx, t, s=0.92, flip=False, color=PINK,
                   hands=lambda sh: ((sh[0] + 8, sh[1] + 22), (sh[0] + 2, sh[1] + 24)))
    p.text("!", fg["head"][0] + 16, fg["head"][1] - 20, 22, color=RED, hand=True)
    hip_y = FLOOR - 2 * LEG * 0.92 + 0.5
    shb = Pen.anchors(bx0, hip_y, s=0.92, look=30)["sh"]
    fb = p.figure(bx0, hip_y, s=0.92, look=30 if watching else 0, eyes="dots",
                  hands=((shb[0] + 8, shb[1] + 26), (shb[0] + 2, shb[1] + 28)),
                  feet=((bx0 - 8, FLOOR), (bx0 + 8, FLOOR)))
    fo, _ = _actor(p, ox, t, s=0.92, flip=False, color=PINK, walking=True,
                   hands=lambda sh: ((sh[0] + 12, sh[1] + 24), (sh[0] + 4, sh[1] + 26)), eyes="dots")
    for i in range(3):
        _heart(p, fo["head"][0] + 18, fo["head"][1] - 20 - i * 14, 4)
    if watching:
        S.say_at(p, fb["head"], quips.line("distracted", a.key, int(t / IDLE_SLOT_S)), w=280, h=74, size=17, dx=40)
    return "Meme: Distracted Developer"


# ---------------------------------------------------------------- TikTok-Challenges
def _phone(p, x, y, t, live=True):
    """Handy auf Stativ, filmt die Szene (TikTok)."""
    p.rect(x - 12, y - 22, 24, 40, lw=1.8, fill=PAPER)
    p.text("REC", x, y - 8, 8, align="center", color=RED if live else GRAY, bold=True, upper=False)
    if live:
        p.circle(x + 8, y - 18, 2, w=1.0, color=RED, fill=RED)
    for dx in (-8, 8):
        p.line(x + dx, y + 18, x + 2 * dx, y + 44, w=1.6, amp=0)
    p.line(x - 6, y + 30, x + 6, y + 30, w=1.2, amp=0)


def idle_planking(p, a, t, c):
    """TikTok-Challenge: Planking auf zwei Hockern, der Agent zählt mit."""
    u, _ = _slot(a, t)
    plank = _in(u, 1.8, 9.5)
    rise = min(1.0, u / 1.8) if not plank else 1.0
    y = FLOOR - 46 - 40 * rise
    for hx in (78, 250):
        p.rect(hx - 20, FLOOR - 30, 40, 6, lw=1.8, fill=PAPER)
        for sx in (-13, 13):
            p.line(hx + sx, FLOOR - 24, hx + sx, FLOOR, w=2.0, amp=0)
    fx = 164
    p.line(fx - 84, y, fx + 70, y, w=3.2, amp=0)                    # steifer Körper
    p.circle(fx + 84, y - 2, 12, w=2.6, fill=PAPER)
    p.circle(fx + 88, y - 4, 1.6, w=1.2, fill=INK)
    p.line(fx - 84, y, fx - 100, y + 11, w=2.2, amp=0)              # steife Füße
    p.line(fx - 84, y, fx - 100, y - 5, w=2.2, amp=0)
    p.line(fx + 36, y, fx + 50, y - 18, w=2.2, amp=0)               # steife Arme
    p.line(fx + 36, y, fx + 50, y + 16, w=2.2, amp=0)
    _phone(p, 40, 300, t, live=plank)
    if plank:
        p.text("1… 2… 3…", 380, 120, 18, align="center", color=GRAY, hand=True)
        S.say_at(p, _host(p, c, lean=-4, look=-12, eyes="dots"), "Hält! Weiter so!", w=250, h=70, size=17, dx=40)
    else:
        _host(p, c, lean=-4, look=-12)
    return "TikTok: Planking auf zwei Hockern"


def idle_mannequin(p, a, t, c):
    """TikTok-Challenge: Mannequin – alle erstarren mitten in der Bewegung, das Handy filmt."""
    u, _ = _slot(a, t)
    frozen = _in(u, 2.4, 9.6)
    tt = 2.4 if frozen else t
    vx, walking, flip = _arrive(tt) if tt < 3 else (150, False, True)
    f, _ = _actor(p, vx, tt, flip=flip, walking=walking and not frozen, color=BLUE, eyes="dots",
                  hands=lambda sh: ((sh[0] + 26, sh[1] - 20), (sh[0] + 10, sh[1] + 16)))
    _host(p, c, lean=-4, look=-10, eyes="dots",
          hands=((c.cx + 26, c.hip[1] - 30), (c.cx + 30, c.hip[1] - 4)))
    _phone(p, 60, 300, t, live=True)
    if frozen:
        p.text("FREEZE", 330, 130, 26, align="center", bold=True, color=RED)
    else:
        p.text("3… 2… 1…", 330, 130, 18, align="center", color=GRAY, hand=True)
    return "TikTok: Mannequin Challenge"


def idle_icebucket(p, a, t, c):
    """TikTok-Challenge: Ice Bucket – der Eimer kippt, Wasser und Eis prasseln herunter."""
    u, _ = _slot(a, t)
    tip = _in(u, 2.6, 3.4)
    splash = _in(u, 3.4, 5.2)
    fx = 150
    hip_y = _stand_hip() + 6
    k = _ease(min(1.0, max(0.0, (u - 2.6) / 0.8)))
    sh = Pen.anchors(fx, hip_y)["sh"]
    ex, ey = sh[0] + 30, sh[1] - 34 + 18 * k
    f = p.figure(fx, hip_y, eyes="x" if splash else "dots", lean=-6 + 10 * k,
                 hands=((ex - 8, ey + 8), (ex + 10, ey + 6)),
                 feet=((fx - 12, FLOOR), (fx + 12, FLOOR)))
    ang = -0.3 + 2.4 * k
    ex2, ey2 = ex + 26 * math.cos(ang), ey + 26 * math.sin(ang)
    p.poly([(ex, ey - 18), (ex2, ey2 - 18), (ex2, ey2 + 18), (ex, ey + 18)], closed=True, w=2.4,
           fill=(0.8, 0.86, 0.95), amp=0.4)
    if splash:
        for i in range(16):
            kk = (t * 1.6 + i / 16) % 1
            wx = ex + math.sin(i * 2.4) * 26 * kk
            wy = ey + 26 - 120 * kk
            p.line(wx, wy, wx + 2, wy + 8, w=1.4, color=BLUE, amp=0)
            if i % 4 == 0:
                p.circle(wx, wy + 10, 3.4, w=1.3, color=BLUE, fill=(0.88, 0.94, 1.0))
        p.text("PLATSCH!", fx + 30, ey - 40, 20, align="center", color=BLUE, hand=True)
    _host(p, c, lean=-4, look=-12, eyes="dots" if splash else None)
    return "TikTok: Ice Bucket Challenge"


NEW_IDLE = [idle_guest, idle_postman, idle_fly, idle_desksleep, idle_paperball, idle_spin, idle_stretch, idle_phone, idle_spider, idle_trek, idle_zombies, idle_starwars, idle_lotr, idle_coffeeduo, idle_flirt, idle_kids, idle_protest, idle_cosplay, idle_taichi, idle_karate, idle_67, idle_thisisfine, idle_distracted, idle_planking, idle_mannequin, idle_icebucket]

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

def _slot_kind(key: str, slot: int) -> int:
    """Welche Umgebungsfigur läuft in diesem Zeitfenster? 6, 7 = ruhiger Slot. Je Lauf anders verteilt."""
    return int(S._hash01(kh(key), slot, 99, RUN_SEED) * 8)

def ambient(p: Pen, key: str, t: float):
    """Gelegentlich geht etwas durchs Bild (Katze, Vogel, Ballon, Schnecke) – in jedem Panel zu anderer Zeit."""
    slot = int(t / AMBIENT_SLOT_S)
    kind = _slot_kind(key, slot)
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
