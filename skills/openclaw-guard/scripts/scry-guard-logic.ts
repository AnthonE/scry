// scry-guard's pure decision logic — no OpenClaw SDK imports, so it can be
// unit tested directly (scry-guard.test.ts) without the host runtime's
// module resolution. scry-guard.ts imports this and wires it to real hooks.
export const AUTHORIZE_TOOL = "scry-sidecar__authorize_action";

// Staleness cap on an unconsumed authorization. Single-use consumption is
// the real guard; this just bounds how long a never-used authorization can
// sit around before decideBeforeToolCall stops honoring it.
export const DEFAULT_AUTH_MAX_AGE_MS = 2 * 60 * 1000;

export type PluginConfig = {
  gatedTools?: string[];
  authMaxAgeSeconds?: number;
};

// liveText is the text that earned this authorization — kept (not just the
// timestamp) so robinhood-guard-logic.ts's decideBeforeRobinhoodPlaceCall can
// check the instruction actually names a specific order's symbol/side, not
// just that some live instruction existed this turn. Empty string if the
// authorize_action call's params didn't carry a recognizable live.text.
export type PendingAuth = { authorizedAt: number; liveText?: string };

// sessionKey -> pending auth. Presence means "one unconsumed
// authorize_action pass is waiting"; decideBeforeToolCall deletes the entry
// the moment it spends it (single-use).
export type PendingAuthMap = Map<string, PendingAuth>;

export function sessionKeyOf(ctx: { sessionKey?: string; sessionId?: string; runId?: string }): string {
  return ctx.sessionKey ?? ctx.sessionId ?? ctx.runId ?? "default";
}

export function extractToolResultText(result: unknown): string {
  if (result && typeof result === "object" && Array.isArray((result as { content?: unknown }).content)) {
    const content = (result as { content: Array<{ type?: string; text?: string }> }).content;
    return content
      .map((c) => (c && typeof c.text === "string" ? c.text : ""))
      .join("");
  }
  if (typeof result === "string") return result;
  try {
    return JSON.stringify(result ?? {});
  } catch {
    return "";
  }
}

/** Pulls live.text back out of the params an authorize_action call was made
 * with (not its result — the caller supplies {live: {text, source, role}}).
 * Kept here (not robinhood-guard-logic.ts) to avoid a circular import: that
 * module imports PendingAuthMap/AUTHORIZE_TOOL from this one. */
function _extractLiveText(authorizeActionParams: unknown): string {
  if (authorizeActionParams && typeof authorizeActionParams === "object") {
    const live = (authorizeActionParams as { live?: unknown }).live;
    if (live && typeof live === "object" && typeof (live as { text?: unknown }).text === "string") {
      return (live as { text: string }).text;
    }
  }
  return "";
}

/** after_tool_call logic: record or clear a pending authorization for `key`.
 * `params` is the authorize_action call's own arguments (needed to recover
 * live.text for robinhood-guard-logic.ts's order-matching; unused by the
 * plain gated_tools path, which only ever needed the pass/fail result). */
export function recordAuthorizationResult(
  pendingAuth: PendingAuthMap,
  key: string,
  toolName: string,
  params: unknown,
  result: unknown,
  now: number,
): void {
  if (toolName !== AUTHORIZE_TOOL) return;
  let ok = false;
  try {
    const parsed = JSON.parse(extractToolResultText(result));
    ok = parsed?.authorized === true;
  } catch {
    ok = false;
  }
  if (ok) {
    pendingAuth.set(key, { authorizedAt: now, liveText: _extractLiveText(params) });
  } else {
    pendingAuth.delete(key);
  }
}

/**
 * before_tool_call logic: allow (undefined) or block (`{block, blockReason}`)
 * a gated tool call, consuming any pending authorization for `key` on read
 * regardless of outcome (single-use, pass or fail).
 */
export function decideBeforeToolCall(
  pendingAuth: PendingAuthMap,
  key: string,
  toolName: string,
  gatedTools: Set<string>,
  authMaxAgeMs: number,
  now: number,
): { block: true; blockReason: string } | undefined {
  if (!gatedTools.has(toolName)) return undefined;
  const pending = pendingAuth.get(key);
  pendingAuth.delete(key);
  if (pending && now - pending.authorizedAt <= authMaxAgeMs) {
    return undefined; // authorized, single use spent — let it through
  }
  return {
    block: true,
    blockReason: `scry-guard: call ${AUTHORIZE_TOOL} with a live trusted instruction immediately before ${toolName} (single-use — call it again for each gated action).`,
  };
}
