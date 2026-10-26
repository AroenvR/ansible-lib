"""Tests of qa-budget's guard and status line: python3 test_qa_budget.py <folder of guard.py>. Each test runs the hook as Claude
Code does, with a fresh configuration directory holding the readings and ledger it sets up."""
import copy
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

FOLDER = sys.argv.pop(1)
GUARD = os.path.join(FOLDER, "guard.py")
NOW = datetime.datetime.now(datetime.timezone.utc)


def at(hours):
    return (NOW + datetime.timedelta(hours=hours)).isoformat(timespec="seconds")


class Guard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.dir.name, "qa-budget")
        os.makedirs(self.state)
        self.week_reset = (NOW + datetime.timedelta(days=3)).timestamp()
        self.reading(week=10, five=10)

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, lines):
        with open(os.path.join(self.state, name), "w") as f:
            f.write("".join(json.dumps(line) + "\n" for line in lines))

    def reading(self, week, five, week_reset=None, five_reset=None):
        limits = {"seven_day": {"used_percentage": week, "resets_at": week_reset or self.week_reset},
                  "five_hour": {"used_percentage": five, "resets_at": five_reset or NOW.timestamp() + 3600}}
        with open(os.path.join(self.state, "rate-limits.json"), "w") as f:
            json.dump({"time": at(0), "rate_limits": limits}, f)

    def run_hook(self, event, **env):
        event = dict({"session_id": "s1", "transcript_path": os.path.join(self.dir.name, "s1.jsonl")}, **event)
        environment = dict(os.environ, CLAUDE_CONFIG_DIR=self.dir.name, **env)
        done = subprocess.run([sys.executable, GUARD], input=json.dumps(event), capture_output=True, text=True,
                              env=environment, check=True)
        self.assertEqual(done.stderr, "")
        return json.loads(done.stdout) if done.stdout.strip() else None

    def prompt(self, text, **env):
        return self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": text}, **env)

    def agent(self, **env):
        answer = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {}}, **env)
        return answer and answer["hookSpecificOutput"]["permissionDecision"]

    def test_under_the_ceilings_everything_runs(self):
        self.assertIsNone(self.prompt("[auto qa-budget step 3] go on"))
        self.assertIsNone(self.agent())

    def test_a_wakeup_at_the_weekly_ceiling_is_blocked_and_an_expert_run_denied(self):
        self.reading(week=60, five=10)
        self.assertEqual(self.prompt("[auto resume] Read STATE.md")["decision"], "block")
        self.assertEqual(self.agent(), "deny")

    def test_the_person_is_asked_at_a_ceiling_instead(self):
        self.reading(week=10, five=90)
        self.assertIsNone(self.prompt("please review the PR"))
        self.assertEqual(self.agent(), "ask")

    def test_a_reading_from_before_a_reset_counts_as_zero(self):
        self.reading(week=100, five=100, week_reset=NOW.timestamp() - 60, five_reset=NOW.timestamp() - 60)
        self.assertIsNone(self.prompt("[auto qa-budget step 2] go"))
        self.assertIsNone(self.agent())

    def test_spend_down_raises_the_weekly_ceiling_while_the_person_is_inactive(self):
        with open(os.path.join(self.state, "activity.json"), "w") as f:
            json.dump({"person_prompt_at": at(-4)}, f)
        self.reading(week=80, five=10, week_reset=NOW.timestamp() + 2 * 3600)
        self.assertIsNone(self.prompt("[auto resume] go on"))
        self.assertIsNone(self.agent())

    def test_no_spend_down_while_the_person_was_active_recently(self):
        self.prompt("I am here")
        self.reading(week=80, five=10, week_reset=NOW.timestamp() + 2 * 3600)
        self.assertEqual(self.prompt("[auto resume] go on")["decision"], "block")

    def test_usage_rising_while_idle_means_someone_is_active(self):
        reset = NOW.timestamp() + 2 * 3600
        self.write("rate-limits.jsonl", [
            {"time": at(-2), "rate_limits": {"seven_day": {"used_percentage": 70, "resets_at": reset}}},
            {"time": at(-1), "rate_limits": {"seven_day": {"used_percentage": 75, "resets_at": reset}}}])
        self.reading(week=75, five=10, week_reset=reset)
        self.assertEqual(self.prompt("[auto resume] go on")["decision"], "block")

    def test_an_automatic_turn_at_the_limit_pauses_every_tool(self):
        self.prompt("[auto resume] go on")
        self.reading(week=98, five=10)
        answer = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}})
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("extra usage", answer["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_person_s_turn_at_the_limit_keeps_its_tools(self):
        self.prompt("go on, I pay the extra usage")
        self.reading(week=98, five=10)
        self.assertIsNone(self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}}))

    def test_the_run_cap_counts_the_session_s_runs(self):
        self.prompt("[auto resume] go on")
        self.write("ledger.jsonl", [{"event": "SubagentStart", "session_id": "s1"}] * 2
                   + [{"event": "SubagentStart", "session_id": "other"}] * 5)
        self.assertIsNone(self.agent(QA_BUDGET_RUNS="3"))
        self.assertEqual(self.agent(QA_BUDGET_RUNS="2"), "deny")

    def test_an_expert_over_its_token_budget_must_report(self):
        os.makedirs(os.path.join(self.dir.name, "s1", "subagents"))
        with open(os.path.join(self.dir.name, "s1", "subagents", "agent-a1.jsonl"), "w") as f:
            usage = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                     "output_tokens": 300}
            f.write(json.dumps({"type": "assistant", "message": {"id": "m1", "usage": usage}}) + "\n")
        event = {"hook_event_name": "PreToolUse", "tool_name": "Read", "agent_id": "a1", "agent_type": "tester"}
        self.assertIsNone(self.run_hook(event, QA_BUDGET_RUN_TOKENS="1501"))
        answer = self.run_hook(event, QA_BUDGET_RUN_TOKENS="1500")
        self.assertIn("write your report now", answer["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_person_s_prompt_that_starts_with_a_bracket_is_theirs(self):
        self.reading(week=70, five=10)
        self.assertIsNone(self.prompt("[Image #1] what is this?"))
        self.assertEqual(self.agent(), "ask")

    def test_a_session_the_guard_has_not_seen_counts_as_automatic(self):
        self.reading(week=99, five=10)
        answer = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}})
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_failed_save_still_blocks(self):
        self.reading(week=70, five=10)
        os.chmod(self.state, 0o500)
        try:
            event = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "[auto resume] go on"}
            done = subprocess.run([sys.executable, GUARD], input=json.dumps(event), capture_output=True, text=True,
                                  env=dict(os.environ, CLAUDE_CONFIG_DIR=self.dir.name), check=True)
            self.assertEqual(json.loads(done.stdout)["decision"], "block")
        finally:
            os.chmod(self.state, 0o700)

    def test_without_a_fresh_reading_an_automatic_turn_starts_no_expert(self):
        os.remove(os.path.join(self.state, "rate-limits.json"))
        self.assertIsNone(self.prompt("[auto resume] go on"))
        self.assertEqual(self.agent(), "deny")
        with open(os.path.join(self.state, "rate-limits.json"), "w") as f:
            json.dump({"time": at(-1), "rate_limits": {"seven_day": {"used_percentage": 1}}}, f)
        self.assertEqual(self.agent(), "deny")
        self.prompt("me again")
        self.assertIsNone(self.agent())

    def test_a_workflow_counts_as_an_expert_run(self):
        self.prompt("[auto resume] go on")
        self.reading(week=60, five=10)
        answer = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Workflow", "tool_input": {}})
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_broken_input_breaks_nothing(self):
        done = subprocess.run([sys.executable, GUARD], input="not json", capture_output=True, text=True,
                              env=dict(os.environ, CLAUDE_CONFIG_DIR=self.dir.name))
        self.assertEqual((done.returncode, done.stdout), (0, ""))


