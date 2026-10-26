"""Datenschicht: sammelt Agentenzustände für den Screensaver.

Quellen (in dieser Reihenfolge):
1. Live-Dateien der pi-Erweiterung: $XDG_RUNTIME_DIR/agentscope/<pid>.json (Schema v1).
   Nur Dateien lebender Prozesse zählen. Prozesse, deren ppid selbst eine Live-Datei hat,
   sind Subagent-Kinder und werden dem Eltern-Panel zugeordnet.
2. Fallback: kürzlich geschriebene pi-Session-Logs (~/.pi/agent/sessions/**/*.jsonl),
   die keiner Live-Datei gehören – z. B. pi-Prozesse, die vor der Installation der
   Erweiterung gestartet wurden. Gelesen wird nur das Dateiende.
3. Demo: synthetische Daten (`demo_agents`) für Tests, Screenshots und `--demo`.
"""

from __future__ import annotations

import glob
import json
import math
import os
import time
from dataclasses import dataclass, field

RUNTIME_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "agentscope")
SESSIONS_DIR = os.path.expanduser("~/.pi/agent/sessions")
BUSY_MAX_S = 10 * 60      # Log endet mit offener Anfrage: so lange gilt der Agent als beschäftigt
SESSION_FRESH_S = 15 * 60  # Logs, die länger ruhen, gelten als inaktiv
RATE_WINDOW_S = 90         # Log-Fallback: Antworten der letzten 90 s mitteln
RATE_HOLD_S = 25           # … und die Rate so lange nach der letzten Antwort noch zeigen
TAIL_BYTES = 768 * 1024


@dataclass
class Agent:
    """Ein Panel: ein pi-Prozess (oder eine Session) mit allem, was gezeichnet wird."""

    key: str
    title: str
    source: str  # live | log | demo
    phase: str = "idle"
    prompt: str = ""
    model: str = ""
    turn: int = 0
    ctx_tokens: int | None = None
    ctx_window: int | None = None
    ctx_percent: float | None = None
    tok_total: int = 0
    tok_in: int = 0
    tok_out: int = 0
    rate: float = 0.0
    rate_est: bool = False  # Rate aus Log-Durchschnitt geschätzt (keine Live-Messung)
    tools: list = field(default_factory=list)  # [{name,label,started}]
    tool_counts: dict = field(default_factory=dict)
    errors: int = 0
    last_error: str = ""
    last_error_at: float = 0.0
    compacting: bool = False
    compact_count: int = 0
    compact_before: int | None = None
    compact_after: int | None = None
    compact_at: float = 0.0
    retry: dict | None = None
    runs: list = field(default_factory=list)  # subagentRuns aus Schema v1
    children: list = field(default_factory=list)  # Live-Zustände der Subagent-Prozesse (dict)
    events: list = field(default_factory=list)
    updated: float = 0.0


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _short_cwd(cwd: str) -> str:
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        cwd = "~" + cwd[len(home):]
    parts = cwd.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else cwd


def agent_from_state(s: dict) -> Agent:
    ctx = s.get("context") or {}
    tok = s.get("tokens") or {}
    comp = s.get("compaction") or {}
    le = s.get("lastError") or {}
    title = s.get("sessionName") or _short_cwd(s.get("cwd") or "?")
    return Agent(
        key=f"pid:{s.get('pid')}",
        title=title,
        source="live",
        phase=s.get("phase", "idle"),
        prompt=s.get("prompt", ""),
        model=(s.get("model") or "").split("/")[-1],
        turn=s.get("turn", 0),
        ctx_tokens=ctx.get("tokens"),
        ctx_window=ctx.get("window"),
        ctx_percent=ctx.get("percent"),
        tok_total=tok.get("total", 0),
        tok_in=tok.get("input", 0),
        tok_out=tok.get("output", 0),
        rate=float(tok.get("rateOut", 0) or 0),
        tools=list(s.get("tools") or []),
        tool_counts=dict(s.get("toolCounts") or {}),
        errors=s.get("errors", 0),
        last_error=le.get("msg", ""),
        last_error_at=(le.get("at") or 0) / 1000,
        compacting=bool(comp.get("active")),
        compact_count=comp.get("count", 0),
        compact_before=comp.get("tokensBefore"),
        compact_after=comp.get("tokensAfter"),
        compact_at=(comp.get("at") or 0) / 1000,
        retry=s.get("retry"),
        runs=list(s.get("subagentRuns") or []),
        events=list(s.get("events") or []),
        updated=(s.get("updated") or 0) / 1000,
    )


