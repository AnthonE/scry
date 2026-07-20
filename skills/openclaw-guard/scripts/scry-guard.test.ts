// Tests for scry-guard (OpenClaw plugin). Uses Node's built-in test runner
// (node:test) and native TS execution — zero extra dependencies, matching
// how the plugin itself loads (plugins.load.paths runs .ts files directly).
//
// Run with:
//   node --test /home/anthony/.openclaw/policies/scry-guard.test.ts
import assert from "node:assert/strict";
import { test, describe } from "node:test";

import {
  AUTHORIZE_TOOL,
  DEFAULT_AUTH_MAX_AGE_MS,
  sessionKeyOf,
  extractToolResultText,
  recordAuthorizationResult,
  decideBeforeToolCall,
  type PendingAuthMap,
} from "./scry-guard-logic.ts";

describe("sessionKeyOf", () => {
  test("prefers sessionKey, then sessionId, then runId, then default", () => {
    assert.equal(sessionKeyOf({ sessionKey: "a", sessionId: "b", runId: "c" }), "a");
    assert.equal(sessionKeyOf({ sessionId: "b", runId: "c" }), "b");
    assert.equal(sessionKeyOf({ runId: "c" }), "c");
    assert.equal(sessionKeyOf({}), "default");
  });
});

describe("extractToolResultText", () => {
  test("extracts joined text from MCP content-block shape", () => {
    const result = { content: [{ type: "text", text: '{"authorized":true}' }] };
    assert.equal(extractToolResultText(result), '{"authorized":true}');
  });

  test("passes through a plain string result", () => {
    assert.equal(extractToolResultText("hello"), "hello");
  });

  test("stringifies anything else rather than throwing", () => {
    assert.equal(extractToolResultText({ foo: "bar" }), '{"foo":"bar"}');
  });

  test("returns empty string for a value that can't stringify", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    assert.equal(extractToolResultText(circular), "");
  });
});

describe("recordAuthorizationResult", () => {
  test("ignores calls to tools other than the authorize tool", () => {
    const pending: PendingAuthMap = new Map();
    recordAuthorizationResult(pending, "sess-1", "some_other_tool", { authorized: true }, 1000);
    assert.equal(pending.size, 0);
  });

  test("records a pending authorization on a passing authorize_action result", () => {
    const pending: PendingAuthMap = new Map();
    const result = { content: [{ type: "text", text: '{"authorized":true,"reason":"ok"}' }] };
    recordAuthorizationResult(pending, "sess-1", AUTHORIZE_TOOL, result, 1000);
    assert.deepEqual(pending.get("sess-1"), { authorizedAt: 1000 });
  });

  test("clears any pending authorization on a failing authorize_action result", () => {
    const pending: PendingAuthMap = new Map();
    pending.set("sess-1", { authorizedAt: 500 });
    const result = { content: [{ type: "text", text: '{"authorized":false,"reason":"nope"}' }] };
    recordAuthorizationResult(pending, "sess-1", AUTHORIZE_TOOL, result, 1000);
    assert.equal(pending.has("sess-1"), false);
  });

  test("treats unparseable results as a failed authorization", () => {
    const pending: PendingAuthMap = new Map();
    recordAuthorizationResult(pending, "sess-1", AUTHORIZE_TOOL, "not json", 1000);
    assert.equal(pending.has("sess-1"), false);
  });
});

describe("decideBeforeToolCall", () => {
  test("always allows a tool not in gatedTools", () => {
    const pending: PendingAuthMap = new Map();
    const result = decideBeforeToolCall(pending, "sess-1", "read_file", new Set(), DEFAULT_AUTH_MAX_AGE_MS, 1000);
    assert.equal(result, undefined);
  });

  test("blocks a gated tool with no pending authorization", () => {
    const pending: PendingAuthMap = new Map();
    const result = decideBeforeToolCall(
      pending,
      "sess-1",
      "send_payment",
      new Set(["send_payment"]),
      DEFAULT_AUTH_MAX_AGE_MS,
      1000,
    );
    assert.equal(result?.block, true);
    assert.match(result!.blockReason, /authorize_action/);
  });

  test("allows a gated tool with a fresh pending authorization", () => {
    const pending: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000 }]]);
    const result = decideBeforeToolCall(
      pending,
      "sess-1",
      "send_payment",
      new Set(["send_payment"]),
      DEFAULT_AUTH_MAX_AGE_MS,
      1500,
    );
    assert.equal(result, undefined);
  });

  test("consumes the authorization — a second gated call right after is blocked again", () => {
    const pending: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000 }]]);
    const gated = new Set(["send_payment"]);
    const first = decideBeforeToolCall(pending, "sess-1", "send_payment", gated, DEFAULT_AUTH_MAX_AGE_MS, 1500);
    assert.equal(first, undefined, "first gated call should be allowed");
    const second = decideBeforeToolCall(pending, "sess-1", "send_payment", gated, DEFAULT_AUTH_MAX_AGE_MS, 1600);
    assert.equal(second?.block, true, "second gated call must not reuse the same authorization");
  });

  test("an authorization does not carry over to a DIFFERENT gated tool either", () => {
    // This is the exact gap that motivated single-use consumption: without
    // it, one authorize_action call could unlock any gated tool for the
    // whole TTL window, not just the action it was meant for.
    const pending: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000 }]]);
    const gated = new Set(["send_payment", "delete_account"]);
    const paymentCall = decideBeforeToolCall(pending, "sess-1", "send_payment", gated, DEFAULT_AUTH_MAX_AGE_MS, 1500);
    assert.equal(paymentCall, undefined, "the authorized call goes through");
    const deleteCall = decideBeforeToolCall(pending, "sess-1", "delete_account", gated, DEFAULT_AUTH_MAX_AGE_MS, 1600);
    assert.equal(deleteCall?.block, true, "a different gated tool must not ride the same authorization");
  });

  test("rejects a stale authorization past authMaxAgeMs even if unconsumed", () => {
    const pending: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000 }]]);
    const authMaxAgeMs = 60_000;
    const result = decideBeforeToolCall(
      pending,
      "sess-1",
      "send_payment",
      new Set(["send_payment"]),
      authMaxAgeMs,
      1000 + authMaxAgeMs + 1,
    );
    assert.equal(result?.block, true);
  });

  test("authorizations are isolated per session key", () => {
    const pending: PendingAuthMap = new Map([["sess-1", { authorizedAt: 1000 }]]);
    const result = decideBeforeToolCall(
      pending,
      "sess-2",
      "send_payment",
      new Set(["send_payment"]),
      DEFAULT_AUTH_MAX_AGE_MS,
      1500,
    );
    assert.equal(result?.block, true, "session-2 must not see session-1's authorization");
  });
});
