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


class VarietyTest(unittest.TestCase):
    """0.5.0: mehr Abwechslung – Varianten, Siegestanz, Leerlauf-Szenen."""

    def setUp(self):
        from agentscope import acts
        self.acts = acts
        acts.FORCE.clear()

    def test_variants_change_over_time_and_never_repeat_directly(self):
        a = self.acts
        for name, n in (("thinking", 4), ("idle", 9)):
            seq = [a.variant("k", name, i * a.VARIANT_S + 1, n) for i in range(60)]
            self.assertGreaterEqual(len(set(seq)), n - 1, name)
            self.assertTrue(all(x != y for x, y in zip(seq, seq[1:])), name)
        self.assertEqual(a.variant("k", "x", 33.0, 4), a.variant("k", "x", 33.0, 4))      # deterministisch
        self.assertNotEqual([a.variant("a", "idle", i * 14.0, 9) for i in range(9)],
                            [a.variant("b", "idle", i * 14.0, 9) for i in range(9)])        # Panels verschieden

    def test_every_variant_renders_in_every_phase(self):
        from agentscope import model
        a = self.acts
        base = model.demo_agents(14.0)[0]
        cases = [(ph, None) for ph in ("thinking", "streaming", "compacting", "error", "retrying", "idle")]
        cases += [("tool", n) for n in ("bash", "read", "edit", "subagent", "grep")]
        for ph, tool in cases:
            base.phase = ph
            base.tools = [{"name": tool, "label": "x", "started": 0}] if tool else []
            base.retry = {"attempt": 1, "max": 3, "error": "529"}
            base.idle_since = None
            for v in range(10):
                a.FORCE["variant"] = v
                for t in (0.5, 3.3, 9.1):
                    scene.draw_actor(pen(), base, t)
        a.FORCE.clear()

    def test_finished_agent_dances_on_table_then_returns_to_idle_scenes(self):
        import time
        from agentscope import model
        a = self.acts
        ag = model.demo_agents(14.0)[0]
        ag.phase, ag.tools = "idle", []
        ag.idle_since = time.time() - 3
        for i in range(4):
            ag.turn = i
            self.assertIn(a.finale_style(ag), dance_mod().FINALE)
        self.assertEqual({a.finale_style(type("A", (), {"key": "x", "turn": i})()) for i in range(4)}, set(dance_mod().FINALE))
        ag.idle_since = time.time() - a.FINALE_S - 1

    def test_history_detects_work_to_idle_transition(self):
        import time
        from agentscope import model
        h = scene.History()
        ag = model.demo_agents(14.0)[0]
        ag.phase, ag.idle_since = "streaming", None
        h.sample([ag], time.time())
        self.assertIsNone(ag.idle_for)
        ag.phase = "idle"
        h.sample([ag], time.time())
        self.assertLess(ag.idle_for, 1.0)                       # frisch fertig → tanzt
        ag2 = model.demo_agents(14.0)[2]                         # schon beim Start untätig
        ag2.idle_since = None
        h.sample([ag2], time.time())
        self.assertIsNone(ag2.idle_for)

    def test_hopak_squats_and_kicks(self):
        from agentscope import dance
        lows = [dance.pose("hopak", i * 0.05, 100, 300, 0.85)["hip"][1] for i in range(180)]
        self.assertGreater(max(lows) - min(lows), 12)            # Hocke ↔ Sprung
        self.assertGreater(max(lows), 300 - 1.5 * LEG * 0.85)    # tief in der Hocke
        xs = [dance.pose("hopak", i * 0.05, 100, 300, 0.85)["feet"][0][0] for i in range(120)]
        self.assertGreater(max(xs) - min(xs), 20)                # Bein wird ausgestreckt

    def test_empty_scenes_rotate_and_render(self):
        a = self.acts
        seen = {a.variant("leer", "szene", i * a.EMPTY_SLOT_S + 1, a.EMPTY_SCENES, a.EMPTY_SLOT_S) for i in range(30)}
        self.assertEqual(seen, set(range(a.EMPTY_SCENES)))
        for v in range(a.EMPTY_SCENES):
            a.FORCE["variant"] = v
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
            scene.render(cairo.Context(surf), 1000, 560, [], 3.0, None)
        a.FORCE.clear()

