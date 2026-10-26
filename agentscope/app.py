"""Vollbild-Screensaver (GTK4 + Cairo).

    python3 -m agentscope.app [--demo] [--windowed] [--fps 12]

Beenden: beliebige Taste, Mausklick oder deutliche Mausbewegung (wie ein Screensaver).
`--windowed` lässt das Fenster offen und reagiert nur auf q/Esc (zum Daneben-Arbeiten).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import model, scene, sketch  # noqa: E402

APP_ID = "org.omarchy.agentscope"
POLL_S = 0.5
MOVE_THRESHOLD = 40  # px bis eine Mausbewegung beendet
GRACE_S = 1.0  # Eingaben direkt nach dem Start ignorieren (Tastenkürzel loslassen)


class Scope(Gtk.ApplicationWindow):
    def __init__(self, app, demo: bool, windowed: bool, fps: int):
        super().__init__(application=app, title="agentscope")
        self.demo = demo
        self.windowed = windowed
        self.t0 = time.monotonic()
        self.started = time.monotonic()
        self.agents: list = []
        self.hist = scene.History()
        self.layer = scene.StaticLayer()
        self.last_frame = 0.0
        self.frame_dt = 1.0 / max(1, fps)
        self.last_poll = 0.0
        self.motion_origin = None

        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.on_draw)
        self.set_child(self.area)
        self.set_default_size(1600, 900)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.maybe_quit(why="click"))
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.on_motion)
        self.add_controller(motion)

        if not windowed:
            self.fullscreen()
            self.set_cursor_from_name("none")
        self.poll()
        # Takt am Frame-Clock des Compositors: gezeichnet wird höchstens fps-mal pro Sekunde, nie zwischen zwei Frames
        self.add_tick_callback(self.tick)

    # -------------------------------------------------------------- Daten
    def poll(self):
        now = time.time()
        try:
            self.agents = model.demo_agents(time.monotonic() - self.t0) if self.demo else model.collect(now)
        except Exception as e:  # Anzeige darf nie abstürzen
            print(f"agentscope: poll failed: {e}", file=sys.stderr)
        self.hist.sample(self.agents, now)
        self.last_poll = time.monotonic()

    def tick(self, _widget, _clock):
        now = time.monotonic()
        if now - self.last_frame < self.frame_dt * 0.9:
            return GLib.SOURCE_CONTINUE
        self.last_frame = now
        if self.demo or now - self.last_poll >= POLL_S:
            self.poll()
        self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def on_draw(self, _area, cr, w, h):
        sc = self.area.get_scale_factor()
        if sc != sketch.HINT_SCALE:
            sketch.HINT_SCALE = float(sc)
        t0 = time.process_time()
        scene.render_cached(cr, w, h, self.agents, time.monotonic() - self.t0, self.hist, self.layer)
        if os.environ.get("AGENTSCOPE_DEBUG"):
            self._dbg = getattr(self, "_dbg", [0, 0.0, time.monotonic()])
            self._dbg[0] += 1
            self._dbg[1] += time.process_time() - t0
            if time.monotonic() - self._dbg[2] >= 5:
                n = self._dbg[0]
                print(f"agentscope: {n / 5:.1f} fps, draw {1000 * self._dbg[1] / n:.1f} ms, static renders {self.layer.renders}, {w}x{h}", file=sys.stderr)
                self._dbg = [0, 0.0, time.monotonic()]

    # -------------------------------------------------------------- Eingabe
    def maybe_quit(self, force=False, why="?"):
        if force or (not self.windowed and time.monotonic() - self.started > GRACE_S):
            if os.environ.get("AGENTSCOPE_DEBUG"):
                print(f"agentscope: quit ({why}) after {time.monotonic() - self.started:.1f}s", file=sys.stderr)
            self.get_application().quit()

    def on_key(self, _c, keyval, _code, _state):
        name = (Gtk.accelerator_name(keyval, 0) or "").lower()
        if name in ("escape", "q"):
            self.maybe_quit(force=True, why=f"key {name}")
        else:
            self.maybe_quit(why=f"key {name}")
        return True

    def on_motion(self, _c, x, y):
        if self.windowed or time.monotonic() - self.started < GRACE_S:
            self.motion_origin = (x, y)
            return
        if self.motion_origin is None:
            self.motion_origin = (x, y)
        elif abs(x - self.motion_origin[0]) + abs(y - self.motion_origin[1]) > MOVE_THRESHOLD:
            self.maybe_quit(why=f"motion {self.motion_origin} -> {(round(x), round(y))}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agentscope")
    ap.add_argument("--demo", action="store_true", help="synthetische Daten statt echter pi-Prozesse")
    ap.add_argument("--windowed", action="store_true", help="Fenster statt Vollbild, beenden nur mit q/Esc")
    ap.add_argument("--fps", type=int, default=8)
    a = ap.parse_args(argv)
    app = Gtk.Application(application_id=APP_ID)
    app.connect("activate", lambda ap_: Scope(ap_, a.demo, a.windowed, a.fps).present())
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
