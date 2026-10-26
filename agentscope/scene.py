"""Die xkcd-Szene: jeder Agent ist ein Comic-Panel.

Metaphern (siehe docs/SPEC.md):
- Hauptfigur am Schreibtisch = Hauptagent; Pose zeigt die Phase
  (denken, tippen/streamen, Werkzeug, quetschen, erneut versuchen, Fehler, schlafen).
- Werkzeuge als Requisiten: bash = Hammer auf Kiste, read = Buch, edit/write = Bleistift,
  subagent = Megafon, Rest = Lupe.
- Glas "CONTEXT" = Kontextfüllung; Presse darüber = Kompaktierung ("SQUISH!").
- Tacho = Tokens pro Sekunde, fliegende Münzen = Token-Strom, Zähler = Summe.
- Kurve "CONTEXT OVER TIME" mit Sägezahn = Kompaktierungen im Verlauf.
- Kleine Figuren unten = Subagents (arbeiten / Haken / umgefallen) + Fortschrittsbalken.
- Strichliste "OOPS" + rote Notiz = Fehler. Notizblock rechts = letzte Ereignisse.
"""

from __future__ import annotations

import math
import time
from collections import deque

import cairo

from . import dance
from .model import Agent
from .sketch import LEG, BLUE, GRAY, INK, LIGHT, PAPER, RED, Pen

PW, PH = 1000.0, 560.0  # virtuelles Panel
FLOOR = 376.0

ALT_TEXTS = [
    "The context window is like a suitcase: the more you squish, the more you forget where you packed your socks.",
    "Subagents are just interns with infinite patience and zero memory.",
    "Every token you see here was hand-crafted by a tiny statistical artisan.",
    "If the error tally reaches five, it's not a bug, it's a bundle.",
    "Compaction: the art of summarizing three hours of work as 'did stuff, mostly fine'.",
    "Retrying is just optimism with exponential backoff.",
]

PHASE_WORDS = {
    "idle": "zzz… waiting for you",
    "thinking": "thinking very hard",
    "streaming": "typing like crazy",
    "tool": "using tools",
    "compacting": "squishing the context",
    "retrying": "knocking on the API again",
    "error": "something broke",
}


def fmt_tok(n) -> str:
    if n is None:
        return "?"
    n = float(n)
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k" if n >= 1e4 else f"{n / 1e3:.1f}k"
    return f"{int(n)}"


class History:
    """Kontextverlauf je Agent (für die Kurve), eine Probe pro Sekunde."""

    def __init__(self, keep_s: float = 600):
        self.keep = keep_s
        self.data: dict[str, deque] = {}
        self.marks: dict[str, deque] = {}
        self._compacts: dict[str, int] = {}
        self._needle: dict[str, tuple[float, float]] = {}

    def needle(self, key: str, target: float, t: float, tau: float = 0.6) -> float:
        """Geglätteter Tachowert (exponentiell, Zeitkonstante tau): die Nadel schwingt statt zu springen."""
        if key not in self._needle:                # erster Wert: sofort anzeigen (Schnappschuss, Start)
            self._needle[key] = (target, t)
            return target
        v, t0 = self._needle[key]
        dt = max(0.0, min(1.0, t - t0))
        v += (target - v) * (1 - math.exp(-dt / tau))
        self._needle[key] = (v, t)
        return v

    def sample(self, agents: list[Agent], now: float):
        for a in agents:
            d = self.data.setdefault(a.key, deque())
            m = self.marks.setdefault(a.key, deque())
            prev = self._compacts.get(a.key)
            if prev is not None and a.compact_count > prev:
                m.append(now)
            self._compacts[a.key] = a.compact_count
            if a.ctx_tokens is not None and (not d or now - d[-1][0] >= 1.0):
                d.append((now, a.ctx_tokens))
            while d and now - d[0][0] > self.keep:
                d.popleft()
            while m and now - m[0] > self.keep:
                m.popleft()


# ======================================================================== Layout
def layout(n: int, W: float, H: float, top: float, bottom: float, gap: float = 18):
    """Wählt Spalten/Zeilen so, dass das virtuelle Panel möglichst groß wird."""
    best = None
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        cw = (W - gap * (cols + 1)) / cols
        ch = (H - top - bottom - gap * (rows - 1)) / rows
        s = min(cw / PW, ch / PH)
        if best is None or s > best[0] + 1e-6:
            best = (s, cols, rows, cw, ch)
    s, cols, rows, cw, ch = best
    cells = []
    for i in range(n):
        r, c = divmod(i, cols)
        x = gap + c * (cw + gap) + (cw - PW * s) / 2
        y = top + r * (ch + gap) + (ch - PH * s) / 2
        cells.append((x, y, s))
    return cells