class StayInActorAreaTest(unittest.TestCase):
    """Regression 0.5.1: der Papierkorb stand über dem Kontextglas (x≈475). Varianten bleiben links von x=450."""

    def test_no_variant_paints_into_the_jar_area(self):
        import time
        from agentscope import acts, model
        ag = model.demo_agents(14.0)[0]
        ag.idle_since = time.time() - 100
        ag.retry = {"attempt": 1, "max": 3, "error": "x"}
        bad = []
        cases = [(ph, None) for ph in ("thinking", "streaming", "compacting", "error", "retrying", "idle")]
        cases += [("tool", n) for n in ("bash", "read", "edit", "subagent", "grep")]
        for ph, tool in cases:
            ag.phase = ph
            ag.tools = [{"name": tool, "label": "x", "started": 0}] if tool else []
            kind = scene.tool_kind(tool) if tool else None
            for v in range(1, 40):
                acts.FORCE["variant"] = v
                for t in (0.5, 2.0, 3.3, 4.2, 5.5, 7.7, 9.1):
                    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
                    cr = cairo.Context(surf)
                    cr.set_source_rgb(1, 1, 1)
                    cr.paint()
                    cx, fl = scene.ACTOR_X, scene.FLOOR
                    dk, st = fl - scene.DESK_H, fl - scene.SEAT_H
                    c = acts.context(cx, fl, dk, st, (cx, st - 3), cx + 70, (cx + 48, dk - 3))
                    acts.draw(Pen(cr), ag, ph, kind, t, c)
                    surf.flush()
                    buf, stride = surf.get_data(), surf.get_stride()
                    for y in range(0, 560, 2):
                        row = buf[y * stride + 452 * 4: y * stride + 700 * 4]
                        if any(b != 255 for b in row):
                            bad.append((ph, tool, v, t))
                            break
        acts.FORCE.clear()
        self.assertEqual(sorted(set((b[0], b[1], b[2]) for b in bad), key=str), [])

class AmbientTest(unittest.TestCase):
    def test_ambient_creatures_all_appear_and_stay_left_of_the_jar(self):
        from agentscope import acts
        kinds = set()
        for key in ("a", "b", "c", "d", "e", "f"):
            for slot in range(12):
                for u in range(4, 28, 2):
                    t = slot * acts.AMBIENT_SLOT_S + u + 4
                    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
                    cr = cairo.Context(surf)
                    cr.set_source_rgb(1, 1, 1)
                    cr.paint()
                    acts.ambient(Pen(cr), key, t)
                    surf.flush()
                    buf, st = surf.get_data(), surf.get_stride()
                    if any(b != 255 for b in buf[:st * 560]):
                        kinds.add(acts._slot_kind(key, slot))
        self.assertEqual(kinds, {0, 1, 2, 3, 4, 5})

    def test_guest_and_postman_are_idle_scenes(self):
        from agentscope import acts
        names = {f.__name__ for f in acts.ACTS["idle"] if f}
        self.assertTrue({"idle_guest", "idle_postman"} <= names)
        self.assertIn("Claude", acts.GUESTS[0][0])

def dance_mod():
    from agentscope import dance
    return dance

if __name__ == "__main__":
    unittest.main()


class NoBoldBubblesTest(unittest.TestCase):
    """Wunsch 0.6.0: Comicschrift in Sprechblasen nie fett – auch wenn ein Aufrufer bold=True übergibt."""

    def test_speech_bubble_never_uses_bold(self):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 600, 300)
        p = Pen(cairo.Context(surf))
        seen = []
        orig = p._font

        def spy(size, bold=False, hand=False):
            seen.append(bold)
            return orig(size, bold, hand)

        p._font = spy
        p.say("AAAAA!", 200, 100, 200, 70, (210, 160), size=24, bold=True)
        scene.say_at(p, (200, 200), "ES BRENNT!", w=190, h=70, size=24, bold=True)
        self.assertTrue(seen)
        self.assertFalse(any(seen), "Sprechblase hat fette Schrift benutzt")


