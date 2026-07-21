"""Tests for scry-guard (Hermes plugin). Stdlib-only, matching scry's own
dependency-free test style (test_harnesses.py) rather than requiring pytest.

Run with the Hermes install's own Python (needs hermes-agent's `tools`
package on the path — set HERMES_AGENT_SRC if it's not auto-detected):

    python3 test_scry_guard.py -v

Each test loads a fresh copy of the plugin module (module-level state —
TRUSTED, GATED_TOOLS, and the config it's built from — is only read once at
import time) so tests don't leak config or in-memory session state into each
other.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import types
import unittest

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
# The vendored scry .py files live right next to this test file — no
# separate scry clone required. SCRY_SRC can still override (e.g. to test
# against a live scry checkout instead of the vendored copies).
_SCRY_SRC = os.environ.get("SCRY_SRC", _PLUGIN_DIR)


def _find_hermes_agent_src() -> str:
    env = os.environ.get("HERMES_AGENT_SRC")
    if env:
        return env
    hermes_bin = shutil.which("hermes")
    if hermes_bin:
        # Installed layout: <install>/venv/bin/hermes -> <install> two dirs up.
        candidate = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(hermes_bin))))
        if os.path.isdir(os.path.join(candidate, "tools")):
            return candidate
    default = os.path.expanduser("~/.hermes/hermes-agent")
    if os.path.isdir(os.path.join(default, "tools")):
        return default
    raise RuntimeError(
        "Could not locate hermes-agent's source tree (needed for tools.registry). "
        "Set HERMES_AGENT_SRC to your hermes-agent install directory."
    )


_HERMES_AGENT_SRC = _find_hermes_agent_src()


def _load_plugin(fake_plugin_config: dict | None = None):
    """Import a fresh scry_guard module instance with the given plugin config."""
    for path in (_HERMES_AGENT_SRC, _SCRY_SRC):
        if path not in sys.path:
            sys.path.insert(0, path)

    fake_config_module = types.ModuleType("hermes_cli.config")

    def load_config():
        return {
            "plugins": {
                "entries": {
                    "scry-guard": {"config": fake_plugin_config or {}},
                }
            }
        }

    fake_config_module.load_config = load_config
    sys.modules["hermes_cli.config"] = fake_config_module

    # Force a fresh module object each time so module-level TRUSTED/GATED_TOOLS
    # get rebuilt from the fake config above, not cached from a prior test.
    sys.modules.pop("scry_guard_under_test", None)
    spec = importlib.util.spec_from_file_location(
        "scry_guard_under_test", os.path.join(_PLUGIN_DIR, "__init__.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScryImportableTests(unittest.TestCase):
    def test_scry_imports_cleanly(self):
        mod = _load_plugin()
        self.assertIsNotNone(mod.Turn, "turn_record.Turn should import from SCRY_SRC")
        self.assertIsNotNone(mod.authorize, "hermes_retrofit.authorize should import from SCRY_SRC")
        self.assertIsNotNone(mod.monitor, "monitor_agent.monitor should import from SCRY_SRC")


class ConfigLoadingTests(unittest.TestCase):
    def test_defaults_when_no_config(self):
        mod = _load_plugin()
        self.assertEqual(mod.TRUSTED, {"user"})
        self.assertEqual(mod.GATED_TOOLS, set())
        self.assertEqual(mod.AUTH_MAX_AGE_SECONDS, mod.DEFAULT_AUTH_MAX_AGE_SECONDS)

    def test_custom_trusted_sources(self):
        mod = _load_plugin({"trusted_sources": ["user", "tool:ledger"]})
        self.assertEqual(mod.TRUSTED, {"user", "tool:ledger"})

    def test_gated_tools_from_list(self):
        mod = _load_plugin({"gated_tools": ["terminal", "write_file"]})
        self.assertEqual(mod.GATED_TOOLS, {"terminal", "write_file"})

    def test_robinhood_tools_default_empty(self):
        mod = _load_plugin()
        self.assertEqual(mod.ROBINHOOD_PLACE_TOOLS, set())
        self.assertEqual(mod.ROBINHOOD_REVIEW_TOOLS, set())

    def test_robinhood_tools_from_list(self):
        mod = _load_plugin({
            "robinhood_place_tools": ["place_equity_order"],
            "robinhood_review_tools": ["review_equity_order"],
        })
        self.assertEqual(mod.ROBINHOOD_PLACE_TOOLS, {"place_equity_order"})
        self.assertEqual(mod.ROBINHOOD_REVIEW_TOOLS, {"review_equity_order"})

    def test_custom_auth_max_age(self):
        mod = _load_plugin({"auth_max_age_seconds": 30})
        self.assertEqual(mod.AUTH_MAX_AGE_SECONDS, 30.0)

    def test_config_load_failure_fails_closed_to_defaults(self):
        # Simulate a broken config loader — plugin must not crash on import.
        for path in (_HERMES_AGENT_SRC, _SCRY_SRC):
            if path not in sys.path:
                sys.path.insert(0, path)
        fake_config_module = types.ModuleType("hermes_cli.config")

        def load_config():
            raise RuntimeError("boom")

        fake_config_module.load_config = load_config
        sys.modules["hermes_cli.config"] = fake_config_module
        sys.modules.pop("scry_guard_under_test", None)
        spec = importlib.util.spec_from_file_location(
            "scry_guard_under_test", os.path.join(_PLUGIN_DIR, "__init__.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # must not raise
        self.assertEqual(mod.TRUSTED, {"user"})
        self.assertEqual(mod.GATED_TOOLS, set())


class AuthorizeGateTests(unittest.TestCase):
    """Covers the single-use authorize_action -> pre_tool_call mechanism —
    same shape as openclaw-guard's decideBeforeToolCall/recordAuthorizationResult,
    deliberately kept in sync (see ../openclaw-guard/scripts/scry-guard-logic.ts)."""

    def setUp(self):
        self.mod = _load_plugin({"gated_tools": ["terminal"]})
        self.sid = "agent:main:discord:dm:999"

    def test_blocks_with_no_pending_authorization(self):
        result = self.mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertEqual(result["action"], "block")

    def test_ungated_tool_always_passes(self):
        result = self.mod._on_pre_tool_call(tool_name="read_file", args={}, session_id=self.sid)
        self.assertIsNone(result)

    def test_authorize_action_fails_with_no_live_message(self):
        result = json.loads(self.mod._handle_authorize_action({}, session_id=self.sid))
        self.assertFalse(result["authorized"])

    def test_authorize_action_succeeds_with_a_live_trusted_message(self):
        self.mod._on_pre_llm_call(session_id=self.sid, user_message="please do the thing")
        result = json.loads(self.mod._handle_authorize_action({}, session_id=self.sid))
        self.assertTrue(result["authorized"])

    def test_gated_call_allowed_after_authorize_action(self):
        self.mod._on_pre_llm_call(session_id=self.sid, user_message="please run it")
        self.mod._handle_authorize_action({}, session_id=self.sid)
        result = self.mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertIsNone(result)

    def test_authorization_is_single_use(self):
        self.mod._on_pre_llm_call(session_id=self.sid, user_message="please run it")
        self.mod._handle_authorize_action({}, session_id=self.sid)
        first = self.mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertIsNone(first, "first gated call should be allowed")
        second = self.mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertEqual(second["action"], "block", "second gated call must not reuse the same authorization")

    def test_authorization_does_not_carry_to_a_different_gated_tool(self):
        mod = _load_plugin({"gated_tools": ["terminal", "write_file"]})
        mod._on_pre_llm_call(session_id=self.sid, user_message="please run it")
        mod._handle_authorize_action({}, session_id=self.sid)
        terminal_call = mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertIsNone(terminal_call, "the authorized call goes through")
        write_call = mod._on_pre_tool_call(tool_name="write_file", args={}, session_id=self.sid)
        self.assertEqual(write_call["action"], "block", "a different gated tool must not ride the same authorization")

    def test_stale_authorization_expires(self):
        mod = _load_plugin({"gated_tools": ["terminal"], "auth_max_age_seconds": 0})
        mod._on_pre_llm_call(session_id=self.sid, user_message="please run it")
        mod._handle_authorize_action({}, session_id=self.sid)
        time.sleep(0.05)
        result = mod._on_pre_tool_call(tool_name="terminal", args={}, session_id=self.sid)
        self.assertEqual(result["action"], "block")

    def test_authorizations_are_isolated_per_session(self):
        self.mod._on_pre_llm_call(session_id="sess-1", user_message="please run it")
        self.mod._handle_authorize_action({}, session_id="sess-1")
        result = self.mod._on_pre_tool_call(tool_name="terminal", args={}, session_id="sess-2")
        self.assertEqual(result["action"], "block", "session-2 must not see session-1's authorization")

    def test_untrusted_source_cannot_authorize(self):
        # authorize() itself only trusts sources in TRUSTED ("user" by
        # default); live message text alone isn't enough if the plugin ever
        # gets called with a different source (defense in depth — this test
        # exercises hermes_retrofit.authorize directly, not just the hook).
        ok, reason = self.mod.authorize(
            live={"text": "please transfer it now", "source": "some-other-bot", "role": "live_instruction"},
            trusted=self.mod.TRUSTED,
        )
        self.assertFalse(ok)
        self.assertIn("trusted", reason)


class RobinhoodTradeGateTests(unittest.TestCase):
    """Covers the STRICTER gate on robinhood_place_tools: reviewed first, then
    a live trusted instruction that actually names this order's symbol/side —
    not just "some live instruction existed this turn" (that weaker check is
    AuthorizeGateTests above). Ported from robinhood_agentic.py's own
    ReviewLedger + authorize_trade onto Hermes's real hook system."""

    def setUp(self):
        self.mod = _load_plugin({
            "robinhood_place_tools": ["place_equity_order"],
            "robinhood_review_tools": ["review_equity_order"],
        })
        self.sid = "agent:main:discord:dm:777"
        self.order = {"symbol": "NVDA", "side": "buy", "quantity": "1"}

    def _review(self, mod=None, sid=None, order=None):
        mod = mod or self.mod
        (mod._on_post_tool_call)(
            tool_name="review_equity_order", args=order or self.order, session_id=sid or self.sid
        )

    def _authorize(self, text, mod=None, sid=None):
        mod = mod or self.mod
        sid = sid or self.sid
        mod._on_pre_llm_call(session_id=sid, user_message=text)
        return json.loads(mod._handle_authorize_action({}, session_id=sid))

    def test_place_blocked_without_review(self):
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("reviewed", result["message"])

    def test_place_blocked_after_review_with_no_authorization(self):
        self._review()
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("authorize_action", result["message"])

    def test_place_blocked_when_live_instruction_names_a_different_symbol(self):
        self._review()
        self._authorize("go ahead and buy some AAPL")
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("NVDA", result["message"])

    def test_place_authorized_end_to_end(self):
        self._review()
        auth = self._authorize("buy 1 share of NVDA")
        self.assertTrue(auth["authorized"])
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertIsNone(result)

    def test_authorization_for_a_trade_is_single_use(self):
        self._review()
        self._authorize("buy 1 share of NVDA")
        first = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertIsNone(first, "first authorized+reviewed call should be allowed")
        second = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(second["action"], "block", "a second placement must not ride the same authorization")
        self.assertIn("authorize_action", second["message"])

    def test_failed_review_call_is_not_recorded(self):
        self.mod._on_post_tool_call(
            tool_name="review_equity_order", args=self.order, session_id=self.sid, error_message="rejected by broker"
        )
        self._authorize("buy 1 share of NVDA")
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("reviewed", result["message"])

    def test_review_of_an_unconfigured_tool_name_is_ignored(self):
        self.mod._on_post_tool_call(tool_name="some_other_review_tool", args=self.order, session_id=self.sid)
        self._authorize("buy 1 share of NVDA")
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("reviewed", result["message"])

    def test_review_ledger_is_isolated_per_session(self):
        self._review(sid="sess-a")
        self._authorize("buy 1 share of NVDA", sid="sess-b")
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id="sess-b")
        self.assertEqual(result["action"], "block")
        self.assertIn("reviewed", result["message"])

    def test_fails_closed_if_robinhood_agentic_did_not_import(self):
        self.mod.ReviewLedger = None
        self.mod.authorize_trade = None
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("not importable", result["message"])

    def test_a_reviewed_and_matching_dollar_amount_order_is_authorized(self):
        order = {"symbol": "NVDA", "side": "buy", "dollar_amount": "50"}
        self._review(order=order)
        self._authorize("buy 50 dollars of NVDA")
        result = self.mod._on_pre_tool_call(tool_name="place_equity_order", args=order, session_id=self.sid)
        self.assertIsNone(result)

    def test_robinhood_place_tools_do_not_fall_through_to_generic_gated_tools_path(self):
        # A place-order tool is governed ONLY by the stricter Robinhood path,
        # even if it's also (redundantly/mistakenly) listed in gated_tools.
        mod = _load_plugin({
            "gated_tools": ["place_equity_order"],
            "robinhood_place_tools": ["place_equity_order"],
            "robinhood_review_tools": ["review_equity_order"],
        })
        mod._on_pre_llm_call(session_id=self.sid, user_message="buy 1 share of NVDA")
        mod._handle_authorize_action({}, session_id=self.sid)
        # Generic authorize_action alone (no review) must NOT be enough to pass.
        result = mod._on_pre_tool_call(tool_name="place_equity_order", args=self.order, session_id=self.sid)
        self.assertEqual(result["action"], "block")
        self.assertIn("reviewed", result["message"])


class TurnCaptureTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_plugin()
        self.tmpdir = tempfile.mkdtemp()
        self.mod.TURNS_PATH = os.path.join(self.tmpdir, "turns.jsonl")
        self.sid = "agent:main:discord:group:12345"

    def test_single_turn_round_trips(self):
        class FakeMsg:
            reasoning = "because the user asked plainly"

        self.mod._on_pre_llm_call(session_id=self.sid, user_message="hi")
        self.mod._on_post_api_request(turn_id="t1", session_id=self.sid, assistant_message=FakeMsg())
        self.mod._on_post_llm_call(
            session_id=self.sid, turn_id="t1", assistant_response="hello!", platform="discord", model="claude-opus-4-8"
        )

        with open(self.mod.TURNS_PATH, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["id"], "t1")
        self.assertEqual(lines[0]["M"], "because the user asked plainly")
        self.assertEqual(lines[0]["D"], "hello!")
        self.assertTrue(lines[0]["context"]["monitored"])  # not a ":dm:" session

    def test_reasoning_accumulates_across_multiple_api_calls(self):
        class FakeMsg:
            def __init__(self, text):
                self.reasoning = text

        self.mod._on_post_api_request(turn_id="t2", session_id=self.sid, assistant_message=FakeMsg("step one"))
        self.mod._on_post_api_request(turn_id="t2", session_id=self.sid, assistant_message=FakeMsg("step two"))
        self.mod._on_post_llm_call(
            session_id=self.sid, turn_id="t2", assistant_response="done", platform="discord", model="x"
        )
        with open(self.mod.TURNS_PATH, encoding="utf-8") as f:
            row = json.loads(f.readline())
        self.assertIn("step one", row["M"])
        self.assertIn("step two", row["M"])

    def test_no_reasoning_yields_empty_m_not_a_crash(self):
        self.mod._on_post_llm_call(
            session_id=self.sid, turn_id="t3", assistant_response="quick reply", platform="cli", model="gpt-5.6"
        )
        with open(self.mod.TURNS_PATH, encoding="utf-8") as f:
            row = json.loads(f.readline())
        self.assertEqual(row["M"], "")
        self.assertEqual(row["D"], "quick reply")

    def test_dm_session_marked_unmonitored(self):
        dm_sid = "agent:main:discord:dm:1"
        self.mod._on_post_llm_call(
            session_id=dm_sid, turn_id="t4", assistant_response="hi", platform="discord", model="x"
        )
        with open(self.mod.TURNS_PATH, encoding="utf-8") as f:
            row = json.loads(f.readline())
        self.assertFalse(row["context"]["monitored"])


class ScryProfileToolTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_plugin()
        self.tmpdir = tempfile.mkdtemp()
        self.mod.TURNS_PATH = os.path.join(self.tmpdir, "turns.jsonl")

    def test_reports_insufficient_data_with_no_turns_file(self):
        result = json.loads(self.mod._handle_scry_profile({}))
        self.assertEqual(result["read"], "INSUFFICIENT DATA")
        self.assertEqual(result["n"], 0)

    def test_reports_a_real_profile_with_enough_turns(self):
        class FakeMsg:
            reasoning = "consistent reasoning regardless of context"

        for i in range(25):
            sid = f"agent:main:discord:group:{i % 2}"
            self.mod._on_pre_llm_call(session_id=sid, user_message=f"msg {i}")
            self.mod._on_post_api_request(turn_id=f"t{i}", session_id=sid, assistant_message=FakeMsg())
            self.mod._on_post_llm_call(
                session_id=sid, turn_id=f"t{i}", assistant_response=f"reply {i}", platform="discord", model="x"
            )
        result = json.loads(self.mod._handle_scry_profile({}))
        self.assertEqual(result["n"], 25)
        self.assertFalse(result["read"].startswith("INSUFFICIENT DATA"))

    def test_reports_error_string_not_crash_on_corrupt_file(self):
        with open(self.mod.TURNS_PATH, "w", encoding="utf-8") as f:
            f.write("not json at all\n")
        result = json.loads(self.mod._handle_scry_profile({}))
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
