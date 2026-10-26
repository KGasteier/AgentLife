"""Fremd-Harness-Leser: Claude Code und Codex (keine Live-Erweiterung, nur Sitzungs-Logs).

pi schreibt Live-Zustand über die Erweiterung. Claude Code und Codex haben keine solche
Schnittstelle, also wird das jeweilige Sitzungs-Log von hinten gelesen und zu einem
`Agent` rekonstruiert – so grob wie der pi-Log-Fallback, aber mit Harness-Kennzeichnung.

- Claude Code: ~/.claude/projects/<slug>/<uuid>.jsonl   (user/assistant-Zeilen, usage, ai-title)
- Codex:       ~/.codex/sessions/JJJJ/MM/TT/rollout-*.jsonl (event_msg/response_item, token_usage_record)
"""

from __future__ import annotations

import glob
import json
import os
import re
import time

from .model import (
    BUSY_MAX_S,
    TAIL_BYTES,
    Agent,
    _tool_label,
    _tail_lines,
    _iso_s,
    log_rate,
    skill_from_prompt,
    _short_cwd,
)

CLAUDE_DIR = os.path.expanduser("~/.claude/projects")
CODEX_DIR = os.path.expanduser("~/.codex/sessions")
FOREIGN_FRESH_S = 30 * 60   # so lange gilt ein fremdes Sitzungs-Log als „läuft noch“
FOREIGN_LIMIT = 2           # höchstens so viele Panels je fremdem Harness


def _fresh_files(pattern: str, now: float, fresh_s: float, limit: int) -> list[str]:
    found = []
    for f in glob.glob(pattern):
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        if now - mt <= fresh_s:
            found.append((mt, f))
    return [f for _, f in sorted(found, reverse=True)[:limit]]


def _head_lines(path: str, want: int = 30, max_bytes: int = 4 * 1024 * 1024) -> list[str]:
    """Die ersten `want` vollständigen Zeilen (Codex schreibt session_meta/turn_context nur am Anfang;
    die session_meta-Zeile ist wegen der Basisinstruktionen sehr lang, deshalb zeilenweise lesen)."""
    out: list[str] = []
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                out.append(raw.decode("utf-8", "replace"))
                if len(out) >= want or fh.tell() > max_bytes:
                    break
    except OSError:
        return []
    return [ln for ln in out if ln.strip()]


