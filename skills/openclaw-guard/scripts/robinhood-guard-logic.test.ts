// Tests for robinhood-guard-logic.ts (OpenClaw plugin's Robinhood trade
// gate). Same node:test / native-TS style as scry-guard.test.ts.
//
// Run with:
//   node --test /home/anthony/.openclaw/policies/robinhood-guard-logic.test.ts
import assert from "node:assert/strict";
import { test, describe } from "node:test";

import { AUTHORIZE_TOOL, type PendingAuthMap } from "./scry-guard-logic.ts";
import {
  orderSignature,
  recordReview,
  wasReviewed,
  orderFromParams,
  authorizeTrade,
  recordReviewResult,
  decideBeforeRobinhoodPlaceCall,
  type ReviewLedgerMap,
} from "./robinhood-guard-logic.ts";

describe("orderSignature", () => {
  test("normalizes symbol case and side case", () => {
    assert.equal(orderSignature({ symbol: "nvda", side: "BUY", quantity: "1" }), "NVDA|buy|1");
  });

  test("falls back to dollar_amount when quantity is absent", () => {
    assert.equal(orderSignature({ symbol: "NVDA", side: "buy", dollar_amount: "50" }), "NVDA|buy|50");
  });

  test("different quantity yields a different signature (no partial match)", () => {
    assert.notEqual(
      orderSignature({ symbol: "NVDA", side: "buy", quantity: "1" }),
      orderSignature({ symbol: "NVDA", side: "buy", quantity: "2" }),
    );
  });
});

describe("recordReview / wasReviewed", () => {
  test("an order is not reviewed until recorded", () => {
    const ledger: ReviewLedgerMap = new Map();
    assert.equal(wasReviewed(ledger, "sess-1", { symbol: "NVDA", side: "buy", quantity: "1" }), false);
  });

  test("recordReview makes wasReviewed true for the exact same order", () => {
    const ledger: ReviewLedgerMap = new Map();
    const order = { symbol: "NVDA", side: "buy", quantity: "1" };
    recordReview(ledger, "sess-1", order);
    assert.equal(wasReviewed(ledger, "sess-1", order), true);
  });

  test("review of one order does not cover a different quantity", () => {
    const ledger: ReviewLedgerMap = new Map();
    recordReview(ledger, "sess-1", { symbol: "NVDA", side: "buy", quantity: "1" });
    assert.equal(wasReviewed(ledger, "sess-1", { symbol: "NVDA", side: "buy", quantity: "2" }), false);
  });

  test("review is isolated per session key", () => {
    const ledger: ReviewLedgerMap = new Map();
    const order = { symbol: "NVDA", side: "buy", quantity: "1" };
    recordReview(ledger, "sess-1", order);
    assert.equal(wasReviewed(ledger, "sess-2", order), false);
  });
});

describe("orderFromParams", () => {
  test("extracts symbol/side/quantity from a tool-call params object", () => {
    const order = orderFromParams({ account_number: "824497481", symbol: "NVDA", side: "buy", quantity: "1", type: "market" });
    assert.deepEqual(order, { symbol: "NVDA", side: "buy", quantity: "1", dollar_amount: undefined });
  });

  test("returns an empty order for non-object params", () => {
    assert.deepEqual(orderFromParams(null), {});
    assert.deepEqual(orderFromParams("garbage"), {});
  });
});

describe("authorizeTrade", () => {
  test("authorizes when the live text names both symbol and side", () => {
    const { ok } = authorizeTrade("buy 1 share of NVDA", { symbol: "NVDA", side: "buy" });
    assert.equal(ok, true);
  });

  test("is case-insensitive", () => {
    const { ok } = authorizeTrade("BUY 1 SHARE OF nvda", { symbol: "NVDA", side: "buy" });
    assert.equal(ok, true);
  });

  test("refuses when the live text names a different symbol", () => {
    const { ok, reason } = authorizeTrade("buy 1 share of AAPL", { symbol: "NVDA", side: "buy" });
    assert.equal(ok, false);
    assert.match(reason, /symbol/);
  });

  test("refuses when the live text omits the side", () => {
    const { ok, reason } = authorizeTrade("NVDA please", { symbol: "NVDA", side: "buy" });
    assert.equal(ok, false);
    assert.match(reason, /side/);
  });

  test("an attacker riding a real live instruction for a DIFFERENT order still fails", () => {
    // The exact injection shape robinhood_agentic.py's own demo guards
    // against: a genuine live+trusted instruction exists this turn, but for
    // a different order than the one being placed.
    const { ok } = authorizeTrade("buy 3 shares of NVDA", { symbol: "TSLA", side: "buy" });
    assert.equal(ok, false);
  });
});

