# Zustandsdatei – Schema v1

Pfad: `$XDG_RUNTIME_DIR/agentscope/<pid>.json`, geschrieben von `extension/index.ts`
(atomar über `.tmp` + rename, höchstens alle 250 ms, Herzschlag alle 2 s, gelöscht bei `session_shutdown`).

| Feld | Typ | Bedeutung |
|---|---|---|
| `v` | 1 | Schemaversion |
| `pid`, `ppid` | int | Prozess; `ppid` mit eigener Datei ⇒ Subagent-Kind |
| `started`, `updated` | ms | Zeitstempel |
| `cwd`, `sessionFile`, `sessionName`, `model` | string | Kontext |
| `phase` | `idle·thinking·streaming·tool·compacting·retrying·error` | aktuelle Tätigkeit |
| `prompt`, `turn` | | letzter Nutzerprompt (gekürzt), Turn-Index |
| `context` | `{tokens, window, percent}` | aus `ctx.getContextUsage()` |
| `tokens` | `{input, output, cacheRead, total, rateOut}` | Summen aus `message_end`-Usage; `rateOut` = geschätzte Ausgabe-Token/s (Deltas/4 Zeichen, 4-s-Fenster) |
| `tools` | `[{id, name, label, started}]` | laufende Werkzeuge |
| `toolCounts` | `{name: n}` | Aufrufe je Werkzeug |
| `errors`, `lastError` | int, `{msg, at}` | Tool-Fehler, Modellfehler, gescheiterte Kompaktierung/Retries |
| `compaction` | `{active, reason, tokensBefore, tokensAfter, at, count}` | |
| `retry` | `{attempt, max, error}` oder null | automatischer Retry läuft |
| `subagentRuns` | `[{toolCallId, mode, total, done, running, failed, finished, agents[]}]` | aus `details` des subagent-Werkzeugs (partial + final), max. 4 |
| `events` | `[{seq, at, kind, text}]` | letzte 40 Ereignisse; `kind`: input, tool, tool_error, error, compact, compact_failed, retry, subagent, done |

Hinweis: Die subagent-Erweiterung meldet `exitCode: 0` schon während des Laufs. Ein Teilergebnis gilt
erst als fertig, wenn die letzte Nachricht eine Assistent-Antwort mit `stopReason ≠ toolUse` ist.