class PopCultureAndGrowthTest(unittest.TestCase):
    def _blank(self):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
        cr = cairo.Context(surf)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        return surf, cr

    def _ink(self, surf):
        surf.flush()
        return sum(1 for b in surf.get_data() if b != 255)

    def test_new_idle_scenes_registered(self):
        from agentscope import acts
        names = {f.__name__ for f in acts.ACTS["idle"] if f}
        need = {"idle_trek", "idle_zombies", "idle_starwars", "idle_lotr", "idle_coffeeduo", "idle_flirt",
                "idle_kids", "idle_protest", "idle_cosplay", "idle_taichi", "idle_karate"}
        self.assertTrue(need <= names, need - names)

    def test_overgrowth_grows_with_idle_time(self):
        import time
        from agentscope import acts, model
        ag = model.demo_agents(14.0)[0]
        ag.phase = "idle"
        cx, fl = scene.ACTOR_X, scene.FLOOR
        dk, st = fl - scene.DESK_H, fl - scene.SEAT_H
        c = acts.context(cx, fl, dk, st, (cx, st - 3), cx + 70, (cx + 48, dk - 3))
        inks = []
        for g in (0.0, 0.5, 1.0):
            acts.FORCE["grow"] = g
            surf, cr = self._blank()
            acts.overgrowth(Pen(cr), ag, 3.0, c)
            inks.append(self._ink(surf))
        acts.FORCE.pop("grow", None)
        self.assertLess(inks[0], inks[1])
        self.assertLess(inks[1], inks[2])

    def test_drool_runs_down(self):
        from agentscope import acts
        a, b = [], []
        for k, out in ((0.1, a), (1.0, b)):
            surf, cr = self._blank()
            acts._drool(Pen(cr), 100, 100, 200, k)
            out.append(self._ink(surf))
        self.assertLess(a[0], b[0])

    def test_tokens_land_in_the_maul(self):
        import time
        from agentscope import model
        ag = model.demo_agents(7.0)[0]
        ag.phase, ag.rate = "streaming", 60
        acts_ = __import__("agentscope.acts", fromlist=["x"])
        acts_.FORCE["variant"] = 0
        surf, cr = self._blank()
        scene.draw_actor(Pen(cr), ag, 3.3)
        self.assertTrue(hasattr(scene, "MAUL"))
        mx, my = scene.MAUL
        surf.flush()
        buf, st = surf.get_data(), surf.get_stride()
        self.assertTrue(any(buf[int(my) * st + 4 * x] != 255 for x in range(int(mx) - 25, int(mx) + 25)))
        acts_.FORCE.pop("variant", None)