def read_live(runtime_dir: str = RUNTIME_DIR, alive=pid_alive) -> tuple[list[Agent], set[str]]:
    """Liest Live-Dateien. Gibt (Top-Level-Agenten, belegte Session-Dateien) zurück."""
    states = {}
    for f in glob.glob(os.path.join(runtime_dir, "*.json")):
        try:
            with open(f) as fh:
                s = json.load(fh)
        except Exception:
            continue
        pid = s.get("pid")
        if s.get("v") != 1 or not isinstance(pid, int) or not alive(pid):
            continue
        states[pid] = s
    sessions = {s["sessionFile"] for s in states.values() if s.get("sessionFile")}
    tops, kids = [], {}
    for pid, s in states.items():
        if s.get("ppid") in states:
            kids.setdefault(s["ppid"], []).append(s)
        else:
            tops.append(s)
    agents = []
    for s in sorted(tops, key=lambda x: x.get("started", 0)):
        a = agent_from_state(s)
        a.children = sorted(kids.get(s["pid"], []), key=lambda x: x.get("started", 0))
        agents.append(a)
    return agents, sessions


# --------------------------------------------------------------------- Session-Fallback
def _tail_lines(path: str, nbytes: int = TAIL_BYTES) -> list[str]:
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - nbytes))
        data = fh.read()
    lines = data.split(b"\n")
    if size > nbytes:
        lines = lines[1:]  # erste Zeile ist abgeschnitten
    return [ln.decode("utf-8", "replace") for ln in lines if ln.strip()]


def _tool_label(name: str, args: dict) -> str:
    args = args or {}
    if name == "bash":
        return " ".join(str(args.get("command", "")).split())[:48]
    if name in ("read", "edit", "write"):
        return str(args.get("path") or args.get("file_path") or "").rstrip("/").split("/")[-1]
    if name == "subagent":
        if isinstance(args.get("tasks"), list) and args["tasks"]:
            return f"{len(args['tasks'])} parallel"
        if isinstance(args.get("chain"), list) and args["chain"]:
            return f"chain of {len(args['chain'])}"
        return str(args.get("agent", ""))
    return json.dumps(args)[:40]


def _iso_s(ts) -> float | None:
    """ISO-Zeitstempel des Log-Eintrags → Unix-Sekunden."""
    if not isinstance(ts, str):
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def log_rate(samples: list[tuple[float, float, int]], now: float, last_entry: float | None = None) -> float:
    """Ausgabe-Token/s aus abgeschlossenen Antworten (ende, dauer, output) im Log.

    Gemittelt über RATE_WINDOW_S. Gezeigt, solange der Agent arbeitet (letzter Eintrag jünger als
    RATE_HOLD_S) – sonst 0, damit die Nadel bei ruhenden Sessions zurückfällt."""
    recent = [(e, d, o) for e, d, o in samples if now - e <= RATE_WINDOW_S and d > 0.2 and o > 0]
    if not recent:
        return 0.0
    newest = max(e for e, _, _ in recent)
    active = max(newest, last_entry or 0)
    if now - active > RATE_HOLD_S:
        return 0.0
    return sum(o for _, _, o in recent) / sum(d for _, d, _ in recent)


