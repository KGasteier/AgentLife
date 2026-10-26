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

from .model import Agent
from .sketch import BLUE, GRAY, INK, LIGHT, PAPER, RED, Pen

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
        p.text("z", 420 - k * 40 + i * 6, 250 - k * 120, 16 + k * 22, color=GRAY)
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
    draw_gauge(p, a, t, 690, 140)
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


def draw_actor(p: Pen, a: Agent, t: float):
    cx, floor = 180.0, FLOOR
    desk_y = floor - 80
    hip = (cx, floor - 92)
    ph = a.phase
    tool = a.tools[0] if a.tools else None
    kind = tool_kind(tool["name"]) if tool else None
    if ph == "tool" and not tool:
        ph = "thinking"

    if ph != "retrying":
        p.desk(cx + 30, desk_y, 210, floor)
        p.chair(cx - 4, floor - 55, floor)
    p.line(20, floor, 440, floor, w=1.6, color=GRAY)

    sw = math.sin(t * 7)
    if ph == "idle":
        p.laptop(cx + 140, desk_y, 1.0)
        p.figure(*hip, la=(25, 70), ra=(40, 85), ll=(-80, 0), rl=(-75, 5), lean=-25, flip=True)
        for i in range(3):
            k = (t * 0.45 + i / 3) % 1
            p.text("z", cx - 40 - k * 30, floor - 190 - k * 110, 14 + k * 20, color=GRAY)
        caption(p, "waiting for your next prompt", cx + 40)
    elif ph == "thinking":
        p.laptop(cx + 140, desk_y, 1.0, glow=True)
        h = p.figure(*hip, la=(-160, -200), ra=(-120, -60), ll=(-80, 0), rl=(-75, 5), lean=-6, flip=True)
        bw = 240
        p.bubble(cx - 120, 60, bw, 110, (h["head"][0] - 10, h["head"][1] - 18), kind="thought")
        words = (a.prompt or "hmm…").split()
        k = int(t * 1.3) % max(1, len(words))
        frag = " ".join(words[k:k + 6]) or "…"
        p.lines(frag, cx - 100, 105, 15, bw - 50, max_lines=2)
        dots = "." * (1 + int(t * 2) % 3)
        p.text(dots, cx + 90, 150, 22)
    elif ph == "streaming":
        p.laptop(cx + 140, desk_y, 1.0, glow=True)
        k = 1 + min(3.0, a.rate / 25)
        p.figure(*hip, la=(-85 + 18 * math.sin(t * 9 * k), -95), ra=(-75 + 18 * math.sin(t * 9 * k + 2), -90), ll=(-80, 0), rl=(-75, 5), lean=-10, flip=True)
        caption(p, "streaming tokens", cx + 40)
    elif ph == "tool":
        p.laptop(cx + 140, desk_y, 1.0, glow=True)
        draw_tool_pose(p, kind, tool, hip, cx, desk_y, floor, t)
        caption(p, f"{tool['name']}: {tool['label']}", cx + 40)
        if len(a.tools) > 1:
            p.text(f"+{len(a.tools) - 1} more tools running", cx + 300, 80, 13, color=GRAY, align="center")
    elif ph == "compacting":
        p.laptop(cx + 140, desk_y, 1.0)
        # Figur zeigt aufgeregt auf das Glas
        p.figure(*hip, la=(-115, -120), ra=(-60, -50), ll=(-80, 0), rl=(-75, 5), lean=-15 + 5 * sw, flip=True)
        p.bubble(cx - 40, 70, 220, 64, (cx + 20, 150))
        p.text("hold on, packing…", cx + 70, 110, 17, align="center")
        caption(p, "summarizing old context", cx + 40)
    elif ph == "retrying":
        # Figur klopft an die Tür "API"
        dx = 300
        p.rect(dx, floor - 190, 80, 190, lw=2.6, fill=PAPER)
        p.circle(dx + 14, floor - 95, 4, w=2)
        p.text("API", dx + 40, floor - 160, 20, align="center", bold=True)
        knock = abs(math.sin(t * 6))
        p.figure(dx - 70, floor - 96, ra=(-110 + 30 * knock, -150), la=(-30, -10), ll=(14, 0), rl=(-14, 0), lean=4)
        if knock > 0.85:
            p.text("knock", dx - 10, floor - 175, 15, color=GRAY)
        r = a.retry or {}
        p.bubble(40, 70, 220, 64, (dx - 80, floor - 170))
        p.text(f"try {r.get('attempt', '?')} of {r.get('max', '?')}…", 150, 110, 17, align="center")
        caption(p, r.get("error") or "provider said no", 220)
    elif ph == "error":
        p.laptop(cx + 140, desk_y, 1.0)
        p.flame(cx + 145, desk_y - 40, t)
        p.smoke(cx + 150, desk_y - 70, t)
        jump = abs(math.sin(t * 5)) * 8
        p.figure(hip[0] - 40, hip[1] - jump, la=(160 + 15 * sw, 200), ra=(-160 - 15 * sw, -200), ll=(14, 0), rl=(-14, 0), eyes="dots")
        p.bubble(cx - 150, 60, 150, 56, (cx - 50, 140))
        p.text("aaaaa!", cx - 75, 96, 20, align="center", bold=True, color=RED)
        caption(p, a.last_error or "error", cx + 40, color=RED)
    else:
        p.laptop(cx + 140, desk_y, 1.0)
        p.figure(*hip, flip=True)

    # Token-Münzen fliegen vom Laptop zum Tacho
    if a.rate > 0 and ph in ("streaming", "tool", "thinking"):
        n = int(min(10, 1 + a.rate / 10))
        for i in range(n):
            k = (t * (0.35 + a.rate / 300) + i / n) % 1
            x0, y0 = cx + 150, desk_y - 40
            x1, y1 = 690, 200
            x = x0 + (x1 - x0) * k
            y = y0 + (y1 - y0) * k - math.sin(k * math.pi) * 120
            p.coin(x, y, 7)