class PromptBlock(unittest.TestCase):
    """loop-to-delivery asks guard.prompt_block(moment) instead of reading the limits itself (IF-101): it must say what
    a blocked automatic prompt says, and nothing where the guard lets the prompt through."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.dir.name, "qa-budget")
        os.makedirs(self.state)
        environment = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.dir.name})
        environment.start()
        self.addCleanup(environment.stop)
        for name in [name for name in os.environ if name.startswith("QA_BUDGET_")]:
            del os.environ[name]
        spec = importlib.util.spec_from_file_location("guard_under_test", GUARD)
        self.guard = importlib.util.module_from_spec(spec)
        saved = list(sys.path)   # guard.py puts its own folder first on sys.path to import ledger
        try:
            spec.loader.exec_module(self.guard)
        finally:
            sys.path[:] = saved
        self.assertTrue(callable(getattr(self.guard, "prompt_block", None)), "the guard has no prompt_block (IF-101)")

    def tearDown(self):
        self.dir.cleanup()

    def put(self, name, content):
        with open(os.path.join(self.state, name), "w") as f:
            json.dump(content, f)

    def listing(self):
        return {name: os.stat(os.path.join(self.state, name)).st_mtime_ns for name in os.listdir(self.state)}

    def reading(self, week, five, when=0, week_reset_hours=72):
        self.put("rate-limits.json", {"time": at(when), "rate_limits": {
            "seven_day": {"used_percentage": week, "resets_at": (NOW + datetime.timedelta(hours=week_reset_hours)).timestamp()},
            "five_hour": {"used_percentage": five, "resets_at": NOW.timestamp() + 3600}}})

    def agree(self, activity=None):
        """prompt_block (activity from activity.json, and given) against on_prompt for an automatic prompt, same
        reading, same moment; returns the text, or None where the prompt passes."""
        saved = activity if activity is not None else {}
        if activity is not None:
            self.put("activity.json", activity)
        before = self.listing()
        by_file = self.guard.prompt_block(NOW)
        given = self.guard.prompt_block(NOW, copy.deepcopy(saved))
        self.assertEqual(self.listing(), before, "prompt_block wrote a file")
        self.assertEqual(by_file, given)
        answer = self.guard.on_prompt({"session_id": "s1", "prompt": "[auto resume] go on"}, copy.deepcopy(saved), NOW)
        if answer is None:
            self.assertIsNone(given)
            return None
        self.assertEqual(answer["decision"], "block")
        self.assertIsInstance(given, str)
        self.assertEqual(answer["reason"], "qa-budget: automatic prompt not run, %s. It runs again after the reset, or "
                         "when a person starts the turn." % given)
        return given

    def test_prompt_block_agrees_with_the_blocked_automatic_prompt(self):
        with self.subTest("the ceilings and the limit"):
            self.reading(week=10, five=10)
            self.assertIsNone(self.agree())
            self.reading(week=61, five=10)
            text = self.agree()
            self.assertTrue(text.startswith("the weekly ceiling (61% of the week used, ceiling 60%) is reached; "
                                            "weekly window resets "), text)
            self.assertIn("5-hour window resets ", text)
            self.reading(week=10, five=91)
            self.assertTrue(self.agree().startswith("the 5-hour ceiling (91% used, ceiling 90%) is reached; "))
            self.reading(week=98, five=10)
            self.assertTrue(self.agree().startswith("the subscription's limit (98%) is reached; "))
        with self.subTest("the spend-down and the person's activity"):
            self.reading(week=80, five=10, week_reset_hours=2)
            self.assertIsNone(self.agree({"person_prompt_at": at(-4)}), "inactive person: the ceiling rises to the limit")
            self.assertIn("the weekly ceiling (80% of the week used, ceiling 60%)", self.agree({"person_prompt_at": at(-1)}))
            os.remove(os.path.join(self.state, "activity.json"))
        with self.subTest("a reading as the guard judges it"):
            # A window whose reset has passed counts as 0; a stale reading over a ceiling still blocks (the guard
            # ignores its staleness for a prompt), so the loop must end where the guard blocks.
            self.put("rate-limits.json", {"time": at(0), "rate_limits": {
                "seven_day": {"used_percentage": 100, "resets_at": NOW.timestamp() - 60},
                "five_hour": {"used_percentage": 100, "resets_at": NOW.timestamp() - 60}}})
            self.assertIsNone(self.agree())
            self.reading(week=70, five=10, when=-1)
            self.assertIn("the weekly ceiling (70% of the week used, ceiling 60%) is reached", self.agree())
            os.remove(os.path.join(self.state, "rate-limits.json"))
            self.assertIsNone(self.agree(), "no reading: the prompt passes")
        with self.subTest("an activity file that is not an object counts as empty"):
            self.reading(week=61, five=10)
            self.put("activity.json", ["not", "an", "object"])
            self.assertEqual(self.guard.prompt_block(NOW), self.guard.prompt_block(NOW, {}))
            self.assertIsNotNone(self.guard.prompt_block(NOW))
            os.remove(os.path.join(self.state, "activity.json"))
        with self.subTest("the environment's limits apply"):
            self.reading(week=61, five=10)
            with mock.patch.dict(os.environ, {"QA_BUDGET_WEEKLY": "70"}):
                self.assertIsNone(self.agree())
            with mock.patch.dict(os.environ, {"QA_BUDGET_WEEKLY": "50"}):
                self.assertIn("ceiling 50%", self.agree())


class StatusLine(unittest.TestCase):
    def test_an_older_lower_reading_does_not_replace_a_newer_one(self):
        with tempfile.TemporaryDirectory() as folder:
            def show(week, reset):
                session = {"model": {"display_name": "Opus"},
                           "rate_limits": {"seven_day": {"used_percentage": week, "resets_at": reset}}}
                subprocess.run([sys.executable, os.path.join(FOLDER, "statusline.py")], input=json.dumps(session),
                               capture_output=True, text=True, env=dict(os.environ, CLAUDE_CONFIG_DIR=folder), check=True)
                with open(os.path.join(folder, "qa-budget", "rate-limits.json")) as f:
                    return json.load(f)["rate_limits"]["seven_day"]["used_percentage"]
            self.assertEqual(show(50, 2000000000), 50)
            self.assertEqual(show(40, 2000000000), 50)
            self.assertEqual(show(5, 2000600000), 5)


if __name__ == "__main__":
    unittest.main(verbosity=1)