class Wunsch080Test(unittest.TestCase):
    """Wünsche 0.8.0: Farbe nur im Titelkasten, Maul rechts mit gelb/grün, Grundlinien-Wackeln,
    nie dieselbe Reihenfolge, Protest-Antwort, neue Memes/Challenges."""

    def test_regression_only_the_title_box_is_tinted(self):
        """Regression 0.8.0: vorher wurde jede Skizzenlinie je Harness eingefärbt; jetzt nur der Titelkasten."""
        import cairo as c
        from agentscope import model
        ag = model.Agent(key="k", title="Vault", source="log", harness="claude", phase="idle", updated=1.0)
        surf = c.ImageSurface(c.FORMAT_RGB24, 1000, 560)
        p = Pen(c.Context(surf))
        scene.render_panel(p, ag, 3.0, None)
        self.assertEqual(scene.INK, p.ink, "Skizzenstift darf nicht eingefärbt sein")
        tint = scene.harness_tint(ag)
        self.assertNotEqual(tint, (1.0, 1.0, 1.0))
        self.assertNotEqual(tint, scene.harness_tint(model.Agent(key="k", title="t", source="log", harness="pi")))

    def test_regression_title_always_carries_session_info(self):
        """Regression 0.8.0: ohne Skill und Sitzungsnamen blieb der Titel bei „?“. Jetzt steht Sitzungsinfo dort."""
        from agentscope import model
        for key in ("claude:/home/kg/.claude/projects/x/3f2a9c11.jsonl", "codex:", "live:1"):
            a = model.Agent(key=key, title="", source="log")
            t = scene.panel_title(a)
            self.assertNotEqual(t, "pi · ?", t)
            self.assertTrue(len(t.split("·", 1)[1].strip()) >= 5, t)

    def test_regression_tokens_are_yellow_in_and_green_out(self):
        """Regression 0.8.0: Münzen waren alle gelb und flogen quer durchs Panel; jetzt gelb hinein, grün hinaus, lokal."""
        import time
        from agentscope import model
        ag = model.demo_agents(7.0)[0]
        ag.phase, ag.rate = "streaming", 60
        acts_ = __import__("agentscope.acts", fromlist=["x"])
        acts_.FORCE["variant"] = 0
        colors = []
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)
        ctx = cairo.Context(surf)
        ctx.set_source_rgb(1, 1, 1)
        ctx.paint()
        p = Pen(ctx)
        orig = p.coin

        def spy(x, y, r=7, color=scene.INK, fill=(1.0, 0.93, 0.55)):
            colors.append((round(x), fill))
            return orig(x, y, r, color, fill)

        p.coin = spy
        scene.draw_actor(p, ag, 3.3)
        acts_.FORCE.pop("variant", None)
        self.assertIn(scene.TOK_IN, [c for _, c in colors])
        self.assertIn(scene.TOK_OUT, [c for _, c in colors])
        self.assertTrue(all(abs(x - scene.MAUL[0]) < 90 for x, _ in colors), colors)

    def test_regression_comic_font_wobbles_on_the_baseline(self):
        """Regression 0.8.0: die Comicschrift saß exakt auf der Grundlinie und wirkte gesetzt."""
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 800, 300)
        p = Pen(cairo.Context(surf))
        p._font(20, False, True)
        txt = "Hallo Welt, das ist ein langer Satz fuer die Grundlinie"
        hand = [g[2] for g in p._laid_out(txt, 100, 100, 20, 1.0, True)]
        plain = [g[2] for g in p._laid_out(txt, 100, 100, 20, 1.0, False)]
        self.assertNotEqual(hand, plain, "Comicschrift wackelt nicht wie die Unterzeile")
        avg = lambda v: sum(abs(y - 100) for y in v) / len(v)
        self.assertGreater(avg(hand), avg(plain))

    def test_regression_animation_order_varies_between_runs(self):
        """Regression 0.8.0: jede Sitzung spielte Szenen in derselben Reihenfolge; jetzt mischt RUN_SEED mit."""
        import importlib
        from agentscope import acts
        seqs = set()
        for seed in (1, 2, 3, 4):
            acts.RUN_SEED = seed
            acts._perm.cache_clear() if hasattr(acts._perm, "cache_clear") else None
            seqs.add(tuple(acts.variant("k", "idle", i * 14.0, 34) for i in range(10)))
        self.assertGreater(len(seqs), 1, "Reihenfolge ist unabhängig vom Lauf identisch")

    def test_protesters_answer_ich_mach_nur_meinen_job(self):
        from agentscope import quips
        self.assertIn("Ich mach nur meinen Job.", quips.QUIPS["protest_reply"])
        self.assertNotIn("Ich bin nur ein Strichmännchen!", str(quips.QUIPS))

    def test_regression_quips_vary_and_keep_the_original(self):
        """Regression 0.8.1: fester Satz für Memes, aber nie zweimal dieselbe Antwort."""
        from agentscope import quips
        seen = {quips.line("protest_reply", "k", i) for i in range(30)}
        self.assertGreater(len(seen), 1, "Antworten wechseln nicht")
        self.assertEqual("Live long and prosper.", quips.line("spock_greeting", "k", 0))
        self.assertIn("Möge die Macht mit dir sein.", quips.QUIPS["spock_reply"])
        for key in ("spock_reply", "67_reply", "protest_reply", "fine", "jedi"):
            self.assertGreaterEqual(len(quips.QUIPS[key]), 4, key)

    def test_spock_greeting_reply_is_star_wars(self):
        """Wunsch: Auf Spocks Gruß antwortet das Gegenüber „Möge die Macht mit dir sein“."""
        from agentscope import acts
        import inspect
        src = inspect.getsource(acts.idle_trek)
        self.assertIn('"spock_greeting"', src)
        self.assertIn('"spock_reply"', src)
        self.assertIn("Möge die Macht mit dir sein.", acts.quips.QUIPS["spock_reply"])

    def test_new_meme_and_challenge_scenes_registered(self):
        from agentscope import acts
        names = {f.__name__ for f in acts.ACTS["idle"] if f}
        self.assertTrue({"idle_67", "idle_thisisfine", "idle_distracted"} <= names)
        self.assertTrue({"idle_planking", "idle_mannequin", "idle_icebucket"} <= names)

    def test_default_fps_is_eight(self):
        import inspect
        from agentscope import app
        self.assertIn("default=8", inspect.getsource(app.main))


