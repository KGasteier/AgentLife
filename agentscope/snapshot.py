"""Rendert ein PNG ohne Fenster (für Tests, Screenshots und Vorschau).

    python3 -m agentscope.snapshot out.png [--demo] [--t 12.5] [--size 1920x1080] [--panels N]
"""

from __future__ import annotations

import argparse
import time

import cairo

from . import model, scene


def render_png(path: str, agents, t: float, W: int = 1920, H: int = 1080, hist=None, clock="13:37"):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    cr = cairo.Context(surf)
    scene.render(cr, W, H, agents, t, hist, clock=clock)
    surf.write_to_png(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--t", type=float, default=7.0)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--panels", type=int, default=0, help="Demo: Anzahl Panels (0 = alle)")
    a = ap.parse_args(argv)
    W, H = (int(v) for v in a.size.split("x"))
    agents = model.demo_agents(a.t) if a.demo else model.collect()
    if a.panels:
        agents = agents[: a.panels]
    hist = scene.History()
    if a.demo:
        # synthetische Kurve mit zwei Kompaktierungen
        now = time.time()
        for i in range(300):
            ts = now - 300 + i
            for ag in agents:
                v = (i % 120) / 120 * (ag.ctx_window or 1) * 0.9 + 5000
                hist.data.setdefault(ag.key, __import__("collections").deque()).append((ts, v))
            if i % 120 == 0 and i:
                hist.marks.setdefault(agents[0].key, __import__("collections").deque()).append(ts)
    else:
        hist.sample(agents, time.time())
    render_png(a.out, agents, a.t, W, H, hist)
    print(a.out)


if __name__ == "__main__":
    main()