describe("recordReviewResult", () => {
  test("records a successful call to a configured review tool", () => {
    const ledger: ReviewLedgerMap = new Map();
    recordReviewResult(ledger, "sess-1", "review_equity_order", { symbol: "NVDA", side: "buy", quantity: "1" }, undefined, new Set(["review_equity_order"]));
    assert.equal(wasReviewed(ledger, "sess-1", { symbol: "NVDA", side: "buy", quantity: "1" }), true);
  });

  test("ignores a tool not in reviewTools", () => {
    const ledger: ReviewLedgerMap = new Map();
    recordReviewResult(ledger, "sess-1", "some_other_tool", { symbol: "NVDA", side: "buy", quantity: "1" }, undefined, new Set(["review_equity_order"]));
    assert.equal(ledger.size, 0);
  });

  test("does not record a failed/errored review call", () => {
    const ledger: ReviewLedgerMap = new Map();
    recordReviewResult(
      ledger,
      "sess-1",
      "review_equity_order",
      { symbol: "NVDA", side: "buy", quantity: "1" },
      "broker rejected the preview",
      new Set(["review_equity_order"]),
    );
    assert.equal(wasReviewed(ledger, "sess-1", { symbol: "NVDA", side: "buy", quantity: "1" }), false);
  });
});

describe("decideBeforeRobinhoodPlaceCall", () => {
  const order = { symbol: "NVDA", side: "buy", quantity: "1" };

  test("blocks when the order was never reviewed", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of NVDA" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    const result = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1500);
    assert.equal(result?.block, true);
    assert.match(result!.blockReason, /never reviewed/);
  });

  test("blocks when reviewed but there is no pending authorization", () => {
    const pendingAuth: PendingAuthMap = new Map();
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const result = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1500);
    assert.equal(result?.block, true);
    assert.match(result!.blockReason, new RegExp(AUTHORIZE_TOOL));
  });

  test("blocks when reviewed and authorized, but the live text names a different order", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of AAPL" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const result = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1500);
    assert.equal(result?.block, true);
    assert.match(result!.blockReason, /NVDA/);
  });

  test("allows when reviewed and the live text matches exactly", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of NVDA" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const result = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1500);
    assert.equal(result, undefined);
  });

  test("consumes the authorization — a second placement right after is blocked again", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of NVDA" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const first = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1500);
    assert.equal(first, undefined, "first authorized+reviewed call should be allowed");
    const second = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-1", "place_equity_order", order, 120_000, 1600);
    assert.equal(second?.block, true, "a second placement must not ride the same authorization");
  });

  test("rejects a stale authorization past authMaxAgeMs even if reviewed", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of NVDA" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const authMaxAgeMs = 60_000;
    const result = decideBeforeRobinhoodPlaceCall(
      pendingAuth,
      reviewLedger,
      "sess-1",
      "place_equity_order",
      order,
      authMaxAgeMs,
      1000 + authMaxAgeMs + 1,
    );
    assert.equal(result?.block, true);
  });

  test("review and authorization are both isolated per session key", () => {
    const pendingAuth: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000, liveText: "buy 1 share of NVDA" }]]);
    const reviewLedger: ReviewLedgerMap = new Map();
    recordReview(reviewLedger, "sess-1", order);
    const result = decideBeforeRobinhoodPlaceCall(pendingAuth, reviewLedger, "sess-2", "place_equity_order", order, 120_000, 1500);
    assert.equal(result?.block, true, "session-2 must not see session-1's review or authorization");
  });
});