class ModelThreadTest(unittest.TestCase):
    """Wunsch 0.8.2: pinkes Gehirn im Titel, feiner Faden zum Kopf, leblose Puppe ohne Modell."""

    def _blank(self, w=1000, h=560):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
        cr = cairo.Context(surf)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        return surf, cr

    def _pink(self, surf, box=None):
        """Zählt rosa Pixel (R deutlich > G, B dazwischen)."""
        surf.flush()
        buf, st = surf.get_data(), surf.get_stride()
        x0, y0, x1, y1 = box or (0, 0, surf.get_width(), surf.get_height())
        n = 0
        for y in range(y0, y1):
            row = y * st
            for x in range(x0, x1):
                i = row + 4 * x
                r, g, b = buf[i + 2], buf[i + 1], buf[i]
                if r > 170 and r - g > 55 and 60 < b < r:
                    n += 1
        return n

    def test_brain_sits_left_of_the_model_name(self):
        from agentscope import model
        a = model.demo_agents(3.0)[0]
        p = Pen(cairo.Context(cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 560)))
        tw = p.text_width(scene.panel_title(a), 22, bold=True)
        bx, by = scene.brain_pos(a, tw)
        self.assertLess(bx, tw + 66, "Gehirn sitzt rechts vom Modelltext")
        self.assertLess(by, 30, "Gehirn sitzt nicht im Titelbereich")

    def test_regression_thread_follows_the_head(self):
        """Regression 0.8.2: ohne Faden gab es keine Verbindung zwischen Modell und Figur."""
        from agentscope import model
        surf, cr = self._blank()
        p = Pen(cr)
        a = model.demo_agents(3.0)[0]
        a.phase, a.model = "streaming", "claude-opus-5-5"
        scene.render_panel(p, a, 3.0, None)
        # Faden: rosa Pixel im Band zwischen Titel (y≈21) und Figur, links der Panelmitte
        self.assertGreater(self._pink(surf, (150, 30, 300, 300)), 20, "kein pinker Faden sichtbar")

    def test_regression_no_model_shows_lifeless_puppet_and_broken_thread(self):
        """Regression 0.8.2: ohne Modell blieb die Figur fröhlich sitzen; jetzt schlaffe Puppe, gerissener Faden."""
        from agentscope import model
        a = model.demo_agents(3.0)[0]
        a.model = ""
        self.assertFalse(scene.has_model(a))
        surf, cr = self._blank()
        p = Pen(cr)
        scene.render_panel(p, a, 3.0, None)
        src = open(scene.__file__).read()
        self.assertIn("draw_slumped", src)
        self.assertIn("kein Modell · getrennt", src)
        # gerissener Faden: rosa Pixel nur direkt unter dem Gehirn, nicht bis zur Figur
        tw = p.text_width(scene.panel_title(a), 22, bold=True)
        bx, by = scene.brain_pos(a, tw)
        self.assertGreater(self._pink(surf, (int(bx) - 18, int(by) + 4, int(bx) + 18, int(by) + 70)), 5, "gerissener Faden fehlt")
        self.assertLess(self._pink(surf, (150, 130, 440, 340)), 5, "Faden hängt trotz Trennung zur Figur")

    def test_thread_survives_walking_and_jumping_poses(self):
        from agentscope import model
        a = model.demo_agents(14.0)[0]
        a.phase, a.model = "error", "gpt-6.1-sol"
        surf, cr = self._blank()
        p = Pen(cr)
        scene.render_panel(p, a, 3.0, None)
        self.assertGreater(self._pink(surf, (150, 30, 420, 340)), 20)