def _whole_or_split(path: str, tail_bytes: int) -> list[str]:
    """Kleine Dateien ganz lesen; große als Kopf + Ende (Kopf trägt die Sitzungsmetadaten)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return _tail_lines(path)
    if size <= tail_bytes:
        return _tail_lines(path, nbytes=tail_bytes)
    head = _head_lines(path)
    tail = _tail_lines(path, nbytes=tail_bytes)
    seen = set(head)
    return head + [ln for ln in tail if ln not in seen]


def _user_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def _result_blocks(content) -> list[dict]:
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict) and p.get("type") == "tool_result"]
    return []


# ---------------------------------------------------------------------- Claude Code
_CLAUDE_TOOLS = {"bash": "bash", "read": "read", "edit": "edit", "write": "write", "notebookedit": "edit",
                 "grep": "grep", "glob": "grep", "task": "subagent", "webfetch": "read", "websearch": "read",
                 "todowrite": "write"}


def agent_from_claude_lines(lines: list[str], path: str, mtime: float, now: float) -> Agent | None:
    a = Agent(key=f"claude:{path}", title="", source="log", harness="claude", updated=mtime)
    pending: dict[str, dict] = {}
    samples: list[tuple[float, float, int]] = []
    last_kind = None            # user | result | tool | done | compact
    last_entry = None
    prev_ts = None
    cwd = ""
    prompt = ""
    summary = ""
    any_entry = False
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        any_entry = True
        t = o.get("type")
        ts = _iso_s(o.get("timestamp"))
        if ts:
            last_entry = ts
        if o.get("cwd"):
            cwd = o["cwd"]
        if t == "ai-title" and o.get("aiTitle"):
            a.title = str(o["aiTitle"])
        elif t == "last-prompt" and o.get("lastPrompt"):
            prompt = str(o["lastPrompt"])
        elif t == "summary" and o.get("summary"):
            summary = str(o["summary"])
        elif t == "user":
            m = o.get("message") or {}
            if o.get("isCompactSummary"):
                a.compact_count += 1
                last_kind = "compact"
                a.events.append({"kind": "compact", "text": "Kontext zusammengefasst", "at": 0})
                continue
            blocks = _result_blocks(m.get("content"))
            if blocks:
                for b in blocks:
                    pending.pop(b.get("tool_use_id"), None)
                    if b.get("is_error"):
                        a.errors += 1
                        txt = " ".join(_user_text(b.get("content")) .split())
                        a.last_error = txt[:120]
                        a.events.append({"kind": "tool_error", "text": a.last_error[:90], "at": 0})
                last_kind = "result"
            else:
                text = _user_text(m.get("content"))
                if text.strip():
                    prompt = " ".join(text.split())[:160]
                    if o.get("origin", {}).get("kind") in (None, "human") and o.get("promptSource") != "system":
                        a.events.append({"kind": "input", "text": prompt[:90], "at": 0})
                last_kind = "user"
        elif t == "assistant":
            m = o.get("message") or {}
            if m.get("model"):
                a.model = str(m["model"]).split("/")[-1]
            u = m.get("usage") or {}
            ctx = (u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0) + \
                  (u.get("cache_creation_input_tokens", 0) or 0)
            out = u.get("output_tokens", 0) or 0
            a.tok_in += (u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0) + \
                        (u.get("cache_creation_input_tokens", 0) or 0)
            a.tok_out += out
            if ctx:
                a.ctx_tokens = ctx + out
            a.turn += 1
            sr = m.get("stop_reason")
            if sr == "tool_use":
                last_kind = "tool"
            elif sr in ("end_turn", "stop_sequence", None):
                last_kind = "done"
            else:
                last_kind = "done"
            if ts and prev_ts and ts - prev_ts > 0.2 and out:
                samples.append((ts, ts - prev_ts, int(out)))
            for p in m.get("content") or []:
                if isinstance(p, dict) and p.get("type") == "tool_use":
                    name = str(p.get("name", "?")).lower()
                    pi_name = _CLAUDE_TOOLS.get(name, name)
                    label = _tool_label(pi_name, p.get("input") or {})
                    pending[p.get("id")] = {"name": pi_name, "label": label, "started": 0}
                    a.tool_counts[pi_name] = a.tool_counts.get(pi_name, 0) + 1
                    a.events.append({"kind": "subagent" if pi_name == "subagent" else "tool",
                                     "text": f"{pi_name}: {label}", "at": 0})
        if ts:
            prev_ts = ts
    if not any_entry:
        return None
    a.title = a.title or " ".join((first_prompt or prompt).split())[:42] or _short_cwd(cwd or "claude")
    a.skill = skill_from_prompt(prompt)
    a.prompt = prompt
    a.ctx_window = a.ctx_window or 200_000      # Claude-Code-Fenster als Annahme
    a.tok_total = a.tok_in + a.tok_out
    a.tools = list(pending.values())
    a.rate = log_rate(samples, now, last_entry)
    a.rate_est = a.rate > 0
    a.phase = ("tool" if a.tools else
               "idle" if last_kind == "done" else
               "thinking" if last_kind in ("user", "result", "compact") and now - mtime < BUSY_MAX_S else "idle")
    for i, e in enumerate(a.events):
        e["seq"] = i
    a.events = a.events[-40:]
    return a


def read_claude(projects_dir: str = CLAUDE_DIR, now: float | None = None,
                fresh_s: float = FOREIGN_FRESH_S, limit: int = FOREIGN_LIMIT) -> list[Agent]:
    now = time.time() if now is None else now
    out = []
    for f in _fresh_files(os.path.join(projects_dir, "*", "*.jsonl"), now, fresh_s, limit):
        try:
            a = agent_from_claude_lines(_tail_lines(f), f, os.path.getmtime(f), now)
        except Exception:
            a = None
        if a:
            out.append(a)
    return out


# ---------------------------------------------------------------------- Codex
def _codex_label(name: str, args) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return " ".join(args.split())[:40]
    if isinstance(args, dict):
        for k in ("cmd", "command"):
            if args.get(k):
                return " ".join(str(args[k]).split())[:48]
        for k in ("path", "file_path"):
            if args.get(k):
                return str(args[k]).rstrip("/").split("/")[-1]
        return json.dumps(args)[:40]
    return str(name)


def _codex_output_error(payload: dict) -> str:
    """exit_code aus den Ausgabe-Chunks ziehen (0 = ok)."""
    chunks = payload.get("output") or []
    text = " ".join(c.get("text", "") for c in chunks if isinstance(c, dict))
    m = re.search(r'"exit_code"\s*:\s*(-?\d+)', text)
    if m and int(m.group(1)) != 0:
        rest = text.split("Output:", 1)[-1]
        return " ".join(rest.split())[:100] or f"exit {m.group(1)}"
    return ""


def agent_from_codex_lines(lines: list[str], path: str, mtime: float, now: float) -> Agent | None:
    a = Agent(key=f"codex:{path}", title="", source="log", harness="codex", updated=mtime)
    pending: dict[str, dict] = {}
    samples: list[tuple[float, float, int]] = []
    last_entry = None
    prev_ts = None
    in_turn = False
    prompt = ""
    first_prompt = ""
    cwd = ""
    any_entry = False
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        any_entry = True
        t = o.get("type")
        pl = o.get("payload") or {}
        ts = _iso_s(o.get("timestamp"))
        if ts:
            last_entry = ts
        if t == "session_meta":
            cwd = pl.get("cwd") or cwd
            a.model = str(pl.get("model") or a.model)
        elif t == "turn_context":
            cwd = pl.get("cwd") or cwd
            if pl.get("model"):
                a.model = str(pl["model"]).split("/")[-1]
        elif t == "token_usage_record":
            u = pl.get("usage") or {}
            out = int(u.get("output_tokens", 0) or 0)
            a.tok_in += int(u.get("input_tokens", 0) or 0)
            a.tok_out += out
            if ts and prev_ts and ts - prev_ts > 0.2 and out:
                samples.append((ts, ts - prev_ts, out))
        elif t == "compacted":
            a.compact_count += 1
            a.events.append({"kind": "compact", "text": "Kontext zusammengefasst", "at": 0})
        elif t == "event_msg":
            et = pl.get("type")
            if et == "task_started":
                in_turn = True
                a.ctx_window = pl.get("model_context_window") or a.ctx_window
                a.turn += 1
            elif et == "task_complete":
                in_turn = False
            elif et == "token_count":
                info = pl.get("info") or {}
                last = info.get("last_token_usage") or {}
                total = info.get("total_token_usage") or {}
                if last.get("total_tokens"):
                    a.ctx_tokens = int(last["total_tokens"])
                if total.get("total_tokens"):
                    a.tok_total = max(a.tok_total, int(total["total_tokens"]))
                a.ctx_window = info.get("model_context_window") or a.ctx_window
            elif et == "item_completed":
                it = pl.get("item") or {}
                if it.get("type") == "UserMessage":
                    prompt = _user_text(it.get("content"))[:160]
                    first_prompt = first_prompt or prompt
                    if not prompt.lower().startswith("<"):
                        a.events.append({"kind": "input", "text": " ".join(prompt.split())[:90], "at": 0})
        elif t == "response_item":
            rt = pl.get("type")
            if rt in ("function_call", "custom_tool_call"):
                call_id = pl.get("call_id") or pl.get("id")
                name = str(pl.get("name", "?"))
                label = _codex_label(name, pl.get("arguments") if rt == "function_call" else pl.get("input"))
                pending[call_id] = {"name": name, "label": label, "started": 0}
                a.tool_counts[name] = a.tool_counts.get(name, 0) + 1
                a.events.append({"kind": "tool", "text": f"{name}: {label}", "at": 0})
            elif rt in ("function_call_output", "custom_tool_call_output"):
                pending.pop(pl.get("call_id"), None)
                if rt == "custom_tool_call_output":
                    err = _codex_output_error(pl)
                    if err:
                        a.errors += 1
                        a.last_error = err
                        a.events.append({"kind": "tool_error", "text": err[:90], "at": 0})
            elif rt == "message" and pl.get("role") == "assistant":
                text = _user_text([c for c in (pl.get("content") or []) if isinstance(c, dict)])
                if text.strip():
                    a.events.append({"kind": "done", "text": " ".join(text.split())[:90], "at": 0})
                in_turn = False
        if ts:
            prev_ts = ts
    if not any_entry:
        return None
    a.title = a.title or " ".join((first_prompt or prompt).split())[:42] or _short_cwd(cwd or "codex")
    a.prompt = prompt
    a.skill = skill_from_prompt(first_prompt or prompt)
    a.ctx_window = a.ctx_window or 200_000
    if not a.tok_total:
        a.tok_total = a.tok_in + a.tok_out
    a.tools = list(pending.values())
    a.rate = log_rate(samples, now, last_entry)
    a.rate_est = a.rate > 0
    if a.tools:
        a.phase = "tool"
    elif in_turn and now - mtime < BUSY_MAX_S:
        a.phase = "thinking"
    else:
        a.phase = "idle"
    for i, e in enumerate(a.events):
        e["seq"] = i
    a.events = a.events[-40:]
    return a


def read_codex(sessions_dir: str = CODEX_DIR, now: float | None = None,
               fresh_s: float = FOREIGN_FRESH_S, limit: int = FOREIGN_LIMIT) -> list[Agent]:
    now = time.time() if now is None else now
    out = []
    for f in _fresh_files(os.path.join(sessions_dir, "*", "*", "*", "rollout-*.jsonl"), now, fresh_s, limit):
        try:
            a = agent_from_codex_lines(_whole_or_split(f, TAIL_BYTES), f, os.path.getmtime(f), now)
        except Exception:
            a = None
        if a:
            out.append(a)
    return out