def log_phase(last_kind: str | None, has_tools: bool, idle_s: float) -> str:
    """Phase aus dem Log-Ende. pi schreibt erst, wenn eine Nachricht fertig ist: ein langer Modellaufruf
    (oder eine Kompaktierung) hinterlässt also Stille, ohne dass der Agent wartet.
    idle gilt nur, wenn die letzte Antwort abgeschlossen ist; eine offene Anfrage bleibt BUSY_MAX_S lang aktiv."""
    if has_tools:
        return "tool"
    if last_kind in ("user", "result", "tool"):
        return "thinking" if idle_s < BUSY_MAX_S else "idle"
    if last_kind == "compact":
        return "thinking" if idle_s < 30 else "idle"
    return "idle"

def agent_from_session_lines(lines: list[str], key: str, mtime: float, now: float) -> Agent | None:
    """Rekonstruiert einen ungefähren Zustand aus dem Ende eines Session-Logs."""
    a = Agent(key=key, title="", source="log", updated=mtime)
    pending: dict[str, dict] = {}
    samples: list[tuple[float, float, int]] = []
    last_entry = None
    last_kind = None  # user | result | tool | done | compact – womit das Log zuletzt aufhört
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
        ts = _iso_s(o.get("timestamp"))
        if ts:
            last_entry = ts
        if t == "session":
            cwd = o.get("cwd", "")
        elif t == "session_info" and o.get("name"):
            a.title = o["name"]
        elif t == "custom_message":
            last_kind = "user"
        elif t == "model_change":
            a.model = str(o.get("modelId", "")).split("/")[-1]
        elif t == "compaction":
            a.compact_count += 1
            a.compact_before = o.get("tokensBefore")
            last_kind = "compact"
            a.events.append({"kind": "compact", "text": f"Kontext gequetscht von {round((o.get('tokensBefore') or 0) / 1000)}k", "at": 0})
        elif t == "message":
            m = o.get("message") or {}
            role = m.get("role")
            last_kind = {"user": "user", "toolResult": "result"}.get(role, last_kind)
            if role == "user":
                c = m.get("content")
                text = c if isinstance(c, str) else " ".join(p.get("text", "") for p in (c or []) if isinstance(p, dict))
                if text.strip():
                    a.prompt = " ".join(text.split())[:160]
                    a.events.append({"kind": "input", "text": a.prompt[:90], "at": 0})
            elif role == "assistant":
                a.turn += 1
                last_kind = "tool" if m.get("stopReason") == "toolUse" else "done"
                u = m.get("usage") or {}
                a.tok_in += u.get("input", 0) or 0
                a.tok_out += u.get("output", 0) or 0
                a.tok_total += u.get("totalTokens", 0) or 0
                start = m.get("timestamp")
                if ts and isinstance(start, (int, float)) and start > 0:
                    samples.append((ts, ts - start / 1000, int(u.get("output", 0) or 0)))
                if u.get("totalTokens"):
                    a.ctx_tokens = u["totalTokens"]
                if m.get("model"):
                    a.model = str(m["model"]).split("/")[-1]
                if m.get("stopReason") == "error" or m.get("errorMessage"):
                    a.errors += 1
                    a.last_error = str(m.get("errorMessage", "model error"))[:120]
                    a.events.append({"kind": "error", "text": a.last_error[:90], "at": 0})
                for p in m.get("content") or []:
                    if isinstance(p, dict) and p.get("type") == "toolCall":
                        name = p.get("name", "?")
                        label = _tool_label(name, p.get("arguments") or {})
                        pending[p.get("id")] = {"name": name, "label": label, "started": m.get("timestamp", 0)}
                        a.tool_counts[name] = a.tool_counts.get(name, 0) + 1
                        a.events.append({"kind": "subagent" if name == "subagent" else "tool", "text": f"{name}: {label}", "at": 0})
            elif role == "toolResult":
                pending.pop(m.get("toolCallId"), None)
                if m.get("isError"):
                    a.errors += 1
                    txt = " ".join(p.get("text", "") for p in (m.get("content") or []) if isinstance(p, dict))
                    a.last_error = f"{m.get('toolName', '?')}: {' '.join(txt.split())}"[:120]
                    a.events.append({"kind": "tool_error", "text": a.last_error[:90], "at": 0})
                # Subagent-Fortschritt aus final details
                d = m.get("details") or {}
                if m.get("toolName") == "subagent" and isinstance(d.get("results"), list):
                    a.runs = [_run_from_details(m.get("toolCallId", ""), d, True)][-4:]
    if not any_entry:
        return None
    a.title = a.title or _short_cwd(cwd or "pi")
    a.tools = list(pending.values())
    a.rate = log_rate(samples, now, last_entry)
    a.rate_est = a.rate > 0
    a.phase = log_phase(last_kind, bool(a.tools), now - mtime)
    for i, e in enumerate(a.events):
        e["seq"] = i
    a.events = a.events[-40:]
    return a


