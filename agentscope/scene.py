"""Die xkcd-Szene: jeder Agent ist ein Comic-Panel.

Metaphern (siehe docs/SPEC.md):
- Hauptfigur am Schreibtisch = Hauptagent; Pose zeigt die Phase
  (denken, tippen/streamen, Werkzeug, quetschen, erneut versuchen, Fehler, schlafen).
- Werkzeuge als Requisiten: bash = Hammer auf Kiste, read = Buch, edit/write = Bleistift,
  subagent = Megafon, Rest = Lupe.
- Glas „Kontext“ = Kontextfüllung; Presse darüber = Kompaktierung („quetsch!“).
- Tacho = Tokens pro Sekunde, fliegende Münzen = Token-Strom, Zähler = Summe.
- Kurve „Kontext im Zeitverlauf“ mit Sägezahn = Kompaktierungen im Verlauf.
- Kleine Figuren unten = Subagents (arbeiten / Haken / umgefallen) + Fortschrittsbalken.
- Strichliste „Hoppla“ + rote Notiz = Fehler. Notizblock rechts = letzte Ereignisse.
"""

from __future__ import annotations

import math
import time
from collections import deque

import cairo

from . import dance
from .model import Agent
from . import sketch
from .sketch import LEG, BLUE, GRAY, INK, LIGHT, PAPER, PINK, RED, Pen

PW, PH = 1000.0, 560.0  # virtuelles Panel
FLOOR = 376.0

ALT_TEXTS = [
    "Das Kontextfenster ist wie ein Koffer: Je mehr man quetscht, desto weniger weiß man, wo die Socken sind.",
    "Subagents sind Praktikanten mit unendlicher Geduld und null Gedächtnis.",
    "Jedes Token hier wurde von einem winzigen statistischen Handwerker von Hand gefertigt.",
    "Wenn die Strichliste bei fünf ist, ist es kein Bug mehr, sondern ein Bündel.",
    "Compaction: die Kunst, drei Stunden Arbeit als „hab Sachen gemacht, meist okay“ zusammenzufassen.",
    "Retry ist nur Optimismus mit exponentiellem Backoff.",
]

