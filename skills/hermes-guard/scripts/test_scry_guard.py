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
        self.assertEqual(mod.GATED_TOOLS, {})

    def test_custom_trusted_sources(self):
        mod = _load_plugin({"trusted_sources": ["user", "tool:ledger"]})
        self.assertEqual(mod.TRUSTED, {"user", "tool:ledger"})

    def test_gated_tools_keyword_becomes_intent_fn(self):
        mod = _load_plugin({"gated_tools": {"send_payment": "transfer"}})
        self.assertIn("send_payment", mod.GATED_TOOLS)
        intent = mod.GATED_TOOLS["send_payment"]
        self.assertTrue(intent("please transfer 5 dollars"))
        self.assertFalse(intent("hello there"))

    def test_gated_tools_null_keyword_is_none(self):
        mod = _load_plugin({"gated_tools": {"wipe_disk": None}})
        self.assertIsNone(mod.GATED_TOOLS["wipe_disk"])

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
        self.assertEqual(mod.GATED_TOOLS, {})


class AuthorizeGateTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_plugin({"gated_tools": {"send_payment": "transfer"}})
        self.sid = "agent:main:discord:dm:999"

    def test_blocks_when_no_live_message_cached(self):
        result = self.mod._on_pre_tool_call(tool_name="send_payment", args={}, session_id=self.sid)
        self.assertEqual(result["action"], "block")

    def test_blocks_when_live_message_does_not_match_intent(self):
        self.mod._on_pre_llm_call(session_id=self.sid, user_message="hey how are you")
        result = self.mod._on_pre_tool_call(tool_name="send_payment", args={}, session_id=self.sid)
        self.assertEqual(result["action"], "block")

    def test_allows_when_live_message_matches_intent(self):
        self.mod._on_pre_llm_call(session_id=self.sid, user_message="please transfer it now")
        result = self.mod._on_pre_tool_call(tool_name="send_payment", args={}, session_id=self.sid)
        self.assertIsNone(result)

    def test_ungated_tool_always_passes(self):
        result = self.mod._on_pre_tool_call(tool_name="read_file", args={}, session_id=self.sid)
        self.assertIsNone(result)

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
