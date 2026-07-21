// robinhood-guard-logic.ts — pure port of scry's robinhood_agentic.py
// (ReviewLedger + authorize_trade) onto OpenClaw's before/after_tool_call
// hooks, layered on top of scry-guard-logic.ts's generic authorize-gate.
//
// The generic gate (scry-guard-logic.ts) only asks "did SOME live trusted
// instruction pass authorize_action this turn". That's a no-op protection
// for an order-placing tool by itself — it doesn't check the instruction
// actually named THIS order, and it doesn't require a review step first
// (Robinhood's own recommended review_equity_order -> place_equity_order
// pairing is optional on their side, not enforced). This module adds both,
// mirroring robinhood_agentic.py's ReviewLedger + authorize_trade exactly —
// see ../../robinhood_agentic.py in the scry repo, keep them in lock-step.
import { AUTHORIZE_TOOL, type PendingAuthMap } from "./scry-guard-logic.ts";

export type Order = {
  symbol?: string;
  side?: string;
  quantity?: string | number;
  dollar_amount?: string | number;
};

export type OrderSignature = string;

export function orderSignature(order: Order): OrderSignature {
  const symbol = String(order.symbol ?? "").toUpperCase();
  const side = String(order.side ?? "").toLowerCase();
  const quantity = String(order.quantity ?? order.dollar_amount ?? "");
  return `${symbol}|${side}|${quantity}`;
}

// sessionKey -> set of reviewed order signatures. Mirrors ReviewLedger's
// per-instance `_reviewed` set, keyed per session the way pendingAuth is.
export type ReviewLedgerMap = Map<string, Set<OrderSignature>>;

export function recordReview(ledger: ReviewLedgerMap, key: string, order: Order): void {
  const sig = orderSignature(order);
  const set = ledger.get(key) ?? new Set<OrderSignature>();
  set.add(sig);
  ledger.set(key, set);
}

export function wasReviewed(ledger: ReviewLedgerMap, key: string, order: Order): boolean {
  return ledger.get(key)?.has(orderSignature(order)) ?? false;
}

export function orderFromParams(params: unknown): Order {
  if (params && typeof params === "object") {
    const p = params as Record<string, unknown>;
    return {
      symbol: typeof p.symbol === "string" ? p.symbol : undefined,
      side: typeof p.side === "string" ? p.side : undefined,
      quantity: typeof p.quantity === "string" || typeof p.quantity === "number" ? p.quantity : undefined,
      dollar_amount:
        typeof p.dollar_amount === "string" || typeof p.dollar_amount === "number" ? p.dollar_amount : undefined,
    };
  }
  return {};
}

export function extractLiveText(authorizeActionParams: unknown): string {
  if (authorizeActionParams && typeof authorizeActionParams === "object") {
    const live = (authorizeActionParams as { live?: unknown }).live;
    if (live && typeof live === "object" && typeof (live as { text?: unknown }).text === "string") {
      return (live as { text: string }).text;
    }
  }
  return "";
}

/** The order-specific check ON TOP OF the generic live+trusted authorize()
 * contract — that part already happened inside authorize_action itself
 * (mcp_sidecar.py's authorize_action -> hermes_retrofit.authorize), so by
 * the time we get here we already know pendingAuth represents a live
 * trusted instruction. This just checks it names THIS order. */
export function authorizeTrade(liveText: string, order: Order): { ok: boolean; reason: string } {
  const text = (liveText || "").toLowerCase();
  const symbol = String(order.symbol ?? "").toLowerCase();
  const side = String(order.side ?? "").toLowerCase();
  if (symbol && !text.includes(symbol)) {
    return { ok: false, reason: `live instruction does not name the order's symbol (${JSON.stringify(order.symbol)})` };
  }
  if (side && !text.includes(side)) {
    return { ok: false, reason: `live instruction does not express the order's side (${JSON.stringify(order.side)})` };
  }
  return { ok: true, reason: "authorized by live trusted instruction for this exact order" };
}

/** after_tool_call logic: record a successful reviewTools call into the
 * ledger. A failed/errored review call is never recorded — mirrors
 * robinhood_agentic's requirement that review actually happened. */
export function recordReviewResult(
  ledger: ReviewLedgerMap,
  key: string,
  toolName: string,
  params: unknown,
  error: string | undefined,
  reviewTools: Set<string>,
): void {
  if (!reviewTools.has(toolName)) return;
  if (error) return;
  recordReview(ledger, key, orderFromParams(params));
}

/** before_tool_call logic for a robinhoodPlaceTools call: reviewed first,
 * then a fresh pending authorization whose live text actually names this
 * order. Consumes the pending authorization on read regardless of outcome
 * (single-use, pass or fail) — same discipline as decideBeforeToolCall. */
export function decideBeforeRobinhoodPlaceCall(
  pendingAuth: PendingAuthMap,
  reviewLedger: ReviewLedgerMap,
  key: string,
  toolName: string,
  params: unknown,
  authMaxAgeMs: number,
  now: number,
): { block: true; blockReason: string } | undefined {
  const order = orderFromParams(params);

  if (!wasReviewed(reviewLedger, key, order)) {
    return {
      block: true,
      blockReason: `scry-guard: ${toolName} refused -- this order was never reviewed (call a review tool for the exact same symbol/side/quantity first).`,
    };
  }

  const pending = pendingAuth.get(key);
  pendingAuth.delete(key); // single-use — consumed on read regardless of outcome

  if (!pending || now - pending.authorizedAt > authMaxAgeMs) {
    return {
      block: true,
      blockReason: `scry-guard: call ${AUTHORIZE_TOOL} with a live trusted instruction naming this exact order (symbol + side) immediately before ${toolName}.`,
    };
  }

  const { ok, reason } = authorizeTrade(pending.liveText ?? "", order);
  if (!ok) {
    return { block: true, blockReason: `scry-guard: ${toolName} refused -- ${reason}` };
  }
  return undefined;
}