def caption(p: Pen, text: str, x: float, color=INK):
    p.text(text, x, FLOOR + 20, 14, align="center", color=color, maxw=400)


def draw_tool_pose(p: Pen, kind, tool, hip, cx, desk_y, floor, t):
    sw = math.sin(t * 6)
    if kind == "bash":
        # Hammer auf eine Kiste mit dem Befehl
        bx = cx - 150
        p.rect(bx, floor - 70, 90, 70, lw=2.4, fill=PAPER)
        p.text(">_", bx + 45, floor - 28, 22, align="center", bold=True)
        ang = -60 + 70 * (0.5 + 0.5 * sw)
        h = p.figure(hip[0] - 20, hip[1], ra=(ang * 0.6 - 90, ang - 90), la=(-50, -20), ll=(-80, 0), rl=(-75, 5), lean=-15, flip=False)
        p.hammer(h["hr"][0], h["hr"][1], -ang - 30)
        if sw > 0.8:
            p.text("bonk!", bx + 40, floor - 95, 15, align="center", color=GRAY)
    elif kind == "read":
        h = p.figure(*hip, la=(-140, -170), ra=(-140, -100), ll=(-80, 0), rl=(-75, 5), lean=-8, flip=True)
        p.book(h["hl"][0] - 6, h["hl"][1] - 4, t)
    elif kind == "write":
        h = p.figure(*hip, la=(-90, -100), ra=(-70 + 10 * sw, -95), ll=(-80, 0), rl=(-75, 5), lean=-18, flip=True)
        p.rect(cx + 40, desk_y - 6, 60, 6, lw=1.6, fill=PAPER)
        p.pencil(h["hr"][0] + 4, h["hr"][1] - 10, 150 + 10 * sw)
        for i in range(3):
            p.line(cx + 44, desk_y - 30 - i * 8, cx + 44 + 30 + 10 * math.sin(t + i), desk_y - 30 - i * 8, w=1, color=GRAY)
    elif kind == "subagent":
        h = p.figure(hip[0] - 10, hip[1], la=(-140, -110), ra=(-30, -20), ll=(-80, 0), rl=(-75, 5), lean=-10, flip=True)
        p.megaphone(h["hl"][0], h["hl"][1] - 4, t)
        p.text("go, minions!", h["hl"][0] + 40, h["hl"][1] - 40, 15, color=GRAY)
    else:
        h = p.figure(*hip, la=(-130, -150), ra=(-60, -40), ll=(-80, 0), rl=(-75, 5), lean=-12 + 4 * sw, flip=True)
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
def draw_gauge(p: Pen, a: Agent, t: float, cx, cy, r=78, vmax=150.0):
    rate = max(0.0, a.rate or 0.0)
    p.arc(cx, cy, r, math.pi, 2 * math.pi, w=2.6)
    p.line(cx - r, cy, cx + r, cy, w=2)
    for i in range(6):
        ang = math.pi + math.pi * i / 5
        p.line(cx + (r - 10) * math.cos(ang), cy + (r - 10) * math.sin(ang), cx + r * math.cos(ang), cy + r * math.sin(ang), w=2, amp=0)
    # roter Bereich
    p.arc(cx, cy, r - 6, math.pi * 1.8, 2 * math.pi, w=5, color=RED)
    v = rate + (1.5 * math.sin(t * 13) if a.rate > 0 else 0)
    ang = math.pi + math.pi * min(1.0, v / vmax)
    p.line(cx, cy, cx + (r - 16) * math.cos(ang), cy + (r - 16) * math.sin(ang), w=3, color=RED, amp=0)
    p.circle(cx, cy, 5, w=2, fill=INK)
    p.text("tokens / sec", cx, cy - r - 12, 15, align="center", bold=True)
    p.text(f"{rate:.0f}", cx, cy + 26, 24, align="center", bold=True)
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
        hip = (cx - 20, base - 48 * s * 1.0 - 4)
        st = sa.get("status")
        if st == "done":
            p.figure(*hip, s=s, la=(30, 10), ra=(-160, -200), ll=(20, 0), rl=(-20, 0))
            p.check(cx + 18, base - 70, 1.3)
        elif st == "failed":
            # umgefallen
            p.figure(cx - 40, base - 8, s=s, la=(-60, -40), ra=(60, 40), ll=(100, 90), rl=(80, 90), lean=-90, eyes="x", color=RED)
            p.smoke(cx + 10, base - 20, t, n=2, color=RED, scale=0.4)
        else:
            sw = math.sin(t * 6 + i)
            p.figure(*hip, s=s, la=(30 * sw, 10), ra=(-30 * sw, -10), ll=(20 * sw, 0), rl=(-20 * sw, 0), head_dy=abs(sw) * 2)
            p.rect(cx + 2, base - 22, 22, 22, lw=1.6, fill=PAPER)
            p.text("…" if int(t * 2 + i) % 2 else "..", cx + 13, base - 26, 12, align="center", color=GRAY)
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