PHASE_WORDS = {
    "idle": "zzz… wartet auf dich",
    "thinking": "denkt angestrengt nach",
    "streaming": "tippt wie verrückt",
    "tool": "benutzt Werkzeuge",
    "compacting": "quetscht den Kontext",
    "retrying": "klopft wieder bei der API an",
    "error": "etwas ist kaputt",
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
        self._phase: dict[str, str] = {}
        self._since: dict[str, float] = {}

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
            # Übergang „arbeitet → fertig“ merken (löst den Siegestanz aus)
            prev_ph = self._phase.get(a.key)
            if a.phase == "idle" and prev_ph not in (None, "idle"):
                self._since[a.key] = now
            elif a.phase != "idle":
                self._since.pop(a.key, None)
            self._phase[a.key] = a.phase
            if a.idle_since is None and a.key in self._since:
                a.idle_since = self._since[a.key]
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
def _header_dynamic(p, W, hs, agents, shown, max_panels, tot, subs, errs, rate, clock):
    sub = f"{len(agents)} {'Agent' if len(agents) == 1 else 'Agenten'} · {subs} Subagents beschäftigt · {fmt_tok(tot)} Tokens gefressen · {rate:.0f} tok/s · {errs} Hoppla"
    p.text(sub, W / 2, 76 * hs, 15 * hs, align="center", color=GRAY)
    p.text(clock or time.strftime("%H:%M"), W - 24, 40 * hs, 22 * hs, align="right")
    if len(agents) > max_panels:
        p.text(f"+{len(agents) - max_panels} weitere nicht gezeigt", 24, 40 * hs, 14 * hs, color=GRAY)

def render(cr: cairo.Context, W: float, H: float, agents: list[Agent], t: float, hist: History | None = None,
           clock: str | None = None, max_panels: int = 4, layer: str | None = None):
    """layer="static" zeichnet nur Rahmen/Beschriftungen (einmal in eine Fläche), "dynamic" nur Bewegtes darüber."""
    boil = 0 if layer == "static" else int(t * 4)
    p = Pen(cr, boil=boil)
    p.layer = layer
    if p.st:
        cr.set_source_rgb(*PAPER)
        cr.paint()

    shown = agents[:max_panels]
    # Kopfzeile
    tot = sum(a.tok_total for a in agents)
    subs = sum(len(r.get("agents") or []) for a in agents for r in a.runs if not r.get("finished")) + sum(len(a.children) for a in agents if not a.runs)
    errs = sum(a.errors for a in agents)
    rate = sum(a.rate for a in agents)
    hs = max(0.6, min(1.3, W / 1440))
    if p.st:
        p.text("Was meine Agenten gerade treiben", W / 2, 46 * hs, 30 * hs, align="center", bold=True)
    if p.dy:
        _header_dynamic(p, W, hs, agents, shown, max_panels, tot, subs, errs, rate, clock)
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

    alt = ALT_TEXTS[int(t / 20) % len(ALT_TEXTS)] if p.dy else ""
    if alt:
        p.text(alt, W / 2, H - 16 * hs, 13 * hs, align="center", color=GRAY, upper=False, jitter=0.3, maxw=W - 60)


class StaticLayer:
    """Rahmen, Möbel-lose Beschriftungen und Achsen einmal in eine Fläche rendern und nur noch blitten.

    Neu gerendert wird nur, wenn sich Größe, Panel-Anzahl oder Titel ändern (Schlüssel `key`)."""

    def __init__(self):
        self.key = None
        self.surf = None
        self.renders = 0

    @staticmethod
    def make_key(W, H, agents, max_panels=4):
        return (round(W), round(H), tuple(panel_title(a) for a in agents[:max_panels]),
                tuple(getattr(a, "harness", "pi") for a in agents[:max_panels]), len(agents) > max_panels)

    def paint(self, cr, W, H, agents, max_panels=4):
        key = self.make_key(W, H, agents, max_panels)
        m = cr.get_matrix()
        sx, sy = (m.xx, m.yy) if m.xx and m.yy else (1.0, 1.0)
        ds = cr.get_target().get_device_scale()[0] * sketch.HINT_SCALE  # HiDPI: GTK setzt den Maßstab auf die Fläche, nicht in die Matrix
        key += (round(sx, 3), round(sy, 3), ds)
        if key != self.key or self.surf is None:
            self.surf = cairo.ImageSurface(cairo.FORMAT_RGB24, max(1, round(W * sx * ds)), max(1, round(H * sy * ds)))
            c2 = cairo.Context(self.surf)
            c2.scale(sx * ds, sy * ds)
            render(c2, W, H, agents, 0.0, None, clock="", max_panels=max_panels, layer="static")
            self.key = key
            self.renders += 1
        cr.save()
        cr.scale(1 / (sx * ds), 1 / (sy * ds))
        cr.set_source_surface(self.surf, 0, 0)
        cr.paint()
        cr.restore()

def render_cached(cr, W, H, agents, t, hist, layer_cache: StaticLayer, clock=None, max_panels=4):
    layer_cache.paint(cr, W, H, agents, max_panels)
    render(cr, W, H, agents, t, hist, clock=clock, max_panels=max_panels, layer="dynamic")

def render_empty(p: Pen, W, H, t, top, bottom):
    if not p.dy:
        return
    cr = p.cr
    s = min(W / PW, (H - top - bottom) / PH) * 0.9
    cr.save()
    cr.translate((W - PW * s) / 2, top + (H - top - bottom - PH * s) / 2)
    cr.scale(s, s)
    from . import acts
    if acts.empty_scene(p, t):
        p.text("Es läuft gerade kein Agent.", PW / 2, 506, 22, align="center", bold=True)
        cr.restore()
        return
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
    p.text("Es läuft gerade kein Agent.", PW / 2, 470, 26, align="center", bold=True)
    p.text("Starte pi und komm wieder – dann füllt sich das Bild.", PW / 2, 506, 17, align="center", color=GRAY)
    cr.restore()


# ======================================================================== Panel
def has_model(a: Agent) -> bool:
    """Ist ein Modell angewählt? Fehlt es, gilt die Verbindung als getrennt (schlaffe Puppe, gerissener Faden)."""
    return bool((getattr(a, "model", "") or "").strip())


# Fehlerhinweise, die auf eine kaputte Anbindung deuten (nicht auf einen inhaltlichen Fehler)
CONNECT_HINTS = ("timeout", "timed out", "econnrefused", "econnreset", "connect", "unreachable",
                 "refused", "getaddrinfo", "socket", "network", "no route", "tls", "dns", "401", "403")


def has_connect(a: Agent) -> bool:
    """Steht die Anbindung zum angewählten Modell?

    Ein Modell kann angewählt sein, ohne dass je ein Token fließt (falscher Schlüssel,
    unerreichbarer Endpunkt, Zeitüberschreitung). Solange kein einziger Token ankam und
    schon in Runde 0 ein Fehler auftrat, gilt die Anbindung als defekt."""
    if not has_model(a):
        return False
    if a.tok_total > 0:
        return True                                  # es flossen schon Tokens → Anbindung stand
    return not (a.turn <= 0 and a.errors > 0)


def model_ink(a: Agent):
    """Farbe des Modellnamens: blau = verbunden, rot = angewählt aber keine Anbindung, grau = kein Modell."""
    if not has_model(a):
        return GRAY
    return BLUE if has_connect(a) else RED


def brain_pos(a: Agent, title_width: float):
    """Position des pinken Gehirns rechts vom Titelkasten, links vom Modellnamen (Mitte des Gehirns)."""
    return (title_width + 54.0, 18.0)


def harness_ink(a: Agent):
    """Farbton für Beschriftungskasten und Titeltext je Harness (pi bleibt Tinte; die Skizzenlinien selbst bleiben schwarz)."""
    return {"pi": INK, "claude": (0.72, 0.36, 0.14), "codex": (0.13, 0.44, 0.34),
            "demo": INK}.get(getattr(a, "harness", "pi") or "pi", INK)


def harness_tint(a: Agent):
    """Sanfte Füllfarbe des Beschriftungskastens: nur dort sitzt die Harness-Farbe, Skizzenlinien bleiben Tinte."""
    return {"pi": (0.94, 0.94, 0.92), "claude": (0.98, 0.90, 0.80), "codex": (0.86, 0.94, 0.91),
            "demo": (0.94, 0.94, 0.92)}.get(getattr(a, "harness", "pi") or "pi", (0.94, 0.94, 0.92))


def session_label(a: Agent) -> str:
    """Kurze Sitzungskennung als Rückfall, wenn weder Skill noch Sitzungsname vorliegt."""
    key = (getattr(a, "key", "") or "").split(":", 1)[-1]
    key = key.rsplit("/", 1)[-1].replace(".jsonl", "").replace(".json", "")
    short = key[-8:] if len(key) > 8 else key
    return f"Sitzung {short}" if short else "Sitzung"


def panel_title(a: Agent) -> str:
    """Beschriftung links oben: Harness · Skill/Sitzungsname, immer mit Sitzungsinfo."""
    harness = getattr(a, "harness", "pi") or "pi"
    short = (getattr(a, "skill", "") or (a.title or "").strip())
    if not short or short == "?":
        short = session_label(a)
    return f"{harness} · {short}"


def render_panel(p: Pen, a: Agent, t: float, hist: History | None):
    title = p.fit(panel_title(a), 22, 420)
    tw = p.text_width(title, 22, bold=True)
    if p.st:
        p.rect(0, 0, PW, PH, lw=3)
        # Beschriftungskasten wie xkcd-Caption: einziger farbiger Ort je Harness
        p.rect(-1, -1, tw + 36, 40, lw=2.4, color=harness_ink(a), fill=harness_tint(a))
        p.text(title, 16, 28, 22, bold=True, color=harness_ink(a))
        p.line(20, FLOOR, 440, FLOOR, w=1.6, color=GRAY)
        # pinkes Gehirn links vom Modellnamen; der Faden zum Kopf folgt in der dynamischen Ebene
        bx, by = brain_pos(a, tw)
        tip = p.brain(bx, by, 2.3)                 # Gehirn im Titelbereich; Stielspitze für den Faden
        p.brain_xy = (bx, by)
        p.brain_tip = tip
    else:
        p.brain_xy = brain_pos(a, tw)
        p.brain_tip = None
    if p.dy:
        phase_txt = PHASE_WORDS.get(a.phase, a.phase)
        if has_model(a):
            # Modellname farbig; ohne Anbindung zusätzlich deutlich als Defekt markiert
            mw = p.text(a.model, tw + 82, 28, 15, color=model_ink(a), maxw=820 - tw - 82)
            tail = f" · Runde {a.turn} · {phase_txt}"
            if not has_connect(a):
                tail = f" · {tail.strip(' ·')} · keine Anbindung!"
            p.text(tail, tw + 82 + mw + 4, 28, 15, color=RED if not has_connect(a) else GRAY,
                   maxw=820 - tw - 82 - mw - 4)
        else:
            p.text("kein Modell · getrennt", tw + 82, 28, 15, color=PINK, maxw=820 - tw - 82)
        if a.source == "log":
            p.text("(aus dem Sitzungslog)" if a.harness == "pi" else f"({a.harness}-Sitzungslog)",
                   830, 28, 12, color=GRAY, align="right")
        draw_actor(p, a, t)
        from . import acts
        if a.phase not in ("retrying",) and not (a.phase == "idle" and (a.idle_for or 1e9) < acts.FINALE_S):
            acts.ambient(p, a.key, t)
    draw_context_jar(p, a, t, 470, 140, 92, 190)
    draw_gauge(p, a, t, 690, 140, hist=hist)
    draw_chart(p, a, t, hist, 590, 250, 230, 130)
    draw_notebook(p, a, t, 845, 52, 145, 345)
    if p.st:
        p.line(10, 404, PW - 10, 404, w=1.2, color=LIGHT)
    if p.dy:
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


def draw_slumped(p: Pen, a: Agent, t: float, cx: float, seat_y: float, floor: float):
    """Kein Modell angewählt: leblose Strichpuppe, versunken in den Stuhl gekippt, Arme baumeln."""
    p.desk(cx + 28, floor - DESK_H, 220, floor)
    p.chair(cx - 6, seat_y, floor, facing=1)
    p.laptop(cx + 70, floor - DESK_H, 1.0, glow=False)
    hip = (cx - 6, seat_y - 3)
    hd = seated_at(hip, lean=-34)["head"]
    h = p.figure(hip[0], hip[1], lean=-34, look=-46, flip=True, feet=((hip[0] + LEG + 3, floor), (hip[0] + LEG - 5, floor)),
                 hands=((hd[0] - 10, hd[1] + 24), (hd[0] - 4, hd[1] + 30)), color=GRAY, w=2.0)
    hx, hy = h["head"]
    for dx in (-5, 4):                                   # geschlossene, leblose Augen
        p.line(hx + dx - 3, hy - 2, hx + dx + 3, hy - 2, w=1.6, color=GRAY, amp=0)
    p.line(hx + 12, hy + 4, hx + 18, hy + 16, w=1.6, color=GRAY, amp=0)   # hängender Mundwinkel
    for i in range(3):
        p.text("z", hx - 24 - i * 12, hy - 14 - i * 12, 11 + i * 4, color=LIGHT, hand=True)
    caption(p, "kein Modell angewählt – Verbindung getrennt", cx + 60, color=GRAY)


def draw_inactive_rest(p: Pen, a: Agent, t: float):
    """Kein Modell: der untere Streifen zeigt keine Aktivität – keine Minions, Balken oder Hoppla-Striche."""
    if not p.dy:
        return
    p.text("Tools in dieser Sitzung", 30, 424, 15, bold=True, color=GRAY)
    p.text("(keine – kein Modell angewählt)", 30, 460, 13, color=GRAY)
    p.text("Hoppla-Zähler", 690, 422, 15, bold=True, color=GRAY)
    p.text("0 – kein Modell", 696, 458, 13, color=GRAY)


def _thread_points(bx, by, tx, ty, t, n=22):
    """Punkte des luftigen pinken Fadens von (bx,by) nach (tx,ty); Anfang und Ende exakt."""
    pts = []
    for i in range(n + 1):
        k = i / n
        x = bx + (tx - bx) * k
        y = by + (ty - by) * k
        env = math.sin(math.pi * k)                        # an beiden Enden exakt 0 (fester Anschluss)
        sag = 16 * env                                     # leichter Durchhang
        wave = 6.0 * math.sin(k * 9.0 - t * 2.6) * env
        pts.append((x + wave * 0.8, y + sag + wave))
    return pts


def _thread_behind(p: Pen, pts, color=PINK):
    """Zeichnet den Faden, lässt ihn aber hinter Sprech-/Gedankenblasen verschwinden (keine Lücke am Kopf)."""
    run = [pts[0]]
    for q in pts[1:]:
        if p.bubbles_cover(q[0], q[1]):
            if len(run) > 1:
                p.curve(run, w=0.7, color=color)
            run = []
        else:
            run.append(q)
    if len(run) > 1:
        p.curve(run, w=0.7, color=color)


def _model_thread(p: Pen, cx: float, t: float, broken: bool = False, bad: bool = False):
    """Ganz feiner Faden vom Gehirn (Titel) zum Kopf der Hauptfigur; wackelt luftig mit.

    Liegt hinter Sprech-/Gedankenblasen und endet fest am Kopf (kein Spalt).
    broken=True (kein Modell): der Faden ist oben abgerissen und baumelt schlaff herab.
    bad=True (Modell angewählt, aber keine Anbindung): der Faden ist rot und zuckt,
    mit einer Blitzstelle in der Mitte – „da kommt nichts durch“."""
    if not p.dy or not p.heads:
        return
    tip = getattr(p, "brain_tip", None)
    if tip:
        bx, by = tip                                  # exakt an der Stielspitze
    else:
        bx, by = getattr(p, "brain_xy", (60.0, 18.0))
        by += 9
    hip, head = min(p.heads, key=lambda hh: abs(hh[0][0] - cx))   # Kopf der Hauptfigur (nächste Hüfte an cx)
    hx, hy = head
    tx, ty = hx - 2, hy - 15                              # Kopfoberkante, fest am Kreis
    if broken:
        # oben abgerissen: kurzes, schlaff herabhängendes Ende direkt unter dem Gehirn
        sway = 5.0 * math.sin(t * 1.3)
        mid = (bx + 3 * math.sin(t * 1.1), by + 22 + 2 * math.sin(t * 0.9))
        end = (bx + sway, by + 40 + 3 * math.sin(t * 1.7))
        p.curve([(bx, by), mid, end], w=0.7, color=PINK)
        p.circle(end[0], end[1], 1.7, w=0.8, color=PINK, fill=PINK)
        p.text("kein Signal", end[0] + 6, end[1] + 4, 9, color=PINK, hand=True, upper=False, jitter=0.4)
        return
    pts = _thread_points(bx, by, tx, ty, t)
    if bad:
        # rote, zuckende Leitung mit Blitzstelle: Anbindung angewählt, aber tot
        jit = [((q[0] + 1.6 * math.sin(t * 21 + i * 2.3)), q[1]) for i, q in enumerate(pts)]
        _thread_behind(p, jit, color=RED)
        mi = max(1, len(pts) // 4)                 # Blitzstelle nahe am Gehirn, nicht hinter der Blase
        mx, my = pts[mi]
        bolt = [(mx - 5, my - 7), (mx + 2, my - 1), (mx - 3, my + 1), (mx + 5, my + 8)]
        p.poly(bolt, closed=False, w=1.6, color=RED)
        for k in range(3):
            a = t * 3.0 + k * 2.1
            p.line(mx + 6 * math.cos(a), my + 4 * math.sin(a), mx + 11 * math.cos(a), my + 8 * math.sin(a),
                   w=1.0, color=RED, amp=0)
        p.circle(tx, ty, 1.5, w=0.9, color=RED, fill=RED)
        p.text("unterbrochen", tx + 10, ty - 6, 9, color=RED, hand=True, upper=False, jitter=0.4)
        return
    _thread_behind(p, pts)
    p.circle(tx, ty, 1.5, w=0.9, color=PINK, fill=PINK)   # fester Anschluss am Kopf


def draw_actor(p: Pen, a: Agent, t: float):
    p.heads = []                     # nur die Figuren dieses Panels für den Modell-Faden
    p.bubbles = []                   # nur die Blasen dieses Panels (Faden liegt dahinter)
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

    sw = math.sin(t * 7)
    glow = ph in ("thinking", "streaming", "tool")
    if ph not in ("retrying",):
        p.laptop(lap_x, desk_y, 1.0, glow=glow)

    if ph == "error":
        p.flame(lap_x + 8, desk_y - 30, t)
        p.smoke(lap_x + 12, desk_y - 60, t)

    if not has_model(a):
        draw_slumped(p, a, t, cx, seat_y, floor)
        _model_thread(p, cx, t, broken=True)
        return
    if not has_connect(a):
        # angewähltes Modell, aber keine Anbindung: normale Pose, dazu roter Defekt-Faden
        _bad = True
    else:
        _bad = False

    from . import acts
    ctx = acts.context(cx, floor, desk_y, seat_y, hip, lap_x, keys)
    acts.overgrowth(p, a, t, ctx)
    cap = acts.draw(p, a, ph, kind, t, ctx)
    if cap is not None:
        caption(p, cap or default_caption(a, ph, tool), cx + 60, color=RED if ph == "error" else INK)
        if ph == "tool" and len(a.tools) > 1:
            p.text(f"+{len(a.tools) - 1} weitere Tools laufen", cx + 300, 80, 13, color=GRAY, align="center")
    elif ph == "idle":
        # zurückgelehnt, Hände im Schoß, Kopf zur Seite gekippt
        h = seated(p, hip, lean=-14, look=-25, hands=((cx + 22, hip[1] - 6), (cx + 28, hip[1] - 4)))
        for i in range(3):
            k = (t * 0.45 + i / 3) % 1
            p.text("z", h["head"][0] - 20 - k * 30, h["head"][1] - 30 - k * 110, 16 + k * 22, color=GRAY, hand=True)
        caption(p, "wartet auf deinen nächsten Prompt", cx + 60)
    elif ph == "thinking":
        # zurückgelehnt, Hand am Kinn
        hd = seated_at(hip, lean=-6)["head"]
        h = seated(p, hip, lean=-6, hands=((hd[0] + 9, hd[1] + 15), (cx + 26, hip[1] - 5)))
        words = (a.prompt or "hmm…").split()
        k = int(t * 0.5) * 7 % max(1, len(words))
        frag = " ".join(words[k:k + 9]) or "…"
        think_at(p, h["head"], frag + " " + "." * (1 + int(t * 2) % 3))
        caption(p, "denkt nach", cx + 60)
    elif ph == "streaming":
        hl, hr, lean, look = typing_hands(t, a.rate, keys)
        seated(p, hip, lean=lean, look=look, hands=(hl, hr))
        caption(p, "streamt Tokens", cx + 60)
    elif ph == "tool":
        draw_tool_pose(p, kind, tool, hip, cx, desk_y, floor, t, keys)
        caption(p, f"{tool['name']}: {tool['label']}", cx + 60)
        if len(a.tools) > 1:
            p.text(f"+{len(a.tools) - 1} weitere Tools laufen", cx + 300, 80, 13, color=GRAY, align="center")
    elif ph == "compacting":
        # zeigt aufgeregt aufs Glas (rechts oben)
        shx, shy = seated_at(hip, lean=4 + 3 * sw)["sh"]
        h = seated(p, hip, lean=4 + 3 * sw, hands=((shx + 46, shy - 14 + 3 * sw), (cx + 26, hip[1] - 5)))
        say_at(p, h["head"], "Moment, ich packe ein…", dx=60)
        caption(p, "fasst alten Kontext zusammen", cx + 60)
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
            p.text("klopf", dx - 14, floor - 205, 16, color=GRAY, hand=True)
        r = a.retry or {}
        say_at(p, h["head"], f"Versuch {r.get('attempt', '?')} von {r.get('max', '?')}…", dx=-120, w=220)
        caption(p, r.get("error") or "Anbieter sagt nein", 220)
    elif ph == "error":
        jump = abs(math.sin(t * 5)) * 12
        h = standing(p, cx - 60, lift=jump, flip=False, la=(160 + 15 * sw, 200), ra=(-160 - 15 * sw, -200), eyes="dots")
        say_at(p, h["head"], "AAAAA!", w=170, h=70, size=24, color=RED, bold=True, dx=-10)
        caption(p, a.last_error or "Fehler", cx + 60, color=RED)
    else:
        seated(p, hip, lean=4, hands=((cx + 24, hip[1] - 6), (cx + 30, hip[1] - 4)))

    _model_thread(p, cx, t, bad=_bad)

    # Token-Münzen: der Laptop wirft gelbe Tokens in den Maul-Kopf; grün spuckt er sie wieder aus
    if a.rate > 0 and ph in ("streaming", "tool", "thinking"):
        mx, my = MAUL
        n = int(min(10, 1 + a.rate / 10))
        speed = 0.35 + a.rate / 300
        chew = 0.0
        coins = []
        for i in range(n):
            k = (t * speed + i / n) % 1
            if k < 0.5:                                    # Flug in den Mund (gelb), kurzer Weg von links
                f = k / 0.5
                x0, y0 = mx - 44, my + 22
                x = x0 + (mx - 18 - x0) * f
                y = y0 + (my - y0) * f - math.sin(f * math.pi) * 6
                coins.append((x, y, 6, TOK_IN))
            elif k < 0.6:
                chew = max(chew, 1.0)                      # gerade verschluckt
            else:                                          # Ausspucken (grün), kleine Wolke nach oben
                f = (k - 0.6) / 0.4
                x = mx - 6 - 26 * f
                y = my - 6 - 54 * f
                coins.append((x, y, 6 * (0.7 + 0.3 * f), TOK_OUT))
                if f < 0.25:
                    chew = max(chew, 0.5)
        draw_maul(p, mx, my, t, chew, mirror=True)
        for x, y, r, col in coins:
            p.coin(x, y, r, fill=col)

# Maul sitzt gespiegelt rechts neben „gesamt gefressen…“; links geht Gelb hinein, rechts kommt Grün heraus.
MAUL = (806.0, 150.0)
TOK_IN = (1.0, 0.88, 0.35)
TOK_OUT = (0.62, 0.90, 0.55)


def draw_maul(p: Pen, x, y, t, chew, mirror=False):
    """Maul-Kopf: Mund klappt auf/zu, Zähne, Schmatzen. mirror=True öffnet nach links."""
    d = -1.0 if mirror else 1.0
    c0 = math.pi if mirror else 0.0
    gap = 0.28 + 0.38 * abs(math.sin(t * 7)) * (0.4 + chew)
    R = 20
    pts = [(x, y)]
    for i in range(0, 25):
        ang = c0 + d * (gap + (2 * math.pi - 2 * gap) * i / 24)
        pts.append((x + R * math.cos(ang), y + R * math.sin(ang)))
    p.poly(pts, closed=True, w=2.2, fill=PAPER, amp=0.4)
    for sgn in (-1, 1):                                   # Zähne an Ober- und Unterkiefer
        ang = c0 + d * gap if sgn < 0 else c0 - d * gap
        for j in range(3):
            r0 = 8 + 4 * j
            ex, ey = x + r0 * math.cos(ang), y + r0 * math.sin(ang)
            p.line(ex, ey, ex - d * sgn * 3.5, ey - sgn * 2, w=1.2, amp=0)
    p.circle(x - d * 4, y - 11, 2.6, w=1.4, fill=INK)
    p.text("MAUL", x - 2, y + 38, 12, align="center", color=GRAY, hand=True)
    if chew >= 1.0:
        p.text("mampf", x - d * 6, y - 28, 12, align="center", color=GRAY, hand=True, upper=False)
    elif chew > 0:
        p.text("ptui", x + d * 30, y - 16, 12, align="center", color=GRAY, hand=True, upper=False)

def default_caption(a: Agent, ph: str, tool) -> str:
    if ph == "tool" and tool:
        return f"{tool['name']}: {tool['label']}"
    return {"idle": "wartet auf deinen nächsten Prompt", "thinking": "denkt nach", "streaming": "streamt Tokens",
            "compacting": "fasst alten Kontext zusammen", "error": a.last_error or "Fehler",
            "retrying": (a.retry or {}).get("error") or "Anbieter sagt nein"}.get(ph, "")

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
        say_at(p, h["head"], "los, Minions!", w=200, h=64, dx=70)
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
    if p.st:
        p.text("Kontext", x + w / 2, y + h + 26, 16, align="center", bold=True)
    if not p.dy:
        return
    if not has_model(a):
        p.poly([(x + 8, y + 30), (x + 6, y + h), (x + w - 6, y + h), (x + w - 8, y + 30)], closed=True, w=2.6, color=GRAY)
        p.text("leer", x + w / 2, y + h / 2 + 5, 15, align="center", color=GRAY)
        return
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
    if guessed:
        label = f"~{fmt_tok(a.ctx_tokens)} Tokens" if a.ctx_tokens else "unbekannt"
    else:
        label = f"{pct:.0f} % von {fmt_tok(a.ctx_window)}"
    p.text(label, x + w / 2, y + h + 46, 14, align="center", color=col if pct > 60 else INK)
    if a.compacting:
        p.text("quetsch!", x + w / 2, y - 52, 18, align="center", bold=True, color=RED)
    elif recent:
        p.text("gequetscht!", x + w / 2, y - 52, 20, align="center", bold=True, color=BLUE)
        if a.compact_before:
            p.text(f"{fmt_tok(a.compact_before)} → {fmt_tok(a.compact_after) if a.compact_after else 'weniger'}", x + w / 2, y - 76, 13, align="center", color=GRAY)
    if a.compact_count:
        p.text(f"{a.compact_count}× gequetscht", x + w / 2, y + h + 64, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Tacho
def draw_gauge(p: Pen, a: Agent, t: float, cx, cy, r=78, vmax=150.0, hist: History | None = None):
    rate = max(0.0, a.rate or 0.0)
    shown = hist.needle(a.key, rate, t) if hist else rate
    if p.st:
        p.arc(cx, cy, r, math.pi, 2 * math.pi, w=2.6)
        p.line(cx - r, cy, cx + r, cy, w=2)
        for i in range(6):
            ang = math.pi + math.pi * i / 5
            p.line(cx + (r - 10) * math.cos(ang), cy + (r - 10) * math.sin(ang), cx + r * math.cos(ang), cy + r * math.sin(ang), w=2, amp=0)
        p.arc(cx, cy, r - 6, math.pi * 1.8, 2 * math.pi, w=5, color=RED)  # roter Bereich
        p.text("Tokens / Sek.", cx, cy - r - 12, 15, align="center", bold=True)
    if not p.dy:
        return
    if not has_model(a):
        p.line(cx, cy, cx - (r - 16), cy, w=3, color=GRAY, amp=0)     # Nadel liegt links am Anschlag
        p.circle(cx, cy, 5, w=2, fill=PAPER, color=GRAY)
        p.text("0", cx, cy + 26, 24, align="center", bold=True, color=GRAY)
        p.text("kein Modell angewählt", cx, cy + 50, 14, align="center", color=GRAY)
        return
    v = shown + (1.5 * math.sin(t * 13) if shown > 0.5 else 0)
    ang = math.pi + math.pi * min(1.0, v / vmax)
    p.line(cx, cy, cx + (r - 16) * math.cos(ang), cy + (r - 16) * math.sin(ang), w=3, color=RED, amp=0)
    p.circle(cx, cy, 5, w=2, fill=INK)
    p.text(f"~{rate:.0f}" if a.rate_est else f"{rate:.0f}", cx, cy + 26, 24, align="center", bold=True)
    p.text(f"gesamt gefressen: {fmt_tok(a.tok_total)}", cx, cy + 50, 14, align="center")
    if a.tok_in or a.tok_out:
        p.text(f"rein {fmt_tok(a.tok_in)} · raus {fmt_tok(a.tok_out)}", cx, cy + 68, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Kurve
def draw_chart(p: Pen, a: Agent, t: float, hist: History | None, x, y, w, h):
    if p.st:
        p.line(x, y + h, x + w, y + h, w=2)
        p.line(x, y + h, x, y, w=2)
        p.poly([(x - 5, y + 8), (x, y), (x + 5, y + 8)], w=2)
        p.poly([(x + w - 8, y + h - 5), (x + w, y + h), (x + w - 8, y + h + 5)], w=2)
        p.text("Kontext im Zeitverlauf", x + w / 2, y - 8, 13, align="center", bold=True)
        p.text("Zeit →", x + w - 4, y + h + 16, 11, align="right", color=GRAY)
    if not p.dy:
        return
    if not has_model(a):
        p.text("(keine Aktivität – kein Modell)", x + w / 2, y + h / 2 + 5, 12, align="center", color=GRAY)
        return
    pts = list(hist.data.get(a.key, [])) if hist else []
    win = a.ctx_window or max([v for _, v in pts] + [1])
    if a.ctx_window:
        p.line(x + 4, y + 12, x + w - 6, y + 12, w=1.2, color=RED, dash=[6, 5])
        p.text("Limit", x + w - 6, y + 8, 11, align="right", color=RED)
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
                p.text("quetsch", mx, y + 18, 11, align="center")
    else:
        p.text("(sammle Daten…)", x + w / 2, y + h / 2 + 5, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Notizblock
KIND_COLOR = {"error": RED, "tool_error": RED, "compact_failed": RED, "compact": BLUE, "retry": RED, "subagent": BLUE, "done": INK, "input": INK}
KIND_MARK = {"error": "!", "tool_error": "!", "compact_failed": "!", "compact": "~", "retry": "↻", "subagent": "»", "done": "✓", "input": "?", "tool": "·"}


def draw_notebook(p: Pen, a: Agent, t: float, x, y, w, h):
    # Spiralblock
    if p.st:
        p.rect(x, y, w, h, lw=2, fill=PAPER)
        for i in range(7):
            p.circle(x + 12 + i * (w - 24) / 6, y, 4, w=1.5)
        p.text("Laborbuch", x + w / 2, y + 26, 14, align="center", bold=True)
    if not p.dy:
        return
    if not has_model(a):
        p.text("(kein Modell angewählt)", x + w / 2, y + 72, 12, align="center", color=GRAY)
        return
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
        p.text("(noch nichts)", x + w / 2, y + 70, 12, align="center", color=GRAY)


# ------------------------------------------------------------------------ Unterer Streifen
def draw_bottom(p: Pen, a: Agent, t: float, x, y, w, h):
    if not has_model(a):
        draw_inactive_rest(p, a, t)
        return
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
    if not run.get("agents"):
        return
    agents = run.get("agents") or []
    total = max(run.get("total", len(agents)), len(agents))
    done, failed = run.get("done", 0), run.get("failed", 0)
    label = f"Subagents ({run.get('mode', '')}): {done}/{total} fertig" + (f", {failed} umgefallen" if failed else "")
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
    if not has_model(a):
        p.text("Tools in dieser Sitzung", x, y + 4, 15, bold=True, color=GRAY)
        p.text("(keine – kein Modell angewählt)", x, y + 40, 13, color=GRAY)
        return
    p.text("Tools in dieser Sitzung", x, y + 4, 15, bold=True)
    items = sorted(a.tool_counts.items(), key=lambda kv: -kv[1])[:5]
    if not items:
        p.text("(noch keine Tools – keine Minions im Einsatz)", x, y + 40, 13, color=GRAY)
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
    if not has_model(a):
        p.text("Hoppla-Zähler", x, y + 4, 15, bold=True, color=GRAY)
        p.text("0 – kein Modell", x + 6, y + 40, 13, color=GRAY)
        return
    p.text("Hoppla-Zähler", x, y + 4, 15, bold=True, color=RED if a.errors else INK)
    if a.errors:
        p.tally(x + 6, y + 40, a.errors, h=20, color=RED, maxn=20)
        recent = a.last_error_at and time.time() - a.last_error_at < 30
        p.lines(a.last_error, x, y + 64, 11, w - 10, max_lines=2, color=RED if recent else GRAY, jitter=0.4, upper=False)
    else:
        p.text("0 – verdächtig ruhig", x, y + 36, 13, color=GRAY)