def looks_finished(messages) -> bool:
    """Siehe extension/core.ts looksFinished: exitCode ist während des Laufs schon 0."""
    if not isinstance(messages, list) or not messages:
        return False
    m = messages[-1]
    return isinstance(m, dict) and m.get("role") == "assistant" and bool(m.get("stopReason")) and m.get("stopReason") != "toolUse"


def _run_from_details(tcid: str, d: dict, finished: bool) -> dict:
    agents = []
    for r in d.get("results") or []:
        u = r.get("usage") or {}
        failed = (r.get("exitCode") or 0) > 0 or r.get("stopReason") in ("error", "aborted") or bool(r.get("errorMessage"))
        running = not finished and not failed and (r.get("exitCode") in (-1, None) or not looks_finished(r.get("messages")))
        agents.append({
            "agent": str(r.get("agent", "?"))[:24], "task": " ".join(str(r.get("task", "")).split())[:90],
            "status": "running" if running else "failed" if failed else "done",
            "turns": u.get("turns", 0), "tokens": (u.get("input", 0) or 0) + (u.get("output", 0) or 0),
            "contextTokens": u.get("contextTokens", 0), "lastTool": "", "error": str(r.get("errorMessage") or "")[:80],
        })
    return {
        "toolCallId": tcid, "mode": d.get("mode", "single"), "total": len(agents),
        "done": sum(x["status"] == "done" for x in agents), "running": sum(x["status"] == "running" for x in agents),
        "failed": sum(x["status"] == "failed" for x in agents), "finished": finished, "agents": agents,
    }


def read_sessions(exclude: set[str], sessions_dir: str = SESSIONS_DIR, now: float | None = None,
                  fresh_s: float = SESSION_FRESH_S, limit: int = 4) -> list[Agent]:
    now = time.time() if now is None else now
    found = []
    for f in glob.glob(os.path.join(sessions_dir, "*", "*.jsonl")):
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        if now - mt <= fresh_s and os.path.abspath(f) not in exclude and f not in exclude:
            found.append((mt, f))
    out = []
    for mt, f in sorted(found, reverse=True)[:limit]:
        try:
            a = agent_from_session_lines(_tail_lines(f), f"log:{f}", mt, now)
        except Exception:
            a = None
        if a:
            out.append(a)
    return out


def collect(now: float | None = None) -> list[Agent]:
    live, sessions = read_live()
    return live + read_sessions(sessions, now=now)


# --------------------------------------------------------------------- Demo
DEMO_PROMPTS = [
    "baue einen animierten Bildschirmschoner im xkcd-Stil, der zeigt, was alle meine Agenten tun",
    "repariere den wackligen Integrationstest im Hub",
    "räume die Export-Pipeline auf und aktualisiere die Doku",
]


