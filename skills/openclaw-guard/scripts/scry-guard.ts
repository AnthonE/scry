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
// The actual decision logic lives in scry-guard-logic.ts (pure functions, no
// OpenClaw SDK import) so it can be unit tested directly — see
// scry-guard.test.ts. This file is just the host wiring: real Date.now(),
// real session state, and plugin config read from
// plugins.entries.scry-guard.config in openclaw.json (validated against
// configSchema in openclaw.plugin.json). Empty gatedTools by default:
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

const pendingAuth: PendingAuthMap = new Map();

export default definePluginEntry({
  id: "scry-guard",
  name: "scry guard",
  description:
    "Requires a passing, single-use scry-sidecar__authorize_action call before any gated tool call goes through.",
  register(api) {
    const config = (api.pluginConfig ?? {}) as PluginConfig;
    const gatedTools = new Set<string>(config.gatedTools ?? []);
    const authMaxAgeMs =
      typeof config.authMaxAgeSeconds === "number" && config.authMaxAgeSeconds > 0
        ? config.authMaxAgeSeconds * 1000
        : DEFAULT_AUTH_MAX_AGE_MS;

    api.on("after_tool_call", (event, ctx) => {
      recordAuthorizationResult(pendingAuth, sessionKeyOf(ctx), event.toolName, event.result, Date.now());
    });

    api.on("before_tool_call", (event, ctx) => {
      return decideBeforeToolCall(
        pendingAuth,
        sessionKeyOf(ctx),
        event.toolName,
        gatedTools,
        authMaxAgeMs,
        Date.now(),
      );
    });
  },
});