# ======================================================================== Gesamtbild
def render(cr: cairo.Context, W: float, H: float, agents: list[Agent], t: float, hist: History | None = None,
           clock: str | None = None, max_panels: int = 4):
    boil = int(t * 4)
    p = Pen(cr, boil=boil)
    cr.set_source_rgb(*PAPER)
    cr.paint()

    shown = agents[:max_panels]
    # Kopfzeile
    tot = sum(a.tok_total for a in agents)
    subs = sum(len(r.get("agents") or []) for a in agents for r in a.runs if not r.get("finished")) + sum(len(a.children) for a in agents if not a.runs)
    errs = sum(a.errors for a in agents)
    rate = sum(a.rate for a in agents)
    hs = max(0.6, min(1.3, W / 1440))
    p.text("What my agents are doing right now", W / 2, 46 * hs, 30 * hs, align="center", bold=True)
    sub = f"{len(agents)} agent{'s' if len(agents) != 1 else ''} · {subs} subagents busy · {fmt_tok(tot)} tokens eaten · {rate:.0f} tok/s · {errs} oops"
    p.text(sub, W / 2, 76 * hs, 15 * hs, align="center", color=GRAY)
    p.text(clock or time.strftime("%H:%M"), W - 24, 40 * hs, 22 * hs, align="right")
    if len(agents) > max_panels:
        p.text(f"+{len(agents) - max_panels} more not shown", 24, 40 * hs, 14 * hs, color=GRAY)

    top, bottom = 96 * hs, 44 * hs
    if not shown:
        render_empty(p, W, H, t, top, bottom)
    else:
        for a, (x, y, s) in zip(shown, layout(len(shown), W, H, top, bottom)):
            cr.save()
            cr.translate(x, y)
            cr.scale(s, s)
            render_panel(p, a, t, hist)
            cr.restore()

    alt = ALT_TEXTS[int(t / 20) % len(ALT_TEXTS)]
    p.text(alt, W / 2, H - 16 * hs, 13 * hs, align="center", color=GRAY, upper=False, jitter=0.3, maxw=W - 60)


def render_empty(p: Pen, W, H, t, top, bottom):
    cr = p.cr
    s = min(W / PW, (H - top - bottom) / PH) * 0.9
    cr.save()
    cr.translate((W - PW * s) / 2, top + (H - top - bottom - PH * s) / 2)
    cr.scale(s, s)
    # Hängematte zwischen zwei Bäumen
    p.line(80, FLOOR + 60, 920, FLOOR + 60, w=2)
    for tx in (260, 740):
        p.line(tx, FLOOR + 60, tx, 150, w=3)
        p.circle(tx, 130, 55, w=2.2)
    sag = 6 * math.sin(t * 0.8)
    p.curve([(260, 220), (380, 300 + sag), (500, 318 + sag), (620, 300 + sag), (740, 220)], w=2.4)
    p.figure(500, 300 + sag, 1.0, la=(150, 200), ra=(-150, -200), ll=(80, 95), rl=(75, 90), lean=-80, head_dy=0)
    for i in range(3):
        k = (t * 0.5 + i / 3) % 1
        p.text("z", 420 - k * 40 + i * 6, 250 - k * 120, 16 + k * 22, color=GRAY, hand=True)
    p.text("No agents are running.", PW / 2, 470, 26, align="center", bold=True)
    p.text("Start pi and come back – this panel will fill up.", PW / 2, 506, 17, align="center", color=GRAY)
    cr.restore()


# ======================================================================== Panel
def render_panel(p: Pen, a: Agent, t: float, hist: History | None):
    cr = p.cr
    p.rect(0, 0, PW, PH, lw=3)
    # Beschriftungskasten wie xkcd-Caption
    title = p.fit(a.title, 22, 420)
    tw = p.text_width(title, 22, bold=True)
    p.rect(-1, -1, tw + 36, 40, lw=2.4, fill=PAPER)
    p.text(title, 16, 28, 22, bold=True)
    phase_txt = PHASE_WORDS.get(a.phase, a.phase)
    p.text(f"{a.model or '?'} · turn {a.turn} · {phase_txt}", tw + 52, 28, 15, color=GRAY, maxw=820 - tw - 52)
    if a.source == "log":
        p.text("(from session log)", 830, 28, 12, color=GRAY, align="right")

    draw_actor(p, a, t)
    draw_context_jar(p, a, t, 470, 140, 92, 190)
    draw_gauge(p, a, t, 690, 140, hist=hist)
    draw_chart(p, a, t, hist, 590, 250, 230, 130)
    draw_notebook(p, a, t, 845, 52, 145, 345)
    draw_bottom(p, a, t, 0, 404, PW, PH - 404)


# ------------------------------------------------------------------------ Hauptfigur
def tool_kind(name: str) -> str:
    if name == "bash":
        return "bash"
    if name == "read":
        return "read"
    if name in ("edit", "write"):
        return "write"
    if name == "subagent":
        return "subagent"
    return "other"


# Möbelmaße (virtuelle Einheiten). Abgeleitet aus der Figur: Unterschenkel = LEG, also sitzt die
# Hüfte eine Unterschenkellänge über dem Boden; der Tisch steht knapp unter Schulterhöhe.
SEAT_H = LEG + 2                 # Sitzfläche über dem Boden
DESK_H = 62                      # Tischplatte über dem Boden
ACTOR_X = 190.0                  # Hüfte der sitzenden Figur


