/**
 * scry-guard — provenance enforcement for Prime Agent's continual harness.
 *
 * A Prime Agent extension. Node builtins only, no dependencies.
 *
 * ── Why this exists, and why it enforces where it does ──────────────────────
 * Prime Agent's `/refine` writes durable state — including `skill` entries that
 * are executable Python the agent is instructed to import and call. The auto-
 * refine reviewer decides what to persist by reading the trajectory, which
 * contains fetched pages, repo files, and subagent replies. So untrusted text
 * can become executable, cross-session state.
 *
 * The extension API has no pre-write refinement hook. `refine_complete` fires
 * with `appliedEdits` already applied — after the fact. So a gate cannot
 * intercept the write.
 *
 * It does not need to. **A poisoned skill sitting in harness_state.json is
 * inert; importing and calling it is where the harm happens** — and that runs
 * through `ipython` or `bash`, which the `tool_call` hook CAN block
 * (`ToolCallEventResult.block`). This extension therefore enforces provenance
 * at the point of execution rather than the point of storage:
 *
 *   an executable skill the agent wrote ABOUT ITSELF may not run
 *   until a human has read it and signed off.
 *
 * Prime Agent already records exactly the fact this needs, per entry:
 * `source: "refine"` marks state the model authored (refinement.ts:772).
 *
 * Three rules:
 *   1. EXECUTION   a tool call referencing a refine-authored `skill` is blocked
 *                  unless that skill's id is in the approvals file. Fails
 *                  closed: an unreadable or missing approvals file approves
 *                  nothing.
 *   2. BYPASS      a tool call that writes harness_state.json directly is
 *                  blocked outright. Refinement is the sanctioned path; a
 *                  direct write is the agent editing its own bound behind it.
 *   3. JOURNAL     `refine_complete` is recorded — it cannot be blocked, so the
 *                  answer is an audit trail that makes an unnoticed global
 *                  executable write loud instead of silent.
 *
 * ── The honest limit (do not soften) ────────────────────────────────────────
 * This gates the SANCTIONED path: the agent importing the skill the harness
 * told it about. It does not stop the model from inlining the same code
 * directly into an `ipython` call — nothing short of a sandbox does, and Prime
 * Agent's README is explicit that it is not one. What it buys is that the
 * automatic path — refine writes a skill, a later session imports it because
 * the system prompt says to — stops being a way for a fetched page to reach
 * `subprocess.run` without a human ever seeing it.
 *
 * ── Install ─────────────────────────────────────────────────────────────────
 *   prime-agent --extension /path/to/scry-guard.ts
 * or copy into an extension directory Prime Agent discovers.
 *
 * Approvals file (default ~/.prime/agent/scry-approved-skills.json):
 *   { "approved": ["changelog_helper"], "note": "read each before adding" }
 */

import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

// Structural types, declared locally rather than imported from Prime Agent's
// source tree, so this file drops into any extension directory without a
// relative path back into the package. They are the subset this guard uses of
// `ExtensionAPI` / `ExtensionFactory` (core/extensions/types.ts) — the real
// `on()` is a much wider overload set, and `ToolCallEventResult` is
// `{block?: boolean; reason?: string}` verbatim.
type ToolCallEvent = { type: "tool_call"; toolCallId: string; toolName: string; input?: unknown };
type ToolCallEventResult = { block?: boolean; reason?: string };
type RefineCompleteEvent = {
	type: "refine_complete";
	id: string;
	summary: string;
	appliedEdits: number;
	scope: "global" | "local";
};
type ExtensionAPI = {
	on(event: "tool_call", h: (e: ToolCallEvent) => ToolCallEventResult | void): void;
	on(event: "refine_complete", h: (e: RefineCompleteEvent) => void): void;
};
type ExtensionFactory = (pi: ExtensionAPI) => void | Promise<void>;

type HarnessEntry = {
	id?: string;
	kind?: string;
	title?: string;
	content?: string;
	scope?: string;
	source?: string;
	reference?: Record<string, unknown>;
};

const AGENT_DIR = process.env.PRIME_AGENT_DIR ?? join(homedir(), ".prime", "agent");
const HARNESS_STATE = join(AGENT_DIR, "harness_state.json");
const APPROVALS = process.env.SCRY_APPROVALS ?? join(AGENT_DIR, "scry-approved-skills.json");
const JOURNAL = process.env.SCRY_JOURNAL ?? join(AGENT_DIR, "scry-guard-journal.jsonl");

/** Tools whose payload can execute code or write files. */
const GATED_TOOLS = new Set(["ipython", "bash", "edit"]);

function readJson(path: string): unknown {
	try {
		return JSON.parse(readFileSync(path, "utf8"));
	} catch {
		return undefined;
	}
}

/**
 * Flatten the harness store. The real file (schema 1) nests kind buckets under
 * `entries`; the flat shape is also accepted so a hand-written or migrated
 * state stays readable rather than silently empty. Silently-empty is the
 * failure that matters here — it would approve everything by finding nothing
 * to gate.
 */
function harnessEntries(state: unknown): HarnessEntry[] {
	if (!state || typeof state !== "object") return [];
	const root = state as Record<string, unknown>;
	const buckets = (root.entries && typeof root.entries === "object" ? root.entries : root) as Record<
		string,
		unknown
	>;
	const out: HarnessEntry[] = [];
	for (const kind of ["prompt", "memory", "skill", "subagent"]) {
		const bucket = buckets?.[kind];
		if (!bucket || typeof bucket !== "object") continue;
		for (const [id, entry] of Object.entries(bucket as Record<string, unknown>)) {
			if (entry && typeof entry === "object") {
				out.push({ ...(entry as HarnessEntry), kind, id: (entry as HarnessEntry).id ?? id });
			}
		}
	}
	return out;
}

