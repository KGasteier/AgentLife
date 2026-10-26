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


class HarnessTest(unittest.TestCase):
    """Fremd-Harnessse (Claude Code, Codex) aus ihren Sitzungs-Logs rekonstruieren."""

    def _write(self, d, name, lines):
        f = os.path.join(d, name)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh:
            for ln in lines:
                fh.write(json.dumps(ln) + "\n")
        return f

    def claude_lines(self):
        now = time.time()
        ts = lambda k: __import__("datetime").datetime.fromtimestamp(now + k, tz=__import__("datetime").timezone.utc).isoformat()
        return [
            {"type": "mode", "cwd": "/home/x/Work/vault"},
            {"type": "ai-title", "aiTitle": "Vault-Editor"},
            {"type": "user", "timestamp": ts(-20), "cwd": "/home/x/Work/vault",
             "message": {"role": "user", "content": "vaultdev bau den Editor"}},
            {"type": "assistant", "timestamp": ts(-18), "message": {"model": "claude-opus-5-5", "stop_reason": "tool_use",
             "usage": {"input_tokens": 100, "cache_read_input_tokens": 400, "cache_creation_input_tokens": 0, "output_tokens": 30},
             "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "cargo test"}}]}},
            {"type": "user", "timestamp": ts(-10), "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "cargo: linking failed"}]}},
            {"type": "user", "timestamp": ts(-9), "isCompactSummary": True, "message": {"role": "user", "content": "summary"}},
        ]

    def test_claude_log_is_reconstructed(self):
        from agentscope import harnesses
        with tempfile.TemporaryDirectory() as d:
            f = self._write(d, "-home-x-Work/vault.jsonl", self.claude_lines())
            a = harnesses.agent_from_claude_lines(harnesses._tail_lines(f), f, os.path.getmtime(f), time.time())
        self.assertEqual(a.harness, "claude")
        self.assertEqual(a.title, "Vault-Editor")
        self.assertEqual(a.skill, "vaultdev")          # /name am Prompt-Anfang
        self.assertEqual(a.model, "claude-opus-5-5")
        self.assertEqual(a.tool_counts, {"bash": 1})
        self.assertEqual(a.errors, 1)
        self.assertEqual(a.compact_count, 1)
        self.assertEqual(a.ctx_tokens, 530)
        self.assertEqual(a.tok_out, 30)

    def codex_lines(self):
        now = time.time()
        ts = lambda k: __import__("datetime").datetime.fromtimestamp(now + k, tz=__import__("datetime").timezone.utc).isoformat()
        return [
            {"type": "session_meta", "timestamp": ts(-30), "payload": {"cwd": "/home/x/Work/pi-hub", "model": "gpt-6.1-sol"}},
            {"type": "turn_context", "timestamp": ts(-29), "payload": {"cwd": "/home/x/Work/pi-hub", "model": "gpt-6.1-sol"}},
            {"type": "event_msg", "timestamp": ts(-28), "payload": {"type": "task_started"}},
            {"type": "event_msg", "timestamp": ts(-27), "payload": {"type": "item_completed", "item": {"type": "UserMessage",
             "content": [{"type": "text", "text": "/tangent2dev mach weiter"}]}}},
            {"type": "response_item", "timestamp": ts(-20), "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": "rg token_count"}},
            {"type": "response_item", "timestamp": ts(-18), "payload": {"type": "custom_tool_call_output", "call_id": "c1",
             "output": [{"type": "text", "text": '{"exit_code":1,"Output":"nichts gefunden"}'}]}},
            {"type": "token_usage_record", "timestamp": ts(-17), "payload": {"usage": {"input_tokens": 800, "output_tokens": 200, "total_tokens": 1000}}},
            {"type": "event_msg", "timestamp": ts(-16), "payload": {"type": "token_count", "info": {"last_token_usage": {"total_tokens": 21000},
             "total_token_usage": {"total_tokens": 1000}, "model_context_window": 475000}}},
            {"type": "compacted", "timestamp": ts(-15), "payload": {"replacement_history": []}},
            {"type": "event_msg", "timestamp": ts(-14), "payload": {"type": "task_complete"}},
        ]

    def test_codex_log_is_reconstructed(self):
        from agentscope import harnesses
        with tempfile.TemporaryDirectory() as d:
            f = self._write(d, "2026/01/02/rollout-x.jsonl", self.codex_lines())
            a = harnesses.agent_from_codex_lines(harnesses._whole_or_split(f, model.TAIL_BYTES), f, os.path.getmtime(f), time.time())
        self.assertEqual(a.harness, "codex")
        self.assertEqual(a.skill, "tangent2dev")        # /name am Prompt-Anfang
        self.assertEqual(a.model, "gpt-6.1-sol")
        self.assertEqual(a.tool_counts, {"exec": 1})
        self.assertEqual(a.errors, 1)
        self.assertEqual(a.compact_count, 1)
        self.assertEqual(a.ctx_tokens, 21000)
        self.assertEqual(a.ctx_window, 475000)
        self.assertEqual(a.tok_total, 1000)

    def test_codex_head_carries_session_meta_for_big_files(self):
        """Regression: session_meta/turn_context stehen nur am Dateianfang – der Tail allein verliert das Modell."""
        from agentscope import harnesses
        with tempfile.TemporaryDirectory() as d:
            lines = self.codex_lines() + [{"type": "event_msg", "timestamp": "2026-01-02T03:00:00+00:00",
                                           "payload": {"type": "item_completed", "item": {"type": "UserMessage", "content": [{"type": "text", "text": "x"}]}}}]
            f = self._write(d, "2026/01/02/rollout-big.jsonl", lines)
            # Datei künstlich größer als das Tail-Fenster machen
            with open(f, "a") as fh:
                fh.write("\n".join(json.dumps({"type": "pad", "payload": {"p": "y" * 400}}) for _ in range(2500)) + "\n")
            self.assertGreater(os.path.getsize(f), model.TAIL_BYTES)
            a = harnesses.agent_from_codex_lines(harnesses._whole_or_split(f, model.TAIL_BYTES), f, os.path.getmtime(f), time.time())
        self.assertEqual(a.model, "gpt-6.1-sol")
        self.assertEqual(a.harness, "codex")

    def test_regression_panel_title_names_harness_and_skill(self):
        """Der Panel-Titel nennt den Harness und den gekürzten Skill- bzw. Sitzungsnamen."""
        a = model.Agent(key="k", title="Screensaver-Agent", source="live", harness="pi", skill="vaultdev")
        self.assertEqual(scene.panel_title(a), "pi · vaultdev")
        b = model.Agent(key="k", title="Vault-Editor", source="log", harness="claude")
        self.assertEqual(scene.panel_title(b), "claude · Vault-Editor")
        self.assertEqual((0.72, 0.36, 0.14), scene.harness_ink(b))
        self.assertEqual(scene.INK, scene.harness_ink(a))
        self.assertNotEqual(scene.harness_ink(a), scene.harness_ink(b))
        self.assertNotEqual(scene.harness_ink(b), scene.harness_ink(model.Agent(key="k", title="t", source="log", harness="codex")))


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

    def test_regression_title_is_session_name(self):
        """Panel-Titel = Sitzungsname von pi (auch wenn die Live-Datei ihn nicht kennt), sonst Verzeichnis."""
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "s.jsonl")
            with open(f, "w") as fh:
                fh.write(json.dumps({"type": "session_info", "name": "Alt"}) + "\n")
                fh.write(json.dumps({"type": "session_info", "name": "Screensaver-Agent"}) + "\n")
            st = {"pid": 1, "cwd": "/home/x/Work/proj", "sessionFile": f, "sessionName": None, "phase": "idle"}
            self.assertEqual(model.agent_from_state(st).title, "Screensaver-Agent")
            st["sessionName"] = "Direkt"
            self.assertEqual(model.agent_from_state(st).title, "Direkt")
            st.update(sessionName=None, sessionFile=None)
            self.assertIn("proj", model.agent_from_state(st).title)

    def test_regression_hidpi_text_stays_sharp(self):
        """Bei Gerätemaßstab 2 (GTK HiDPI) müssen Textmasken und statische Ebene in Gerätepixeln entstehen, sonst unscharf."""
        ag = model.demo_agents(14)[:1]
        def tv(draw):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1200)
            surf.set_device_scale(2, 2)
            draw(cairo.Context(surf))
            d = bytes(surf.get_data())
            return sum((d[i] - d[i + 4]) ** 2 for i in range(0, len(d) - 4, 12))  # Gradientenenergie = Kantenschärfe
        sharp = tv(lambda c: scene.render(c, 960, 600, ag, 14, scene.History()))
        cached = tv(lambda c: scene.render_cached(c, 960, 600, ag, 14, scene.History(), scene.StaticLayer()))
        self.assertGreater(cached / sharp, 0.92)  # unscharf hochskaliert: ca. 0,76

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
