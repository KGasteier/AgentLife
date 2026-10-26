"""Zeichen-Regressionen: Schrift, Blasentext, Sitzhaltung (python3 -m unittest discover -s tests)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cairo  # noqa: E402

from agentscope import scene, sketch  # noqa: E402
from agentscope.sketch import LEG, Pen  # noqa: E402

LONG = ("Please refactor the entire authentication module so that it uses the new token store and also "
        "write migration notes for the ops team, Supercalifragilisticexpialidociouslylongidentifier included")


def pen():
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
    return Pen(cairo.Context(surf))


class FontTest(unittest.TestCase):
    def test_kalam_is_bundled_and_resolves(self):
        self.assertTrue(sketch.register_fonts())
        self.assertEqual(sketch.hand_font(), "Kalam")
        p = pen()
        # Wenn Cairo Kalam nicht fände, fiele es auf die Grundschrift zurück → gleiche Breiten.
        self.assertNotAlmostEqual(p.text_width("hello agents", 20, hand=True, upper=False),
                                  p.text_width("hello agents", 20, hand=False, upper=False), places=1)

    def test_advance_cache_separates_fonts(self):
        p = pen()
        a = p.text_width("W", 30, hand=True)
        b = p.text_width("W", 30, hand=False)
        self.assertEqual(a, p.text_width("W", 30, hand=True))
        self.assertNotEqual(a, b)


class BubbleTest(unittest.TestCase):
    """Regression: Text in der Gedankenblase lief über den Rand."""

    def assert_inside(self, g, text):
        size, rows, _bw, bh = g["block"]
        p = pen()
        lh = 1.2
        y0 = g["cy"] - bh / 2 + size * 0.78
        for i, row in enumerate(rows):
            w = p.text_width(row, size, hand=True, upper=False) + 2      # +2: Zeichen-Jitter
            base = y0 + i * size * lh
            for x in (g["cx"] - w / 2, g["cx"] + w / 2):
                for y in (base - size * 0.8, base + size * 0.3):
                    e = ((x - g["cx"]) / g["a"]) ** 2 + ((y - g["cy"]) / g["b"]) ** 2
                    self.assertLess(e, 1.0, f"{row!r} ragt aus der Blase ({text[:20]}…)")

    def test_text_stays_inside_cloud(self):
        for text in ("hmm", "build an animated xkcd-style screensaver", LONG, "x" * 200):
            for (w, h) in ((330, 170), (240, 110), (200, 90)):
                g = pen().think(text, 220, 140, w, h, (200, 300), size=19)
                self.assert_inside(g, text)
                self.assertLessEqual(len(g["block"][1]), 3)

    def test_long_text_is_ellipsized(self):
        g = pen().think(LONG, 220, 140, 330, 170, (200, 300))
        self.assertTrue(g["block"][1][-1].endswith("…"))

    def test_cloud_outer_size_within_requested_box(self):
        g = pen().think(LONG, 220, 140, 330, 170, (200, 300))
        self.assertLessEqual(2 * (g["a"] + g["rb"]), 330)
        self.assertLessEqual(2 * (g["b"] + g["rb"]), 170)


class PoseTest(unittest.TestCase):
    """Regression: die Figur schwebte über dem Stuhl."""

    def test_seated_on_chair(self):
        p = pen()
        seat_y = scene.FLOOR - scene.SEAT_H
        hip = (scene.ACTOR_X, seat_y - 3)
        h = scene.seated(p, hip, hands=((scene.ACTOR_X + 48, scene.FLOOR - scene.DESK_H - 5),) * 2)
        self.assertLessEqual(abs(h["hip"][1] - seat_y), 4)                    # Gesäß auf der Sitzfläche
        self.assertLess(abs(scene.ACTOR_X - 6 - h["hip"][0]), 22)            # über dem Sitz, nicht daneben
        for f in ("fl", "fr"):
            self.assertAlmostEqual(h[f][1], scene.FLOOR, delta=1.0)          # Füße am Boden
        for k in ("kl", "kr"):
            self.assertLess(abs(h[k][1] - h["hip"][1]), 10)                   # Oberschenkel ~waagerecht
            self.assertGreater(h[k][0], h["hip"][0] + LEG * 0.8)              # Knie zeigen nach vorn

    def test_hands_reach_targets(self):
        p = pen()
        hip = (scene.ACTOR_X, scene.FLOOR - scene.SEAT_H - 3)
        target = (scene.ACTOR_X + 48, scene.FLOOR - scene.DESK_H - 5)
        h = scene.seated(p, hip, hands=(target, target))
        self.assertLess(math.dist(h["hl"], target), 1.5)

    def test_standing_feet_on_floor(self):
        h = scene.standing(pen(), 300)
        for f in ("fl", "fr"):
            self.assertAlmostEqual(h[f][1], scene.FLOOR, delta=1.0)

    def test_all_phases_render(self):
        from agentscope import model
        for t in (1, 7, 14, 21, 30, 35, 46):
            for a in model.demo_agents(float(t)):
                scene.draw_actor(pen(), a, float(t))




class NeedleTest(unittest.TestCase):
    def test_needle_eases_towards_target(self):
        from agentscope.scene import History
        h = History()
        v0 = h.needle("a", 0, 0.0)
        v1 = h.needle("a", 100, 0.3)
        for i in range(1, 31):
            v2 = h.needle("a", 100, 0.3 + i * 0.1)
        self.assertEqual(v0, 0.0)
        self.assertTrue(0 < v1 < 100)
        self.assertGreater(v2, 95)

    def test_first_value_shown_immediately(self):
        from agentscope.scene import History
        self.assertEqual(History().needle("a", 42, 5.0), 42)


class MotionTest(unittest.TestCase):
    """Regression: Hammer schwang starr wie ein Pendel, Tippen war ein Zittern, Minions hampelten alle gleich."""

    def test_hammer_hits_box_and_cocks_overhead(self):
        sh = (130.0, 300.0)
        target = (53.0, 317.0)
        hit = scene.hammer_swing(0.65 * scene.HAMMER_PERIOD)
        hand, ang = scene.hammer_grip(sh, target, hit)
        a = math.radians(ang)
        head = (hand[0] + scene.HAMMER_LEN * math.sin(a), hand[1] - scene.HAMMER_LEN * math.cos(a))
        self.assertLess(math.dist(head, target), 8)                         # Kopf trifft die Kiste
        top = scene.hammer_swing(0.47 * scene.HAMMER_PERIOD)
        hand, _ = scene.hammer_grip(sh, target, top)
        self.assertLess(hand[1], sh[1] - 25)                                 # ausgeholt: Hand über dem Kopf
        self.assertEqual(top["cock"], 1.0)

    def test_hammer_strike_faster_than_windup(self):
        P = scene.HAMMER_PERIOD
        def speed(u0, u1):
            return abs(scene.hammer_swing(u1 * P)["swing"] - scene.hammer_swing(u0 * P)["swing"]) / (u1 - u0)
        self.assertGreater(speed(0.56, 0.60), 3 * speed(0.15, 0.25))

    def test_typing_alternates_and_stays_on_keys(self):
        keys = (238.0, 311.0)
        moved = {"l": 0, "r": 0}
        prev = None
        for i in range(200):
            l, r, _, _ = scene.typing_hands(i * 0.02, 40, keys)
            for hnd in (l, r):
                self.assertLess(math.dist(hnd, keys), 40)
            if prev:
                moved["l"] += math.dist(l, prev[0]) > 0.5
                moved["r"] += math.dist(r, prev[1]) > 0.5
            prev = (l, r)
        self.assertGreater(moved["l"], 20)
        self.assertGreater(moved["r"], 20)

    def test_every_dance_keeps_a_foot_down_and_limbs_reachable(self):
        from agentscope import dance
        from agentscope.sketch import ARM
        s, base = 0.6, 300.0
        for style in dance.DANCES:
            lowest_ok = 0
            for i in range(60):
                d = dance.pose(style, i * 0.05, 100, base, s)
                f = pen().figure(*d["hip"], s=s, lean=d["lean"], flip=d["flip"], hands=d["hands"], feet=d["feet"], splay=d["splay"])
                low = max(f["fl"][1], f["fr"][1])
                self.assertLessEqual(low, base + 1.0, style)                 # nie im Boden
                lowest_ok += low > base - 0.3 * LEG * s
                for hk, tgt in (("hl", d["hands"][0]), ("hr", d["hands"][1])):
                    self.assertLess(math.dist(f[hk], tgt), 2.0, style)       # Hände erreichen ihr Ziel
            self.assertGreater(lowest_ok, 40, style)                         # meistens Bodenkontakt

    def test_neighbours_dance_differently(self):
        from agentscope import dance
        styles = [dance.pick("worker", i, 0) for i in range(4)]
        self.assertEqual(len(set(styles)), 4)
        self.assertNotEqual(dance.pick("worker", 0, 0), dance.pick("worker", 0, dance.DANCE_SWITCH_S))


if __name__ == "__main__":
    unittest.main()
