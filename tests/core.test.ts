import assert from "node:assert/strict";
import { test } from "node:test";
import { parseSubagentDetails, toolLabel, Tracker } from "../extension/core.ts";

const mk = () => new Tracker({ pid: 10, ppid: 1, cwd: "/w", now: 0 });

test("toolLabel kürzt sinnvoll", () => {
	assert.equal(toolLabel("read", { path: "/a/b/main.rs" }), "main.rs");
	assert.equal(toolLabel("subagent", { tasks: [{}, {}, {}] }), "3 parallel");
	assert.ok(toolLabel("bash", { command: "x".repeat(100) }).length <= 48);
});

test("Tool-Lebenszyklus und Phase", () => {
	const t = mk();
	t.agentStart(1);
	assert.equal(t.state.phase, "thinking");
	t.toolStart("a", "bash", { command: "ls" }, 2);
	assert.equal(t.state.phase, "tool");
	assert.equal(t.state.tools.length, 1);
	t.toolEnd("a", "bash", { content: [{ type: "text", text: "boom" }] }, true, 3);
	assert.equal(t.state.tools.length, 0);
	assert.equal(t.state.errors, 1);
	assert.match(t.state.lastError!.msg, /boom/);
	assert.equal(t.state.events.at(-1)!.kind, "tool_error");
	t.settled(4);
	assert.equal(t.state.phase, "idle");
});

test("Tokens summieren und Rate schätzen", () => {
	const t = mk();
	t.assistantEnd({ usage: { input: 100, output: 20, totalTokens: 120 }, model: "m" }, 1);
	t.assistantEnd({ usage: { input: 50, output: 5, totalTokens: 55 } }, 2);
	assert.equal(t.state.tokens.input, 150);
	assert.equal(t.state.tokens.total, 175);
	for (let i = 0; i < 10; i++) t.streamDelta("text_delta", "abcdefgh", 1000 + i * 100); // 10×2 Tok
	assert.equal(t.rate(2000), 5); // 20 Tok / 4 s
	assert.equal(t.rate(10_000), 0);
});

test("Modellfehler zählt als Fehler", () => {
	const t = mk();
	t.assistantEnd({ stopReason: "error", errorMessage: "401 invalid token" }, 1);
	assert.equal(t.state.errors, 1);
	assert.equal(t.state.phase, "error");
	t.settled(2);
	assert.equal(t.state.phase, "error", "Fehlerphase bleibt bis zum nächsten Lauf sichtbar");
	t.agentStart(3);
	assert.equal(t.state.phase, "thinking");
});

test("Kompaktierung", () => {
	const t = mk();
	t.compactStart("threshold", 150_000, 1);
	assert.equal(t.state.phase, "compacting");
	assert.ok(t.state.compaction.active);
	t.compactEnd({ tokensBefore: 150_000, estimatedTokensAfter: 30_000 }, 2);
	assert.equal(t.state.compaction.active, false);
	assert.equal(t.state.compaction.count, 1);
	assert.equal(t.state.compaction.tokensAfter, 30_000);
	t.compactStart("overflow", null, 3);
	t.compactFailed("terminated", 4);
	assert.equal(t.state.errors, 1);
	assert.equal(t.state.compaction.active, false);
});

test("Retry", () => {
	const t = mk();
	t.retryStart(1, 3, "529 overloaded", 1);
	assert.equal(t.state.phase, "retrying");
	t.retryEnd(false, 2);
	assert.equal(t.state.retry, null);
	assert.equal(t.state.errors, 1);
});

test("Subagent-Fortschritt aus partial details", () => {
	const t = mk();
	t.toolStart("s", "subagent", { tasks: [{}, {}, {}] }, 1);
	assert.equal(t.state.subagentRuns[0].total, 3);
	t.toolUpdate(
		"s",
		"subagent",
		{
			details: {
				mode: "parallel",
				results: [
					{ agent: "worker", task: "A", exitCode: 0, usage: { input: 10, output: 5, turns: 2 }, messages: [{ role: "assistant", stopReason: "stop", content: [] }] },
					{
						agent: "worker",
						task: "B",
						exitCode: -1,
						usage: { turns: 1 },
						messages: [{ role: "assistant", content: [{ type: "toolCall", name: "read", arguments: { path: "/x/y.rs" } }] }],
					},
					{ agent: "scout", task: "C", exitCode: 1, errorMessage: "401", usage: {}, messages: [] },
				],
			},
		},
		2,
	);
	const r = t.state.subagentRuns[0];
	assert.deepEqual([r.done, r.running, r.failed, r.total], [1, 1, 1, 3]);
	assert.equal(r.agents[1].lastTool, "read: y.rs");
	assert.equal(r.agents[0].tokens, 15);
	t.toolEnd("s", "subagent", { details: { mode: "parallel", results: [] } }, false, 3);
	assert.ok(t.state.subagentRuns[0].finished);
});

test("Single-Subagent ohne Details bleibt sichtbar", () => {
	const r = parseSubagentDetails("x", { mode: "single", results: [{ agent: "a", task: "t", exitCode: -1, usage: {} }] }, false, 1);
	assert.equal(r!.running, 1);
	assert.equal(parseSubagentDetails("x", undefined, false), null);
});

test("Ereignisliste ist begrenzt", () => {
	const t = mk();
	for (let i = 0; i < 100; i++) t.toolStart(`i${i}`, "read", { path: `f${i}` }, i);
	assert.equal(t.state.events.length, 40);
	assert.equal(t.state.toolCounts.read, 100);
});

test("Regression: leere tasks-Liste ist kein '0 parallel'", () => {
	assert.equal(toolLabel("subagent", { agent: "worker", tasks: [] }), "worker");
	const t = mk();
	t.toolStart("s", "subagent", { agent: "worker", tasks: [], chain: [] }, 1);
	assert.equal(t.state.subagentRuns[0].total, 1);
	assert.equal(t.state.subagentRuns[0].mode, "single");
});

test("Regression: laufender Subagent mit exitCode 0 gilt nicht als fertig", () => {
	const mid = { agent: "w", task: "t", exitCode: 0, usage: {}, messages: [{ role: "assistant", stopReason: "toolUse", content: [] }] };
	const fin = { agent: "w", task: "t", exitCode: 0, usage: {}, messages: [{ role: "assistant", stopReason: "stop", content: [] }] };
	const empty = { agent: "w", task: "t", exitCode: 0, usage: {}, messages: [] };
	const r = parseSubagentDetails("x", { mode: "parallel", results: [mid, fin, empty] }, false, 3)!;
	assert.deepEqual(r.agents.map((a) => a.status), ["running", "done", "running"]);
	const f = parseSubagentDetails("x", { mode: "parallel", results: [mid, fin, empty] }, true, 3)!;
	assert.equal(f.done, 3);
});