def seated(p: Pen, hip, *, hands=(None, None), lean=10.0, look=0.0, eyes=None, la=(-60, -40), ra=(-60, -40), color=INK):
    """Figur sitzt auf dem Stuhl, schaut nach rechts zum Tisch: Oberschenkel waagerecht, Füße am Boden."""
    hx, hy = hip
    feet = ((hx + LEG + 3, FLOOR), (hx + LEG - 5, FLOOR))
    return p.figure(hx, hy, la=la, ra=ra, lean=lean, look=look, flip=True, hands=hands, feet=feet, eyes=eyes, color=color)


def seated_at(hip, lean=10.0, look=0.0):
    return Pen.anchors(*hip, lean=lean, flip=True, look=look)


def standing_at(x, lift=0.0, flip=False, lean=0.0, crouch=0.0):
    return Pen.anchors(x, FLOOR - lift - 2 * LEG + 0.5 + crouch, lean=lean, flip=flip)


def standing(p: Pen, x, *, lift=0.0, flip=False, crouch=0.0, stance=9.0, **kw):
    """Figur steht (Füße am Boden, bei lift>0 in der Luft). Hüfte liegt eine Beinlänge über den Füßen,
    crouch senkt sie (Knie beugen sich, Füße bleiben stehen)."""
    foot_y = FLOOR - lift
    hy = foot_y - 2 * LEG + 0.5 + crouch
    feet = ((x - stance, foot_y), (x + stance, foot_y))
    return p.figure(x, hy, flip=flip, feet=feet, **kw)


def think_at(p: Pen, head, text, *, w=330, h=170, size=19, max_lines=3):
    """Gedankenblase über/links vom Kopf, vollständig im Bereich der Figur (x 18…440, y 46…)."""
    cx = min(max(head[0] + 10, 18 + w / 2), 440 - w / 2)
    cy = max(46 + h / 2, head[1] - 40 - h / 2)
    return p.think(text, cx, cy, w, h, (head[0] - 4, head[1] - 22), size=size, max_lines=max_lines)


def say_at(p: Pen, head, text, *, w=260, h=80, size=19, color=INK, bold=False, dx=40):
    cx = min(max(head[0] + dx, 18 + w / 2), 440 - w / 2)
    cy = max(46 + h / 2, head[1] - 60 - h / 2)
    return p.say(text, cx, cy, w, h, (head[0] + 4, head[1] - 20), size=size, color=color, bold=bold)


def draw_actor(p: Pen, a: Agent, t: float):
    cx, floor = ACTOR_X, FLOOR
    desk_y = floor - DESK_H
    seat_y = floor - SEAT_H
    hip = (cx, seat_y - 3)                       # Gesäß liegt auf der Sitzfläche
    lap_x = cx + 70                              # Laptop (Mitte der Unterkante)
    keys = (lap_x - 22, desk_y - 3)              # Tastatur vorne auf dem Laptop
    ph = a.phase
    tool = a.tools[0] if a.tools else None
    kind = tool_kind(tool["name"]) if tool else None
    if ph == "tool" and not tool:
        ph = "thinking"

    if ph != "retrying":
        p.desk(cx + 28, desk_y, 220, floor)
        p.chair(cx - 6, seat_y, floor, facing=1)
    p.line(20, floor, 440, floor, w=1.6, color=GRAY)

    sw = math.sin(t * 7)
    glow = ph in ("thinking", "streaming", "tool")
    if ph not in ("retrying",):
        p.laptop(lap_x, desk_y, 1.0, glow=glow)

    if ph == "idle":
        # zurückgelehnt, Hände im Schoß, Kopf zur Seite gekippt
        h = seated(p, hip, lean=-14, look=-25, hands=((cx + 22, hip[1] - 6), (cx + 28, hip[1] - 4)))
        for i in range(3):
            k = (t * 0.45 + i / 3) % 1
            p.text("z", h["head"][0] - 20 - k * 30, h["head"][1] - 30 - k * 110, 16 + k * 22, color=GRAY, hand=True)
        caption(p, "waiting for your next prompt", cx + 60)
    elif ph == "thinking":
        # zurückgelehnt, Hand am Kinn
        hd = seated_at(hip, lean=-6)["head"]
        h = seated(p, hip, lean=-6, hands=((hd[0] + 9, hd[1] + 15), (cx + 26, hip[1] - 5)))
        words = (a.prompt or "hmm…").split()
        k = int(t * 0.5) * 7 % max(1, len(words))
        frag = " ".join(words[k:k + 9]) or "…"
        think_at(p, h["head"], frag + " " + "." * (1 + int(t * 2) % 3))
        caption(p, "thinking it over", cx + 60)
    elif ph == "streaming":
        hl, hr, lean, look = typing_hands(t, a.rate, keys)
        seated(p, hip, lean=lean, look=look, hands=(hl, hr))
        caption(p, "streaming tokens", cx + 60)
    elif ph == "tool":
        draw_tool_pose(p, kind, tool, hip, cx, desk_y, floor, t, keys)
        caption(p, f"{tool['name']}: {tool['label']}", cx + 60)
        if len(a.tools) > 1:
            p.text(f"+{len(a.tools) - 1} more tools running", cx + 300, 80, 13, color=GRAY, align="center")
    elif ph == "compacting":
        # zeigt aufgeregt aufs Glas (rechts oben)
        shx, shy = seated_at(hip, lean=4 + 3 * sw)["sh"]
        h = seated(p, hip, lean=4 + 3 * sw, hands=((shx + 46, shy - 14 + 3 * sw), (cx + 26, hip[1] - 5)))
        say_at(p, h["head"], "hold on, packing…", dx=60)
        caption(p, "summarizing old context", cx + 60)
    elif ph == "retrying":
        # steht an der Tür "API" und klopft
        dx = 320
        p.rect(dx, floor - 190, 84, 190, lw=2.6, fill=PAPER)
        p.circle(dx + 14, floor - 95, 4, w=2)
        p.text("API", dx + 42, floor - 158, 22, align="center", bold=True)
        knock = abs(math.sin(t * 6))
        fx = dx - 50
        shx, shy = standing_at(fx, flip=True)["sh"]
        h = standing(p, fx, flip=True, hands=((dx - 2 - 10 * (1 - knock), shy - 6), (fx + 4, shy + 40)))
        if knock > 0.85:
            p.text("knock", dx - 14, floor - 205, 16, color=GRAY, hand=True)
        r = a.retry or {}
        say_at(p, h["head"], f"try {r.get('attempt', '?')} of {r.get('max', '?')}…", dx=-120, w=220)
        caption(p, r.get("error") or "provider said no", 220)
    elif ph == "error":
        p.flame(lap_x + 8, desk_y - 30, t)
        p.smoke(lap_x + 12, desk_y - 60, t)
        jump = abs(math.sin(t * 5)) * 12
        h = standing(p, cx - 60, lift=jump, flip=False, la=(160 + 15 * sw, 200), ra=(-160 - 15 * sw, -200), eyes="dots")
        say_at(p, h["head"], "AAAAA!", w=170, h=70, size=24, color=RED, bold=True, dx=-10)
        caption(p, a.last_error or "error", cx + 60, color=RED)
    else:
        seated(p, hip, lean=4, hands=((cx + 24, hip[1] - 6), (cx + 30, hip[1] - 4)))

    # Token-Münzen fliegen vom Laptop zum Tacho
    if a.rate > 0 and ph in ("streaming", "tool", "thinking"):
        n = int(min(10, 1 + a.rate / 10))
        for i in range(n):
            k = (t * (0.35 + a.rate / 300) + i / n) % 1
            x0, y0 = lap_x + 10, desk_y - 30
            x1, y1 = 690, 200
            x = x0 + (x1 - x0) * k
            y = y0 + (y1 - y0) * k - math.sin(k * math.pi) * 120
            p.coin(x, y, 7)


