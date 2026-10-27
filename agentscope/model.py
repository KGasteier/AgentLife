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
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field

RUNTIME_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "agentscope")
# Spiegel entfernter Backends (copi zieht sie per rsync von SSH-Servern hierher, siehe Akt 3).
# Anders als die lokalen Live-Dateien gilt hier nicht `pid_alive` – entfernte PIDs gibt es lokal nicht –
# sondern die Schreibfrische: copi frischt den Spiegel fortlaufend auf, solange der Agent läuft.
def _cache_root() -> str:
    """Cache-Wurzel wie copi (Rust `dirs::cache_dir`): `XDG_CACHE_HOME` schlägt `~/.cache`.
    Beide Seiten müssen denselben Ort lesen, sonst findet der Screensaver den Spiegel nicht."""
    env = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    return os.path.join(env, "copi", "agentscope-remote") if env else os.path.expanduser("~/.cache/copi/agentscope-remote")


MIRROR_ROOT = _cache_root()
MIRROR_ENV = "AGENTSCOPE_MIRRORS"   # Doppelpunkt-getrennte Liste zusätzlicher Spiegelordner
MIRROR_FRESH_S = 120                 # Spiegeldateien, die länger ruhen, gelten als tot
MIRROR_SYNC_S = 20                   # so oft darf copi den Spiegel auffrischen
SYNC_BINS = ("cocopi", "copi")       # Reihenfolge: cocopi zuerst, copi als Rückfall
SYNC_ENV = "AGENTSCOPE_SYNC_BIN"     # fester Pfad/Name statt der Suche
SYNC_OFF_ENV = "AGENTSCOPE_SYNC"     # "off" schaltet das Auffrischen ab
SESSIONS_DIR = os.path.expanduser("~/.pi/agent/sessions")
SKILL_DIRS = [os.path.expanduser("~/.pi/agent/skills"), os.path.expanduser("~/.agents/skills")]
BUSY_MAX_S = 10 * 60      # Log endet mit offener Anfrage: so lange gilt der Agent als beschäftigt
SESSION_FRESH_S = 15 * 60  # Logs, die länger ruhen, gelten als inaktiv
RATE_WINDOW_S = 90         # Log-Fallback: Antworten der letzten 90 s mitteln
RATE_HOLD_S = 25           # … und die Rate so lange nach der letzten Antwort noch zeigen
TAIL_BYTES = 768 * 1024

# Auffrischungs-Takt der Fern-Spiegel (modulweit, damit mehrere Aufrufer ihn teilen).
_SYNC_LAST = 0.0
_SYNC_BUSY = False


@dataclass
class Agent:
    """Ein Panel: ein pi-Prozess (oder eine Session) mit allem, was gezeichnet wird."""

    key: str
    title: str
    source: str  # live | log | demo
    harness: str = "pi"   # pi | claude | codex | demo
    skill: str = ""       # ausgeführter Skill (aus /skill:name bzw. /name am Prompt-Anfang)
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
    idle_since: float | None = None  # Wanduhr: seit wann fertig (nur gesetzt, wenn der Übergang beobachtet wurde)
    backend: str = ""   # copi-Backend-Kennung bei gespiegelten Fern-Sitzungen (z. B. ssh-r2), sonst leer
    remote: bool = False  # läuft der Prozess auf einem anderen Rechner?

    @property
    def idle_for(self) -> float | None:
        """Sekunden seit dem Ende der letzten Arbeit (None = unbekannt, z. B. schon beim Start untätig)."""
        return None if self.idle_since is None else max(0.0, time.time() - self.idle_since)


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


_SKILL_NAMES: set[str] | None = None


def skill_names() -> set[str]:
    """Installierte Skill-Namen (Verzeichnisname = Skill-Name)."""
    global _SKILL_NAMES
    if _SKILL_NAMES is None:
        names = set()
        for base in SKILL_DIRS:
            if not os.path.isdir(base):
                continue
            for dirpath, dirnames, files in os.walk(base):
                if "SKILL.md" in files:
                    names.add(os.path.basename(dirpath).lower())
        _SKILL_NAMES = names
    return _SKILL_NAMES


def skill_from_prompt(prompt: str) -> str:
    """Erkannter Skill aus dem Prompt: `/skill:name` bzw. `/name` am Anfang oder das erste Wort,
    wenn es ein installierter Skill ist (deutsche Prompts beginnen oft mit dem Skillnamen)."""
    text = (prompt or "").strip()
    m = re.match(r"/(?:skill:)?([a-zA-Z][a-zA-Z0-9-]{2,})", text)
    if m:
        return m.group(1).lower()
    m = re.match(r"([a-zA-Z][a-zA-Z0-9-]{4,})[,: ]", text)
    if m and m.group(1).lower() in skill_names():
        return m.group(1).lower()
    return ""


def _short_cwd(cwd: str) -> str:
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        cwd = "~" + cwd[len(home):]
    parts = cwd.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) > 2 else cwd


