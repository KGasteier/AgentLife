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


if __name__ == "__main__":
    unittest.main()