/** Skills the model wrote about itself: executable, and `source: "refine"`. */
function refineAuthoredSkills(): HarnessEntry[] {
	return harnessEntries(readJson(HARNESS_STATE)).filter(
		(e) => e.kind === "skill" && e.source === "refine",
	);
}

/** Fails closed: an unreadable or absent approvals file approves nothing. */
function approvedIds(): Set<string> {
	const raw = readJson(APPROVALS) as { approved?: unknown } | undefined;
	const list = Array.isArray(raw?.approved) ? raw.approved : [];
	return new Set(list.filter((x): x is string => typeof x === "string"));
}

function esc(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function mentionsName(text: string, name: string): boolean {
	return new RegExp(`\\b${esc(name)}\\b`).test(text);
}

/**
 * Patterns that mean "this code invokes that skill".
 *
 * Module-level identifiers (`id`, `reference.import`, `reference.module`) are
 * matched bare: they are namespaced names a refinement chose, so a whole-word
 * hit is good evidence.
 *
 * `reference.callable` is deliberately NOT matched bare. A first pass did, and
 * the first real Prime Agent run under this guard found the bug immediately —
 * the skill's callable was `setup`, so the gate refused *any* cell containing
 * the word "setup". That is not a gate, it is an off switch, which is the one
 * failure mode this whole skill argues against. A callable only counts when
 * qualified by its module: `project_setup.setup(...)` or
 * `from project_setup import setup`.
 */
function invocationPatterns(entry: HarnessEntry): { label: string; re: RegExp }[] {
	const ref = (entry.reference ?? {}) as Record<string, unknown>;
	const str = (v: unknown) => (typeof v === "string" && v.trim().length > 2 ? v.trim() : undefined);

	const modules = [str(entry.id), str(ref.import), str(ref.module)].filter(
		(n): n is string => n !== undefined,
	);
	const callable = str(ref.callable);
	const out: { label: string; re: RegExp }[] = [];

	for (const m of new Set(modules)) {
		out.push({ label: m, re: new RegExp(`\\b${esc(m)}\\b`) });
	}
	// Qualified callable: only alongside its module, never alone.
	if (callable) {
		for (const m of new Set(modules)) {
			out.push({
				label: `${m}.${callable}`,
				re: new RegExp(`\\b${esc(m)}\\s*\\.\\s*${esc(callable)}\\b|\\bfrom\\s+${esc(m)}\\s+import\\b[^\\n]*\\b${esc(callable)}\\b`),
			});
		}
	}
	return out;
}

/** Everything in a tool call payload a reader would treat as code or a path. */
function payloadText(input: unknown): string {
	if (typeof input === "string") return input;
	try {
		return JSON.stringify(input ?? {});
	} catch {
		return String(input ?? "");
	}
}

function journal(record: Record<string, unknown>): void {
	try {
		mkdirSync(dirname(JOURNAL), { recursive: true });
		appendFileSync(JOURNAL, `${JSON.stringify(record)}\n`, "utf8");
	} catch {
		// A guard that crashes the agent because it could not write its own log
		// is worse than a guard with a gap in its log. Enforcement continues.
	}
}

const factory: ExtensionFactory = (pi: ExtensionAPI) => {
	pi.on("tool_call", (event) => {
		if (!GATED_TOOLS.has(event.toolName)) return;
		const text = payloadText((event as { input?: unknown }).input);

		// Rule 2 — a direct write to the bound, behind refinement's back.
		if (mentionsName(text, "harness_state") && /\b(w|a|w\+|a\+)\b|>>|>|write|dump|edit|patch|sed|tee/.test(text)) {
			const reason =
				"scry-guard: refused a direct write to harness_state.json. That file is the " +
				"agent's own bound; refinement is the sanctioned path for changing it, and a " +
				"direct write goes behind that path. If this is intended, a human should make " +
				"the edit.";
			journal({ rule: "bypass", tool: event.toolName, blocked: true });
			return { block: true, reason };
		}

		// Rule 1 — executing model-authored executable state.
		const skills = refineAuthoredSkills();
		if (skills.length === 0) return;
		const approved = approvedIds();

		for (const skill of skills) {
			if (approved.has(skill.id ?? "")) continue;
			const hit = invocationPatterns(skill).find((p) => p.re.test(text))?.label;
			if (!hit) continue;

			const reason =
				`scry-guard: refused to run the continual-harness skill '${skill.id}' ` +
				`(matched '${hit}'). It is executable Python that this agent wrote about ` +
				`itself (source: "refine"${skill.scope ? `, scope: ${skill.scope}` : ""}), and no ` +
				`human has approved it. A skill written by auto-refine can be derived from a ` +
				`fetched page, a repo file, or a subagent reply — provenance the harness does ` +
				`not track. Read it, then add "${skill.id}" to ${APPROVALS} to allow it.`;
			journal({
				rule: "execution",
				tool: event.toolName,
				skill: skill.id,
				scope: skill.scope,
				matched: hit,
				blocked: true,
			});
			return { block: true, reason };
		}
	});

	// Rule 3 — refinement cannot be blocked (this fires after `appliedEdits`),
	// so make it loud. A global executable write is the one worth seeing.
	pi.on("refine_complete", (event) => {
		const executable = refineAuthoredSkills().map((s) => s.id);
		journal({
			rule: "refine_complete",
			id: event.id,
			summary: event.summary,
			appliedEdits: event.appliedEdits,
			scope: event.scope,
			executable_skills_now_present: executable,
			note:
				"refine_complete fires after the write; this is an audit record, not an " +
				"interception. Execution of any unapproved skill above is still refused.",
		});
	});
};

export default factory;