def caption(p: Pen, text: str, x: float, color=INK):
    p.text(text, x, FLOOR + 20, 14, align="center", color=color, maxw=400)


def _hash01(*xs) -> float:
    """Deterministischer Pseudo-Zufall 0…1 (für Anschlag-Rhythmus ohne Flimmern)."""
    h = 2166136261
    for x in xs:
        h = ((h ^ (int(x) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def typing_hands(t: float, rate: float, keys) -> tuple:
    """Tippen wie ein Mensch: einzelne Anschläge (schnell runter, langsam hoch), die Hände wechseln sich ab,
    wandern über die Tastatur, kurze Denkpausen nach „Wörtern“ und gelegentlich ein beherztes Enter.

    Gibt (linke Hand, rechte Hand, lean, look) zurück; keys = linke vordere Tastaturecke."""
    speed = 4.0 + min(10.0, rate / 8)            # Anschläge/s, schneller bei höherer Tokenrate
    n = int(t * speed)
    ph = t * speed - n                            # 0…1 innerhalb des Anschlags
    word = n // 6                                 # ~6 Anschläge pro Wort
    pause = _hash01(word, 7) < 0.25 and n % 6 == 5
    enter = _hash01(word, 11) < 0.12 and n % 6 == 5
    kx, ky = keys
    base_l, base_r = (kx + 2, ky - 2), (kx + 14, ky - 2)
    hand_r = n % 2 == 1 or _hash01(n, 3) < 0.25   # leicht ungleich verteilt
    off = 6 * _hash01(n, 5) - 3                   # Taste wandert über die Breite
    # Hub: schnell runter (0…0.3), langsamer hoch, Ruhe dazwischen
    if ph < 0.3:
        lift = 1 - ph / 0.3
    else:
        lift = min(1.0, (ph - 0.3) / 0.5)
    lift = 7.0 * lift
    rest = 3.0
    l = (base_l[0] + off * 0.5, base_l[1] - rest)
    r = (base_r[0] + off * 0.5, base_r[1] - rest)
    if pause:                                     # beide Hände schweben, kurz nachdenken
        l, r = (l[0] - 2, l[1] - 3), (r[0] - 2, r[1] - 3)
    elif enter:                                   # rechte Hand holt aus und haut auf Enter
        up = 1 - ph
        r = (base_r[0] + 10 + 4 * up, base_r[1] - 2 - 22 * up * up)
    elif hand_r:
        r = (r[0] + off, base_r[1] - lift)
    else:
        l = (l[0] + off, base_l[1] - lift)
    lean = 12 + 1.2 * math.sin(t * 1.3)           # leichtes Wippen
    look = 8 + (3 if pause else 0) + 2 * math.sin(t * 0.7)
    return l, r, lean, look


HAMMER_PERIOD = 1.3     # s pro Schlag
HAMMER_LEN = 34.0       # Stiel (sketch.Pen.hammer)


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def hammer_swing(t: float) -> dict:
    """Schlagphasen über eine Periode: ausholen (langsam), oben halten, Schlag (schnell, beschleunigt),
    Rückprall, Pause. swing = 1 oben/hinten, 0 auf der Kiste; cock = Handgelenk angewinkelt (0…1)."""
    u = (t / HAMMER_PERIOD) % 1.0
    impact = 0.0
    if u < 0.42:                                  # ausholen
        k = _ease(u / 0.42)
        swing, cock, aim = k, k, k
    elif u < 0.52:                                # oben, kurz halten
        swing, cock, aim = 1.0, 1.0, 1.0
    elif u < 0.62:                                # Schlag: beschleunigt (k²), Handgelenk schnappt spät durch
        k = (u - 0.52) / 0.10
        swing, cock, aim = 1 - k * k, 1 - k ** 3, 1 - k
    elif u < 0.74:                                # Treffer + Rückprall
        k = (u - 0.62) / 0.12
        swing, cock, aim = 0.06 * math.sin(k * math.pi), 0.0, 0.0
        impact = 1 - k
    else:                                         # Pause, Hammer liegt auf
        swing, cock, aim = 0.0, 0.0, 0.0
    lean = -6 * swing + 14 * (1 - swing)          # beim Ausholen zurück, beim Schlag nach vorn
    crouch = 8 * (1 - swing) * (1 - swing)        # Knie geben beim Schlag nach
    return {"u": u, "swing": swing, "cock": cock, "aim": aim, "lean": lean, "crouch": crouch, "impact": impact}


def hammer_grip(sh, target, sp: dict):
    """Hand und Stielwinkel (sketch.hammer-Konvention: 0 = Stiel nach oben) für eine Schwungphase.

    Arm-Winkel th (0 = unten, + = rechts/hinten): von der Kiste (vorn unten) über den Kopf nach hinten
    vorn hoch über den Kopf nach hinten (th_up = -195° ≈ über dem Kopf). Der Stiel hängt dem Arm um bis zu
    115° nach (angewinkeltes Handgelenk): oben hängt der Kopf hinter den Rücken, beim Schlag schnappt er vor."""
    th_hit = math.degrees(math.atan2(target[0] - sh[0], target[1] - sh[1]))   # ca. -45°
    th_up = -195.0
    swing = sp["swing"]
    th = th_hit + (th_up - th_hit) * swing
    reach_hit = min(44.0, math.dist(sh, target) - HAMMER_LEN)
    reach = reach_hit + (42.0 - reach_hit) * swing  # oben Arm fast gestreckt über dem Kopf
    r = math.radians(th)
    hand = (sh[0] + reach * math.sin(r), sh[1] + reach * math.cos(r))
    stick = th - 115 * sp["cock"]                  # Kopf hängt hinterher (Richtung Rücken)
    return hand, 180 - stick


def draw_tool_pose(p: Pen, kind, tool, hip, cx, desk_y, floor, t, keys):
    sw = math.sin(t * 6)
    if kind == "bash":
        # aufgestanden, steht rechts neben der Kiste ">_" und haut mit dem Hammer drauf
        bx, bw_, bh = 22, 70, 56
        p.rect(bx, floor - bh, bw_, bh, lw=2.4, fill=PAPER)
        p.text(">_", bx + bw_ / 2, floor - 20, 22, align="center", bold=True, hand=False)
        fx = bx + bw_ + 40
        target = (bx + bw_ * 0.45, floor - bh - 3)          # Hammerkopf trifft hier
        sp = hammer_swing(t)
        sh = standing_at(fx, flip=False, lean=sp["lean"], crouch=sp["crouch"])["sh"]
        hand, ang = hammer_grip(sh, target, sp)
        # freie Hand zielt beim Ausholen auf die Kiste, hängt beim Schlag
        aim = sp["aim"]
        free = (sh[0] - 30 * aim - 6 * (1 - aim), sh[1] + 40 - 26 * aim)
        standing(p, fx, flip=False, lean=sp["lean"], crouch=sp["crouch"], stance=11, hands=(free, hand))
        p.hammer(hand[0], hand[1], ang)
        if sp["impact"] > 0:
            k = sp["impact"]
            for i in (-1, 0, 1):
                ax = target[0] + 14 * i
                p.line(ax, target[1] - 8 - 4 * (1 - abs(i)), ax + 10 * i * (1 + k), target[1] - 16 - 12 * k, w=1.4, color=GRAY, amp=0)
            p.text("bonk!", bx + bw_ / 2, floor - bh - 30 - 8 * k, 17, align="center", color=GRAY, hand=True)
    elif kind == "read":
        # zurückgelehnt, Buch seitlich vor dem Gesicht: Rücken vorn, offene Seiten zum Leser
        hd = seated_at(hip, lean=-8, look=12)["head"]
        bh = 40.0
        spine = (hd[0] + 46, hd[1] + 2)
        depth = bh * 0.62
        bot = (spine[0] - depth * 0.9, spine[1] + bh / 2)
        # beide Hände halten den unteren Deckel, Ellbogen hängen locker
        seated(p, hip, lean=-8, look=12, hands=((bot[0] + 3, bot[1] + 1), (bot[0] + 12, bot[1] - 4)))
        p.book(*spine, t, h=bh, facing=-1)
    elif kind == "write":
        # schreibt auf ein Blatt neben dem Laptop
        paper_x = cx + 34
        p.rect(paper_x, desk_y - 4, 34, 4, lw=1.6, fill=PAPER)
        pen_at = (paper_x + 10 + 10 * (0.5 + 0.5 * sw), desk_y - 6)
        h = seated(p, hip, lean=18, hands=((pen_at[0] - 6, desk_y - 4), pen_at))
        p.pencil(h["hr"][0] + 2, h["hr"][1] - 14, 160 + 10 * sw)
        for i in range(3):
            p.line(paper_x + 2, desk_y - 30 - i * 8, paper_x + 22 + 8 * math.sin(t + i), desk_y - 30 - i * 8, w=1, color=GRAY)
    elif kind == "subagent":
        # ruft mit dem Megafon nach rechts unten zu den Minions
        shx, shy = seated_at(hip, lean=2)["sh"]
        h = seated(p, hip, lean=2, hands=((shx + 30, shy + 2), (shx + 22, shy + 14)))
        p.megaphone(h["hl"][0], h["hl"][1] - 2, t)
        say_at(p, h["head"], "go, minions!", w=200, h=64, dx=70)
    else:
        # beugt sich mit der Lupe über den Laptop
        shx, shy = seated_at(hip, lean=22 + 4 * sw)["sh"]
        h = seated(p, hip, lean=22 + 4 * sw, hands=((shx + 30, shy + 6), keys))
        p.magnifier(h["hl"][0], h["hl"][1])


# ------------------------------------------------------------------------ Kontextglas
ASSUMED_WINDOW = 200_000


def context_fill(a: Agent) -> tuple[float, bool]:
    """(Füllstand in %, geschätzt?). Ohne bekanntes Fenster wird 200k angenommen."""
    if a.ctx_percent is not None and a.ctx_window:
        return max(0.0, min(100.0, float(a.ctx_percent))), False
    if a.ctx_tokens and a.ctx_window:
        return max(0.0, min(100.0, 100 * a.ctx_tokens / a.ctx_window)), False
    if a.ctx_tokens:
        return max(0.0, min(100.0, 100 * a.ctx_tokens / ASSUMED_WINDOW)), True
    return 0.0, True


def draw_context_jar(p: Pen, a: Agent, t: float, x, y, w, h):
    cr = p.cr
    pct, guessed = context_fill(a)
    squeeze = 0.0
    recent = a.compact_at and (time.time() - a.compact_at) < 12 and a.compact_count > 0
    if a.compacting:
        squeeze = 0.5 + 0.5 * math.sin(t * 4)
    top_y = y + 30 + squeeze * 40
    bulge = squeeze * 14
    # Glas
    jar = [(x + 8, top_y), (x - bulge, top_y + (y + h - top_y) * 0.5), (x + 6, y + h), (x + w - 6, y + h), (x + w + bulge, top_y + (y + h - top_y) * 0.5), (x + w - 8, top_y)]
    fill_top = y + h - (y + h - top_y - 6) * pct / 100
    cr.save()
    cr.move_to(*jar[0])
    for q in jar[1:]:
        cr.line_to(*q)
    cr.close_path()
    cr.clip()
    col = RED if pct > 85 else BLUE if pct > 60 else GRAY
    p.hatch(x - 20, fill_top, w + 40, y + h - fill_top + 4, spacing=6, color=col, lw=1.4)
    p.line(x - 20, fill_top, x + w + 20, fill_top, w=1.8, color=col, amp=1.2)
    cr.restore()
    p.poly(jar, closed=True, w=2.6)
    # Presse
    py = top_y - 8
    p.line(x - 20, py, x + w + 20, py, w=6)
    p.line(x + w / 2, py, x + w / 2, y - 40, w=3)
    p.line(x - 30, y - 40, x + w + 30, y - 40, w=3)
    p.text("context", x + w / 2, y + h + 26, 16, align="center", bold=True)
    if guessed:
        label = f"~{fmt_tok(a.ctx_tokens)} tokens" if a.ctx_tokens else "unknown"
    else:
        label = f"{pct:.0f}% of {fmt_tok(a.ctx_window)}"
    p.text(label, x + w / 2, y + h + 46, 14, align="center", color=col if pct > 60 else INK)
    if a.compacting:
        p.text("squeeeeze!", x + w / 2, y - 52, 18, align="center", bold=True, color=RED)
    elif recent:
        p.text("squish!", x + w / 2, y - 52, 20, align="center", bold=True, color=BLUE)
        if a.compact_before:
            p.text(f"{fmt_tok(a.compact_before)} → {fmt_tok(a.compact_after) if a.compact_after else 'less'}", x + w / 2, y - 76, 13, align="center", color=GRAY)
    if a.compact_count:
        p.text(f"squished {a.compact_count}×", x + w / 2, y + h + 64, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Tacho
def draw_gauge(p: Pen, a: Agent, t: float, cx, cy, r=78, vmax=150.0, hist: History | None = None):
    rate = max(0.0, a.rate or 0.0)
    shown = hist.needle(a.key, rate, t) if hist else rate
    p.arc(cx, cy, r, math.pi, 2 * math.pi, w=2.6)
    p.line(cx - r, cy, cx + r, cy, w=2)
    for i in range(6):
        ang = math.pi + math.pi * i / 5
        p.line(cx + (r - 10) * math.cos(ang), cy + (r - 10) * math.sin(ang), cx + r * math.cos(ang), cy + r * math.sin(ang), w=2, amp=0)
    # roter Bereich
    p.arc(cx, cy, r - 6, math.pi * 1.8, 2 * math.pi, w=5, color=RED)
    v = shown + (1.5 * math.sin(t * 13) if shown > 0.5 else 0)
    ang = math.pi + math.pi * min(1.0, v / vmax)
    p.line(cx, cy, cx + (r - 16) * math.cos(ang), cy + (r - 16) * math.sin(ang), w=3, color=RED, amp=0)
    p.circle(cx, cy, 5, w=2, fill=INK)
    p.text("tokens / sec", cx, cy - r - 12, 15, align="center", bold=True)
    p.text(f"~{rate:.0f}" if a.rate_est else f"{rate:.0f}", cx, cy + 26, 24, align="center", bold=True)
    p.text(f"total eaten: {fmt_tok(a.tok_total)}", cx, cy + 50, 14, align="center")
    if a.tok_in or a.tok_out:
        p.text(f"in {fmt_tok(a.tok_in)} · out {fmt_tok(a.tok_out)}", cx, cy + 68, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Kurve
def draw_chart(p: Pen, a: Agent, t: float, hist: History | None, x, y, w, h):
    p.line(x, y + h, x + w, y + h, w=2)
    p.line(x, y + h, x, y, w=2)
    p.poly([(x - 5, y + 8), (x, y), (x + 5, y + 8)], w=2)
    p.poly([(x + w - 8, y + h - 5), (x + w, y + h), (x + w - 8, y + h + 5)], w=2)
    p.text("context over time", x + w / 2, y - 8, 13, align="center", bold=True)
    p.text("time →", x + w - 4, y + h + 16, 11, align="right", color=GRAY)
    pts = list(hist.data.get(a.key, [])) if hist else []
    win = a.ctx_window or max([v for _, v in pts] + [1])
    if a.ctx_window:
        p.line(x + 4, y + 12, x + w - 6, y + 12, w=1.2, color=RED, dash=[6, 5])
        p.text("limit", x + w - 6, y + 8, 11, align="right", color=RED)
    if len(pts) >= 2:
        t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 30)
        cr = p.cr
        xy = [(x + 4 + (w - 12) * (pt - t0) / (t1 - t0), y + h - 4 - (h - 20) * min(1, v / win)) for pt, v in pts]
        # Ausdünnen
        step = max(1, len(xy) // 80)
        xy = xy[::step] + ([xy[-1]] if (len(xy) - 1) % step else [])
        cr.save()
        p.poly(xy, w=2.4, color=BLUE, amp=0.4)
        cr.restore()
        marks = hist.marks.get(a.key, []) if hist else []
        for m in marks:
            if t0 <= m <= t1:
                mx = x + 4 + (w - 12) * (m - t0) / (t1 - t0)
                p.line(mx, y + 20, mx + 6, y + 40, w=1.4)
                p.text("squish", mx, y + 18, 11, align="center")
    else:
        p.text("(collecting…)", x + w / 2, y + h / 2 + 5, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Notizblock
KIND_COLOR = {"error": RED, "tool_error": RED, "compact_failed": RED, "compact": BLUE, "retry": RED, "subagent": BLUE, "done": INK, "input": INK}
KIND_MARK = {"error": "!", "tool_error": "!", "compact_failed": "!", "compact": "~", "retry": "↻", "subagent": "»", "done": "✓", "input": "?", "tool": "·"}


def draw_notebook(p: Pen, a: Agent, t: float, x, y, w, h):
    # Spiralblock
    p.rect(x, y, w, h, lw=2, fill=PAPER)
    for i in range(7):
        p.circle(x + 12 + i * (w - 24) / 6, y, 4, w=1.5)
    p.text("lab notes", x + w / 2, y + 26, 14, align="center", bold=True)
    evs = a.events[-11:]
    yy = y + 50
    for e in reversed(evs):
        k = e.get("kind", "tool")
        col = KIND_COLOR.get(k, INK)
        p.text(KIND_MARK.get(k, "·"), x + 9, yy, 12, color=col, upper=False)
        p.text(e.get("text", ""), x + 20, yy, 11, color=col, maxw=w - 26, jitter=0.5)
        yy += 26
        if yy > y + h - 8:
            break
    if not evs:
        p.text("(nothing yet)", x + w / 2, y + 70, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Unterer Streifen
def draw_bottom(p: Pen, a: Agent, t: float, x, y, w, h):
    p.line(x + 10, y, x + w - 10, y, w=1.2, color=LIGHT)
    run = next((r for r in reversed(a.runs) if not r.get("finished")), None) or (a.runs[-1] if a.runs else None)
    if run and run.get("agents"):
        draw_minions(p, run, t, x + 20, y, 650, h)
    elif a.children:
        fake = {"total": len(a.children), "done": 0, "failed": 0, "running": len(a.children), "finished": False,
                "agents": [{"agent": f"pid {c.get('pid')}", "task": c.get("prompt", ""), "status": "running" if c.get("phase") != "error" else "failed",
                            "lastTool": (c.get("tools") or [{}])[0].get("label", ""), "tokens": (c.get("tokens") or {}).get("total", 0), "error": ""} for c in a.children]}
        draw_minions(p, fake, t, x + 20, y, 650, h)
    else:
        draw_tool_bars(p, a, x + 30, y + 20, 600, h - 30)
    draw_oops(p, a, t, x + 690, y + 18, 290, h - 24)


def draw_minions(p: Pen, run: dict, t: float, x, y, w, h):
    agents = run.get("agents") or []
    total = max(run.get("total", len(agents)), len(agents))
    done, failed = run.get("done", 0), run.get("failed", 0)
    label = f"subagents ({run.get('mode', '')}): {done}/{total} done" + (f", {failed} fell over" if failed else "")
    lw_ = p.text(label, x, y + 22, 15, bold=True)
    # Fortschrittsbalken hinter der Überschrift
    bx, by, bh = x + lw_ + 20, y + 9, 16
    bw = max(60, w - lw_ - 20)
    p.rect(bx, by, bw, bh, lw=2)
    if total:
        fw = bw * done / total
        if fw > 2:
            p.hatch(bx, by, fw, bh, spacing=5, color=INK, lw=1.4)
        ffw = bw * failed / total
        if ffw > 2:
            p.hatch(bx + fw, by, ffw, bh, spacing=5, color=RED, lw=1.4, angle=-45)
    n = min(len(agents), 6)
    if n == 0:
        return
    slot = w / n
    s = 0.6
    for i, sa in enumerate(agents[:n]):
        cx = x + slot * i + slot / 2
        base = y + h - 22
        hip = (cx - 20, base - 2 * LEG * s)        # Füße genau auf der Grundlinie
        st = sa.get("status")
        if st == "done":
            p.figure(*hip, s=s, la=(30, 10), ra=(-160, -200), ll=(20, 0), rl=(-20, 0))
            p.check(cx + 18, base - 70, 1.3)
        elif st == "failed":
            # umgefallen
            p.figure(cx - 40, base - 8, s=s, la=(-60, -40), ra=(60, 40), ll=(100, 90), rl=(80, 90), lean=-90, eyes="x", color=RED)
            p.smoke(cx + 10, base - 20, t, n=2, color=RED, scale=0.4)
        else:
            # arbeitet = tanzt (jeder Minion eigener, wechselnder Stil), Noten schweben hoch
            style = dance.pick(sa.get("agent", ""), i, t)
            dance.draw(p, style, t + i * 0.37, cx - 10, base, s)
            for j in range(2):
                k = (t * 0.5 + j * 0.5 + i * 0.21) % 1
                p.note(cx + 18 + 8 * math.sin(k * 6 + j), base - 40 - k * 40, 0.7, color=GRAY, double=j == 1)
        name = sa.get("agent", "?")
        p.text(name, cx, base - 92, 12, align="center", bold=True, maxw=slot - 6)
        sub = sa.get("error") if st == "failed" else (sa.get("lastTool") or sa.get("task", ""))
        p.text(sub, cx, base + 16, 10, align="center", color=RED if st == "failed" else GRAY, maxw=slot - 6, jitter=0.4)
    if len(agents) > n:
        p.text(f"+{len(agents) - n}", x + w + 4, y + h / 2 + 10, 14, color=GRAY)


def draw_tool_bars(p: Pen, a: Agent, x, y, w, h):
    p.text("tools used this session", x, y + 4, 15, bold=True)
    items = sorted(a.tool_counts.items(), key=lambda kv: -kv[1])[:5]
    if not items:
        p.text("(no tools yet – no minions deployed)", x, y + 40, 13, color=GRAY)
        return
    mx = max(v for _, v in items)
    bw = (w - 20) / max(1, len(items))
    for i, (name, v) in enumerate(items):
        bx = x + 10 + i * bw
        bh = (h - 40) * v / mx
        p.rect(bx + 10, y + h - 12 - bh, bw - 30, bh, lw=2, fill=PAPER)
        p.hatch(bx + 10, y + h - 12 - bh, bw - 30, bh, spacing=8, color=LIGHT, lw=1)
        p.text(name, bx + bw / 2 - 10, y + h + 4, 12, align="center", maxw=bw - 10)
        p.text(str(v), bx + bw / 2 - 10, y + h - 18 - bh, 12, align="center")


def draw_oops(p: Pen, a: Agent, t: float, x, y, w, h):
    p.text("oops counter", x, y + 4, 15, bold=True, color=RED if a.errors else INK)
    if a.errors:
        p.tally(x + 6, y + 40, a.errors, h=20, color=RED, maxn=20)
        recent = a.last_error_at and time.time() - a.last_error_at < 30
        p.lines(a.last_error, x, y + 64, 11, w - 10, max_lines=2, color=RED if recent else GRAY, jitter=0.4, upper=False)
    else:
        p.text("0 – suspiciously quiet", x, y + 36, 13, color=GRAY)
