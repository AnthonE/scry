// scry-guard — Masa's authorize-gate, wired against scry's MCP sidecar.
//
// Watches for a passing `scry-sidecar__authorize_action` call (registered via
// `openclaw mcp add scry-sidecar ...`, see mcp_sidecar.py in the scry repo:
// https://github.com/AnthonE/scry) and requires one, single-use, before any
// tool in gatedTools is allowed to run. Nothing recalled from memory can
// satisfy this — authorize_action only returns true for a live, trusted
// instruction (hermes_retrofit.authorize's contract, same rule scry uses for
// Mune).
//
// A tool named in robinhoodPlaceTools (e.g. a connected
// agent.robinhood.com/mcp/trading server's place_equity_order) gets the
// STRICTER robinhood-guard-logic.ts gate instead of the plain gatedTools
// check: it also needs a matching prior call to a robinhoodReviewTools tool
// in the same session, and the live instruction spent on authorize_action
// must actually NAME this order's symbol/side, not just exist. Ported from
// scry's robinhood_agentic.py (ReviewLedger + authorize_trade) — see that
// module and robinhood-guard-logic.ts's header for the full rationale.
//
// The actual decision logic lives in scry-guard-logic.ts + robinhood-guard-
// logic.ts (pure functions, no OpenClaw SDK import) so it can be unit tested
// directly — see scry-guard.test.ts / robinhood-guard-logic.test.ts. This
// file is just the host wiring: real Date.now(), real session state, and
// plugin config read from plugins.entries.scry-guard.config in
// openclaw.json (validated against configSchema in openclaw.plugin.json).
// Empty gatedTools/robinhoodPlaceTools/robinhoodReviewTools by default:
// nothing consequential is wired into Masa's toolset yet.
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import {
  DEFAULT_AUTH_MAX_AGE_MS,
  type PendingAuthMap,
  type PluginConfig,
  sessionKeyOf,
  recordAuthorizationResult,
  decideBeforeToolCall,
} from "./scry-guard-logic.ts";
import {
  type ReviewLedgerMap,
  recordReviewResult,
  decideBeforeRobinhoodPlaceCall,
} from "./robinhood-guard-logic.ts";

type RobinhoodPluginConfig = PluginConfig & {
  robinhoodPlaceTools?: string[];
  robinhoodReviewTools?: string[];
};

const pendingAuth: PendingAuthMap = new Map();
const reviewLedger: ReviewLedgerMap = new Map();

export default definePluginEntry({
  id: "scry-guard",
  name: "scry guard",
  description:
    "Requires a passing, single-use scry-sidecar__authorize_action call before any gated tool call goes through; Robinhood order-placing tools additionally require a matching prior review and an instruction naming the exact order.",
  register(api) {
    const config = (api.pluginConfig ?? {}) as RobinhoodPluginConfig;
    const gatedTools = new Set<string>(config.gatedTools ?? []);
    const robinhoodPlaceTools = new Set<string>(config.robinhoodPlaceTools ?? []);
    const robinhoodReviewTools = new Set<string>(config.robinhoodReviewTools ?? []);
    const authMaxAgeMs =
      typeof config.authMaxAgeSeconds === "number" && config.authMaxAgeSeconds > 0
        ? config.authMaxAgeSeconds * 1000
        : DEFAULT_AUTH_MAX_AGE_MS;

    api.on("after_tool_call", (event, ctx) => {
      const key = sessionKeyOf(ctx);
      recordAuthorizationResult(pendingAuth, key, event.toolName, event.params, event.result, Date.now());
      recordReviewResult(reviewLedger, key, event.toolName, event.params, event.error, robinhoodReviewTools);
    });

    api.on("before_tool_call", (event, ctx) => {
      const key = sessionKeyOf(ctx);
      if (robinhoodPlaceTools.has(event.toolName)) {
        return decideBeforeRobinhoodPlaceCall(
          pendingAuth,
          reviewLedger,
          key,
          event.toolName,
          event.params,
          authMaxAgeMs,
          Date.now(),
        );
      }
      return decideBeforeToolCall(pendingAuth, key, event.toolName, gatedTools, authMaxAgeMs, Date.now());
    });
  },
});
