# AgentLife – an xkcd-style screensaver for AI agents (pi, Claude Code, Codex)

[Deutsche Fassung](README.md) · The program and Python package are called `agentscope`.

A fullscreen screensaver for [Omarchy](https://omarchy.org) (Arch Linux + Hyprland). It draws
what **all running agents** are doing right now as hand-drawn stick-figure comic panels in the
style of xkcd: sub-agents and workers, live token consumption (speedometer), context fill,
context compaction ("squeezing"), retries and errors. The UI text is German; code identifiers are English.

![Demo](docs/demo.png)

## Data sources

- **pi** – live, through a small extension (`extension/`) that writes one JSON state file per process
  to `$XDG_RUNTIME_DIR/agentscope/<pid>.json` (schema: [docs/STATE.md](docs/STATE.md)).
- **Claude Code** and **Codex** – read from their session logs (no live token rate).
- **Remote pi sessions** (SSH servers) – mirrored read-only through the `copi`/`cocopi` helper
  (`--sync-states`, from the [pi-lite](https://github.com/KGasteier/pi-lite) project). Optional.

## Install

```bash
git clone https://github.com/KGasteier/AgentLife.git ~/Work/AgentLife && bash ~/Work/AgentLife/install.sh          # --no-hypr leaves the Hyprland config alone
agentscope --demo --windowed                        # try it without any agents
```

`install.sh` links the launcher and the pi extension, adds the keybind **SUPER + Z** and a fullscreen
window rule to the Hyprland config (with backups). Requirements: python3 with GTK 4 (PyGObject) and pycairo.

## Use

| What | Command |
|---|---|
| Toggle screensaver | **SUPER + Z** (press again to close) |
| Demo without agents | `agentscope --demo` |
| Windowed | `agentscope --windowed` |
| Low CPU | `agentscope --fps 4` (default 8) |
| PNG preview | `python3 -m agentscope.snapshot out.png [--demo]` |

Active agents get a second pink outline with a soft shadow; the needle value (tokens/s) is shown large below the gauge.

## Tests

```bash
python3 -m unittest discover -s tests
node --test tests/
```

## Fonts

Bundled: *Steel Umlaut City* (derived from *Steel City Comic*, credit to Steel City; see
`agentscope/fonts/README.md`) and *Kalam* (SIL OFL, `agentscope/fonts/OFL.txt`).

## License

Code: [MIT](LICENSE). The bundled fonts keep their own terms: *Steel Umlaut City* is derived from
*Steel City Comic* (free to use and share, credit "Steel City"; see `agentscope/fonts/README.md`),
*Kalam* is under the SIL OFL (`agentscope/fonts/OFL.txt`).
