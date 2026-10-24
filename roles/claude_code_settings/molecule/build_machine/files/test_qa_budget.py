"""Tests of qa-budget's guard and status line: python3 test_qa_budget.py <folder of guard.py>. Each test runs the hook as Claude
Code does, with a fresh configuration directory holding the readings and ledger it sets up."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

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
