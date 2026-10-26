"""Tests der Datenschicht und der Szene (python3 -m unittest discover -s tests)."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cairo  # noqa: E402

from agentscope import model, scene  # noqa: E402


def state(pid, ppid=1, **kw):
    s = {"v": 1, "pid": pid, "ppid": ppid, "started": pid, "updated": 0, "cwd": "/home/x/Work/proj", "sessionFile": f"/s/{pid}.jsonl",
         "sessionName": None, "model": "udk/cc/opus", "phase": "tool", "prompt": "do it", "turn": 3,
         "context": {"tokens": 5000, "window": 100000, "percent": 5.0}, "tokens": {"input": 10, "output": 5, "cacheRead": 0, "total": 15, "rateOut": 7},
         "tools": [{"id": "a", "name": "bash", "label": "ls", "started": 0}], "toolCounts": {"bash": 1}, "errors": 0, "lastError": None,
         "compaction": {"active": False, "reason": "", "tokensBefore": None, "tokensAfter": None, "at": 0, "count": 0},
         "retry": None, "subagentRuns": [], "events": []}
    s.update(kw)
    return s


class LiveTest(unittest.TestCase):
    def test_children_are_grouped_and_dead_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            for s in (state(100), state(200, ppid=100), state(300), state(999)):
                with open(os.path.join(d, f"{s['pid']}.json"), "w") as f:
                    json.dump(s, f)
            with open(os.path.join(d, "broken.json"), "w") as f:
                f.write("{nope")
            agents, sessions = model.read_live(d, alive=lambda p: p != 999)
            self.assertEqual([a.key for a in agents], ["pid:100", "pid:300"])
            self.assertEqual(len(agents[0].children), 1)
            self.assertIn("/s/200.jsonl", sessions)
            self.assertEqual(agents[0].title, "Work/proj")
            self.assertEqual(agents[0].model, "opus")


def jl(*objs):
    return [json.dumps(o) for o in objs]


class SessionTest(unittest.TestCase):
    def test_reconstruct_from_log(self):
        lines = jl(
            {"type": "session", "cwd": "/home/x/Work/proj"},
            {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "fix the bug"}]}},
            {"type": "message", "message": {"role": "assistant", "model": "m/x", "usage": {"input": 100, "output": 10, "totalTokens": 110},
                                            "content": [{"type": "toolCall", "id": "t1", "name": "bash", "arguments": {"command": "false"}},
                                                        {"type": "toolCall", "id": "t2", "name": "read", "arguments": {"path": "/a/b.py"}}]}},
            {"type": "message", "message": {"role": "toolResult", "toolCallId": "t1", "toolName": "bash", "isError": True, "content": [{"type": "text", "text": "exit 1"}]}},
            {"type": "compaction", "tokensBefore": 150000},
            "not json",
            json.dumps("a json string"),  # Regression: gültiges JSON, aber kein Objekt
        )
        a = model.agent_from_session_lines(lines, "k", mtime=100, now=105)
        self.assertEqual(a.prompt, "fix the bug")
        self.assertEqual(a.errors, 1)
        self.assertEqual(a.compact_count, 1)
        self.assertEqual(a.ctx_tokens, 110)
        self.assertEqual([t["name"] for t in a.tools], ["read"])  # t2 noch offen
        self.assertEqual(a.phase, "tool")

    def test_regression_open_request_is_not_idle(self):
        """Log endet mit offener Anfrage (Modell/Kompaktierung läuft, pi schreibt erst danach): nicht „wartet auf Prompt“."""
        u = {"role": "user", "content": "los"}
        lines = jl({"type": "session", "cwd": "/x"}, {"type": "message", "message": u})
        for silent, want in ((5, "thinking"), (90, "thinking"), (model.BUSY_MAX_S + 5, "idle")):
            a = model.agent_from_session_lines(lines, "k", mtime=1000, now=1000 + silent)
            self.assertEqual(a.phase, want, silent)
        res = {"type": "message", "message": {"role": "toolResult", "toolCallId": "t", "toolName": "bash", "content": []}}
        a = model.agent_from_session_lines(lines + jl(res), "k", mtime=1000, now=1090)
        self.assertEqual(a.phase, "thinking")

    def test_log_idle_only_after_finished_answer(self):
        done = {"type": "message", "message": {"role": "assistant", "stopReason": "stop", "content": [], "usage": {}}}
        lines = jl({"type": "session", "cwd": "/x"}, {"type": "message", "message": {"role": "user", "content": "hi"}}, done)
        self.assertEqual(model.agent_from_session_lines(lines, "k", mtime=1000, now=1090).phase, "idle")
        self.assertEqual(model.agent_from_session_lines(lines, "k", mtime=1000, now=1010).phase, "idle")

    def test_regression_log_rate_moves_needle(self):
        """Realbetrieb ohne Live-Datei: Rate kam nie über 0 (Nadel stand still)."""
        from datetime import datetime, timezone
        iso = lambda s: datetime.fromtimestamp(s, timezone.utc).isoformat().replace("+00:00", "Z")
        lines = jl(
            {"type": "session", "cwd": "/x", "timestamp": iso(1000)},
            {"type": "message", "timestamp": iso(1010), "message": {"role": "assistant", "timestamp": 1000_000,
                                                                     "usage": {"output": 800}, "content": []}},
            {"type": "message", "timestamp": iso(1030), "message": {"role": "assistant", "timestamp": 1020_000,
                                                                     "usage": {"output": 200}, "content": []}},
        )
        a = model.agent_from_session_lines(lines, "k", mtime=1030, now=1035)
        self.assertAlmostEqual(a.rate, 1000 / 20)
        self.assertTrue(a.rate_est)
        idle = model.agent_from_session_lines(lines, "k", mtime=1030, now=1030 + model.RATE_HOLD_S + 1)
        self.assertEqual(idle.rate, 0)

    def test_regression_empty_tasks_label(self):
        self.assertEqual(model._tool_label("subagent", {"agent": "worker", "tasks": []}), "worker")

    def test_regression_exitcode_zero_while_running(self):
        self.assertFalse(model.looks_finished([{"role": "assistant", "stopReason": "toolUse"}]))
        self.assertTrue(model.looks_finished([{"role": "assistant", "stopReason": "stop"}]))
        self.assertFalse(model.looks_finished([]))

    def test_empty_log(self):
        self.assertIsNone(model.agent_from_session_lines([], "k", 0, 0))

    def test_read_sessions_excludes_live_and_stale(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "--w--"))
            fresh = os.path.join(d, "--w--", "a.jsonl")
            stale = os.path.join(d, "--w--", "b.jsonl")
            live = os.path.join(d, "--w--", "c.jsonl")
            for f in (fresh, stale, live):
                with open(f, "w") as fh:
                    fh.write(json.dumps({"type": "session", "cwd": "/p"}) + "\n")
            os.utime(stale, (time.time() - 99999, time.time() - 99999))
            got = model.read_sessions({live}, sessions_dir=d)
            self.assertEqual([a.key for a in got], [f"log:{fresh}"])


class SceneTest(unittest.TestCase):
    def render(self, agents, t=3.0, W=1280, H=720):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        scene.render(cairo.Context(surf), W, H, agents, t, scene.History())
        return surf

    def test_all_demo_phases_render(self):
        for t in range(0, 50, 2):
            self.render(model.demo_agents(float(t)))

    def test_empty_and_many(self):
        self.render([])
        self.render(model.demo_agents(5) * 3, W=800, H=600)

    def test_regression_unknown_window_is_estimated(self):
        a = model.Agent(key="x", title="t", source="log", ctx_tokens=50_000)
        pct, guessed = scene.context_fill(a)
        self.assertTrue(guessed)
        self.assertAlmostEqual(pct, 25.0)
        self.render([a])

    def test_regression_negative_rate_clamped(self):
        a = model.Agent(key="x", title="t", source="demo", rate=-5)
        self.render([a])

    def test_static_layer_is_cached_and_complete(self):
        """Statische Ebene wird einmal gerendert (nur bei Größen-/Titelwechsel neu) und deckt Rahmen + Beschriftung ab."""
        ag = model.demo_agents(14)[:1]
        lc = scene.StaticLayer()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 960, 600)
        for i in range(3):
            scene.render_cached(cairo.Context(surf), 960, 600, ag, 14 + i, scene.History(), lc)
        self.assertEqual(lc.renders, 1)
        scene.render_cached(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)), 800, 500, ag, 14, scene.History(), lc)
        self.assertEqual(lc.renders, 2)
        # Ebenen zusammen ≈ Vollbild: nicht-weiße Pixel im gleichen Rahmen
        full = cairo.ImageSurface(cairo.FORMAT_ARGB32, 960, 600)
        scene.render(cairo.Context(full), 960, 600, ag, 14, scene.History())
        part = cairo.ImageSurface(cairo.FORMAT_ARGB32, 960, 600)
        scene.render_cached(cairo.Context(part), 960, 600, ag, 14, scene.History(), scene.StaticLayer())
        ink = lambda s: sum(1 for b in bytes(s.get_data())[::4] if b < 200)
        self.assertAlmostEqual(ink(part) / ink(full), 1.0, delta=0.08)

    def test_ui_is_german(self):
        self.assertIn("wartet auf deinen nächsten Prompt", open(scene.__file__).read())
        self.assertNotIn("waiting for your", open(scene.__file__).read())

    def test_layout_fits(self):
        for n in range(1, 7):
            for x, y, s in scene.layout(n, 1920, 1080, 96, 44):
                self.assertGreaterEqual(x, 0)
                self.assertLessEqual(x + scene.PW * s, 1920 + 1e-6)
                self.assertLessEqual(y + scene.PH * s, 1080 - 44 + 1e-6)


if __name__ == "__main__":
    unittest.main()