def demo_agents(t: float) -> list[Agent]:
    """Deterministische, zeitabhängige Szenen, die alle Zustände durchspielen."""
    cyc = t % 48
    phases = ["thinking", "streaming", "tool", "tool", "compacting", "tool", "error", "retrying", "streaming", "idle"]
    a_phase = phases[int(cyc / 4.8) % len(phases)]
    ctx_p = 30 + 60 * ((cyc % 24) / 24)
    tool_by_phase = {
        "tool": [{"name": ["bash", "read", "edit", "subagent"][int(t / 6) % 4], "label": ["cargo test --workspace", "sketch.py", "scene.py", "3 parallel"][int(t / 6) % 4], "started": 0}],
    }
    nrun = 5
    prog = (t % 30) / 30
    agents_sub = []
    names = [("worker", "render engine"), ("worker", "data layer + tests"), ("scout", "find pi event names"), ("reviewer", "review the diff"), ("worker", "hyprland keybinding")]
    for i, (n, task) in enumerate(names[:nrun]):
        k = prog * nrun * 1.3 - i * 0.9
        st = "done" if k > 1 else "running"
        if i == 2 and k > 0.6:
            st = "failed"
        agents_sub.append({"agent": n, "task": task, "status": st, "turns": int(max(0, k) * 9), "tokens": int(max(0, min(k, 1)) * 42000),
                           "contextTokens": 0, "lastTool": ["bash: cargo build", "read: core.ts", "bash: rg session_compact", "read: diff", "edit: bindings.lua"][i],
                           "error": "401: invalid token" if st == "failed" else ""})
    run = {"toolCallId": "demo", "mode": "parallel", "total": nrun, "done": sum(a["status"] == "done" for a in agents_sub),
           "running": sum(a["status"] == "running" for a in agents_sub), "failed": sum(a["status"] == "failed" for a in agents_sub),
           "finished": False, "agents": agents_sub}
    ev_texts = [("input", DEMO_PROMPTS[0]), ("tool", "bash: ls ~/.pi/agent"), ("tool", "read: extensions.md"), ("subagent", "delegiert 5 parallel"),
                ("tool_error", "bash-Fehler: Datei nicht gefunden"), ("compact", "Kontext gequetscht von 152k"), ("tool", "edit: scene.py"), ("retry", "Retry 1/3: 529 überlastet")]
    n_ev = 3 + int(t / 2) % len(ev_texts)
    events = [{"seq": i, "kind": k, "text": x, "at": 0} for i, (k, x) in enumerate((ev_texts * 3)[:n_ev])]
    a = Agent(
        key="demo:1", title="omarchy-agentscope", source="demo", phase=a_phase, prompt=DEMO_PROMPTS[0], model="claude-opus-5-5", turn=int(t / 3),
        ctx_tokens=int(ctx_p * 2000), ctx_window=200000, ctx_percent=ctx_p, tok_total=int(t * 1800) % 900000, tok_in=int(t * 1700), tok_out=int(t * 100),
        rate=0 if a_phase in ("idle", "compacting") else max(0.0, 45 + 30 * math.sin(t * 0.7) + 15 * math.sin(t * 2.3)),
        tools=tool_by_phase.get(a_phase, []), tool_counts={"bash": 23, "read": 41, "edit": 12, "subagent": 2},
        errors=2 + int(t / 20), last_error="bash: ls: cannot access '/nonexistent'", last_error_at=time.time() - (0 if a_phase == "error" else 60),
        compacting=a_phase == "compacting", compact_count=1 + int(t / 48), compact_before=152000, compact_after=31000,
        retry={"attempt": 1, "max": 3, "error": "529 overloaded"} if a_phase == "retrying" else None,
        runs=[run], events=events, updated=time.time(),
    )
    b_phase = ["streaming", "tool", "thinking", "tool"][int(t / 5) % 4]
    b = Agent(
        key="demo:2", title="pi-hub", source="demo", phase=b_phase, prompt=DEMO_PROMPTS[1], model="gpt-6.1-sol", turn=int(t / 4),
        ctx_tokens=60000, ctx_window=128000, ctx_percent=47, tok_total=int(t * 600), rate=25 + 10 * math.sin(t),
        tools=[{"name": "bash", "label": "npm test", "started": 0}] if b_phase == "tool" else [], tool_counts={"bash": 9, "read": 14},
        events=[{"seq": 1, "kind": "tool", "text": "bash: npm test", "at": 0}], updated=time.time(),
    )
    c = Agent(key="demo:3", title="more-re", source="demo", phase="idle", prompt=DEMO_PROMPTS[2], model="claude-sonnet-5-5",
              ctx_tokens=20000, ctx_window=200000, ctx_percent=10, tok_total=120000, updated=time.time())
    return [a, b, c]