_NAME_CACHE: dict = {}


def session_name_from_file(path: str | None) -> str | None:
    """Letzter `session_info`-Name aus der Sitzungsdatei (der Name wird mit /name gesetzt, die Live-Datei kennt ihn evtl. nicht)."""
    if not path or not os.path.isfile(path):
        return None
    mt = os.path.getmtime(path)
    hit = _NAME_CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    name = None
    for line in _tail_lines(path):
        if '"session_info"' in line:
            try:
                n = json.loads(line).get("name")
            except ValueError:
                continue
            if n:
                name = n
    _NAME_CACHE[path] = (mt, name)
    return name


def agent_from_state(s: dict, backend: str = "") -> Agent:
    ctx = s.get("context") or {}
    tok = s.get("tokens") or {}
    comp = s.get("compaction") or {}
    le = s.get("lastError") or {}
    title = s.get("sessionName") or session_name_from_file(s.get("sessionFile")) or _short_cwd(s.get("cwd") or "?")
    pid = s.get("pid")
    return Agent(
        key=f"remote:{backend}:{pid}" if backend else f"pid:{pid}",
        title=title,
        source="live",
        backend=backend,
        remote=bool(backend),
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
        skill=skill_from_prompt(s.get("prompt", "")),
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


def _group_states(states: dict, backend: str = "") -> tuple[list[Agent], set[str]]:
    """Aus Live-Dateien Panels bauen: Prozesse, deren ppid selbst eine Live-Datei hat, sind Subagent-Kinder."""
    sessions = {s["sessionFile"] for s in states.values() if s.get("sessionFile")}
    tops, kids = [], {}
    for pid, s in states.items():
        if s.get("ppid") in states:
            kids.setdefault(s["ppid"], []).append(s)
        else:
            tops.append(s)
    agents = []
    for s in sorted(tops, key=lambda x: x.get("started", 0)):
        a = agent_from_state(s, backend=backend)
        a.children = sorted(kids.get(s["pid"], []), key=lambda x: x.get("started", 0))
        agents.append(a)
    return agents, sessions


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
    return _group_states(states)


def mirror_dirs(root: str = MIRROR_ROOT) -> list[tuple[str, str]]:
    """Spiegelordner entfernter Backends: (backend-id, Pfad). Das lokale Live-Verzeichnis ist dabei
    ausgenommen, damit ein versehentlich hineinkopierter Spiegel keine Panels verdoppelt."""
    extra = [p for p in (os.environ.get(MIRROR_ENV) or "").split(os.pathsep) if p.strip()]
    found = []
    for base, sub in [(root, True)] + [(p, False) for p in extra]:
        if not os.path.isdir(base):
            continue
        if sub:
            for name in sorted(os.listdir(base)):
                d = os.path.join(base, name)
                if os.path.isdir(d) and os.path.abspath(d) != os.path.abspath(RUNTIME_DIR):
                    found.append((name, d))
        elif os.path.abspath(base) != os.path.abspath(RUNTIME_DIR):
            found.append((os.path.basename(base.rstrip("/")) or base, base))
    return found


def read_mirrors(now: float | None = None, fresh_s: float = MIRROR_FRESH_S,
                 dirs: list[tuple[str, str]] | None = None) -> tuple[list[Agent], set[str]]:
    """Spiegel entfernter Backends lesen (copi zieht sie per rsync auf diesen Rechner).

    Entfernte PIDs gibt es lokal nicht – deshalb entscheidet hier die Schreibfrische statt
    `pid_alive`. Zusätzlich zu den Top-Level-Agenten kommen ihre Subagent-Kinder mit: copi
    spiegelt das ganze Verzeichnis, die `ppid`-Verknüpfung bleibt also erhalten."""
    now = time.time() if now is None else now
    dirs = mirror_dirs() if dirs is None else dirs
    agents: list[Agent] = []
    sessions: set[str] = set()
    for backend, d in dirs:
        states = {}
        # copi legt je Quellverzeichnis des Servers einen Unterordner an (Laufzeitverzeichnis und
        # Ausweichpfad getrennt, weil `--delete` sie sonst gegenseitig leeren würde). Beide gehören
        # zum selben Backend: erst zusammen ergibt die `ppid`-Verknüpfung vollständige Panels.
        # Rekursiv, damit die Zahl der Zwischenebenen (Backend/Wurzel-Quellordner) keine Rolle spielt.
        files = glob.glob(os.path.join(d, "**", "*.json"), recursive=True)
        for f in files:
            try:
                if now - os.path.getmtime(f) > fresh_s:
                    continue
                with open(f) as fh:
                    s = json.load(fh)
            except Exception:
                continue
            pid = s.get("pid")
            if s.get("v") != 1 or not isinstance(pid, int):
                continue
            states[pid] = s
        part, sess = _group_states(states, backend=backend)
        agents.extend(part)
        sessions |= sess
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
    a.skill = skill_from_prompt(a.prompt)
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


def sync_remote(force: bool = False, now: float | None = None) -> bool:
    """Spiegel der Fern-Zustände auffrischen, indem copi kurz `--sync-states` ausführt.

    Der Screensaver läuft, wenn copi geschlossen ist; die SSH-Konfiguration und das Token liegen
    aber in copi. Deshalb ruft agentscope copi als kurzen Unterprozess auf (headless, nur lesend)
    und liest danach den lokalen Spiegel. Nicht blockierend: der Unterprozess läuft in einem
    eigenen Thread, und höchstens alle `MIRROR_SYNC_S` Sekunden.

    Rückgabe: ob diesmal gestartet wurde.
    """
    global _SYNC_LAST, _SYNC_BUSY
    if (os.environ.get(SYNC_OFF_ENV) or "").lower() in ("off", "0", "false", "nein"):
        return False
    now = time.time() if now is None else now
    if _SYNC_BUSY or (not force and now - _SYNC_LAST < MIRROR_SYNC_S):
        return False
    binary = _sync_binary()
    if not binary:
        return False
    _SYNC_LAST = now
    _SYNC_BUSY = True

    def work():
        global _SYNC_BUSY
        try:
            subprocess.run([binary, "--sync-states"], capture_output=True, timeout=120)
        except Exception:
            pass
        finally:
            _SYNC_BUSY = False

    threading.Thread(target=work, daemon=True).start()
    return True


def _sync_binary() -> str | None:
    """Programm für die Spiegel-Auffrischung finden (ausdrücklich gesetzt oder im PATH)."""
    explicit = (os.environ.get(SYNC_ENV) or "").strip()
    if explicit:
        p = explicit if os.path.isabs(explicit) else shutil.which(explicit)
        return p if p and os.access(p, os.X_OK) else None
    for name in SYNC_BINS:
        p = shutil.which(name)
        if p and _knows_sync(p):
            return p
    return None


def _knows_sync(path: str) -> bool:
    """Nur Programme starten, die `--sync-states` kennen. Ein älterer Build würde das Argument
    ignorieren und stattdessen sein Fenster öffnen – bei jedem Takt eine neue Instanz."""
    try:
        with open(path, "rb") as fh:
            return b"--sync-states" in fh.read()
    except OSError:
        return False


def collect(now: float | None = None) -> list[Agent]:
    """Alle Harnessse: pi (live, sonst Log) zuerst, dann gespiegelte Fern-Backends, dann Claude Code und Codex."""
    live, sessions = read_live()
    mirror, mirror_sessions = read_mirrors(now=now)
    pi = live + read_sessions(sessions, now=now)
    # Fern-Sitzungen decken keine lokalen Logs ab (die Pfade liegen auf dem anderen Rechner): eigene Menge,
    # damit ein gespiegelter Agent nicht als lokales Log-Panel doppelt erscheint.
    fern = read_sessions(mirror_sessions, now=now) if mirror_sessions else []
    from . import harnesses
    return pi + mirror + fern + harnesses.read_claude(now=now) + harnesses.read_codex(now=now)


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
    if a_phase == "idle":
        a.idle_since = time.time() - (cyc - 9 * 4.8)
    c = Agent(key="demo:3", title="more-re", source="demo", phase="idle", prompt=DEMO_PROMPTS[2], model="claude-sonnet-5-5",
              ctx_tokens=20000, ctx_window=200000, ctx_percent=10, tok_total=120000, updated=time.time())
    d = Agent(key="demo:4", title="vault", source="demo", harness="claude", skill="vaultdev", phase=["streaming", "tool", "thinking"][int(t / 6) % 3],
              prompt="vaultdev", model="claude-opus-5-5", turn=int(t / 5),
              ctx_tokens=88000, ctx_window=200000, ctx_percent=44, tok_total=int(t * 900) % 500000,
              rate=max(0.0, 30 + 20 * math.sin(t * 0.9)),
              tools=[{"name": "bash", "label": "cargo test", "started": 0}] if int(t / 6) % 3 == 1 else [],
              tool_counts={"bash": 7, "edit": 5}, errors=1, last_error="cargo: linking failed",
              events=[{"seq": 1, "kind": "tool", "text": "bash: cargo test", "at": 0}], updated=time.time())
    e = Agent(key="demo:5", title="pi-hub", source="demo", harness="codex", phase=["thinking", "tool"][int(t / 7) % 2],
              prompt="refactor the hub", model="gpt-6.1-sol", turn=int(t / 8),
              ctx_tokens=150000, ctx_window=475000, ctx_percent=32, tok_total=int(t * 400) % 300000, rate=max(0.0, 12 + 8 * math.sin(t * 1.4)),
              tools=[{"name": "exec", "label": "rg token_count", "started": 0}] if int(t / 7) % 2 else [],
              tool_counts={"exec": 11}, events=[{"seq": 1, "kind": "tool", "text": "exec: rg token_count", "at": 0}], updated=time.time())
    return [a, b, c, d, e]
