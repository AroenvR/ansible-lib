"""loop-to-delivery's commands (start, end, stop, status), its files and its process (IF-008, IF-009)."""

import json
import os
import re
import stat
import subprocess
import sys
from datetime import timedelta
from unittest import mock

from harness import (A, B, C, DEADLINE, GUARD, J1, J2, MAX_HOURS, NO_STATE_LOOP, PROGRAM, T0, LoopTestCase, b_ended,
                     b_missing, create_line, hook_argv, stamp)

STAMP_RE = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00"


class StartTest(LoopTestCase):

    def test_start_prints_the_loop_and_its_exact_wake_up_job(self):
        """TEST-001: start makes a loop of the conversation, its state and record, and prints its exact job."""
        result = self.main(["start", "--session", A, "--notes", self.notes, "--watch", self.repo],
                           now=T0 + timedelta(microseconds=123456))
        self.assertEqual(result.rc, 0, result)
        lines = result.out.rstrip("\n").split("\n")
        self.assertEqual(len(lines), 3, result.out)
        match = re.match(r"^loop-to-delivery: loop ([0-9a-f]{8}) ", lines[0])
        self.assertIsNotNone(match, lines[0])
        loop = match.group(1)
        self.assertEqual(lines, [
            "loop-to-delivery: loop %s started for this conversation (%s); notes: %s." % (loop, A, self.notes),
            'Create its wake-up job once; skip this if CronList already shows a job whose prompt starts with '
            '"[auto loop-to-delivery %s]":' % loop,
            create_line(loop),
        ])

        state = self.state(loop)
        self.assertIsInstance(state.pop("check_fp"), str)
        state.pop("stop_fp", None)   # set at each wake-up; its value at start is the program's
        self.assertEqual(state, {
            "version": 1, "loop": loop, "session_id": A,
            "started": "2026-10-20T12:00:00+00:00",
            "notes": self.notes, "watch": [self.repo],
            "wakes": 0, "max": None, "max_hours": None, "idle": 0, "wake_prompt_id": None, "idle_counted": False, "failed": False,
            "job_asked": False, "stop_blocks": 0, "jobs": [], "ended": None, "end_notice": False,
        })
        self.assertEqual(self.record(A), {"version": 1, "session_id": A, "loop": loop, "prompt_after_end": None,
                                          "jobs": []})
        self.assertIsNone(self.ended(loop))
        for line in self.log(loop).splitlines():
            self.assertRegex(line, "^" + STAMP_RE + " ")

        # IF-009: folders 0700, files 0600, below the state root.
        for folder, dirs, names in os.walk(self.root):
            self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700, folder)
            for name in names:
                self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, name)).st_mode), 0o600, name)

    def test_the_job_prompt_start_prints_is_an_automatic_prompt_to_a_budget_guard(self):
        """TEST-086: QD18: the printed job prompt starts with [auto loop-to-delivery <id>], so it matches the
        qa-budget guard's default pattern for automatic prompts (the regex below)."""
        result = self.main(["start", "--session", A, "--notes", self.notes, "--watch", self.repo], now=T0)
        self.assertEqual(result.rc, 0, result)
        last = result.out.rstrip("\n").split("\n")[-1]
        self.assertTrue(last.startswith("CronCreate "), last)
        prompt = json.loads(last[len("CronCreate "):])["prompt"]
        loop = self.record_of(A)["loop"]
        self.assertTrue(prompt.startswith("[auto loop-to-delivery %s]" % loop), prompt)
        self.assertIsNotNone(re.match(r"^\s*\[auto\b[^\]\n]*\]", prompt), prompt)

    def test_start_refuses_relative_paths_and_a_missing_or_invalid_session(self):
        """TEST-002: start exits 2 with a reason for a relative path or no/invalid session, and writes no loop."""
        allowed = {os.path.join(".local", "state", "loop-to-delivery", "errors.log")}
        cases = {
            "relative notes": ["start", "--session", A, "--notes", "notes.md"],
            "relative watch": ["start", "--session", A, "--notes", self.notes, "--watch", "repo"],
            "no session": ["start", "--notes", self.notes],
            "invalid session": ["start", "--session", "../../evil", "--notes", self.notes],
            "session too long": ["start", "--session", "a" * 129, "--notes", self.notes],
        }
        for case, argv in cases.items():
            with self.subTest(case):
                result = self.main(argv, environ={"HOME": self.home})
                self.assertEqual(result.rc, 2, result)
                self.assertTrue(result.err.strip(), "no reason on stderr")
                self.assertNotIn("CronCreate", result.out)
                self.assertLessEqual(set(self.files()), allowed)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil")))

        result = self.cli("start", "--notes", self.notes, env_session=B)
        self.assertEqual(result.rc, 0, result)
        self.assertIsNotNone(self.record(B), "start did not take the session from CLAUDE_CODE_SESSION_ID")

    def test_each_loop_gets_an_id_of_its_own(self):
        """TEST-003: loop ids are 8 lowercase hex digits, one per loop."""
        loops = {self.start(A), self.start(B), self.start(C)}
        self.assertEqual(len(loops), 3)
        self.assertEqual(sorted(os.listdir(self.path("loops"))), sorted(loops))

    def test_start_again_continues_the_active_loop(self):
        """TEST-004: start while the loop is active continues it: same job, new notes and watch, counters and max kept."""
        loop = self.started_with_job(A, J1, max_wakes=3)
        pid = self.let_through(loop, 1, 3)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 3))
        before = self.state(loop)
        notes = os.path.join(self.work, "notes-2.md")
        other = os.path.join(self.work, "artifacts")
        os.makedirs(other)
        result = self.main(["start", "--session", A, "--notes", notes, "--watch", self.repo, "--watch", other],
                           now=T0 + timedelta(hours=1))
        self.assertEqual(result.rc, 0, result)
        lines = result.out.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "loop-to-delivery: loop %s is already running for this conversation; its notes "
                                   "and watched paths are updated." % loop)
        self.assertEqual(lines[1:], [
            'Create its wake-up job once; skip this if CronList already shows a job whose prompt starts with '
            '"[auto loop-to-delivery %s]":' % loop,
            create_line(loop),
        ])
        after = self.state(loop)
        self.assertEqual((after["notes"], after["watch"]), (notes, [self.repo, other]))
        for field in ("loop", "session_id", "started", "max_hours", "wakes", "max", "idle", "jobs", "job_asked"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after["max"], 3, "start continuing a loop must keep max (G0 N11)")
        self.assertEqual(os.listdir(self.path("loops")), [loop])
        self.assertEqual(self.record_of(A)["loop"], loop)


class EndStopStatusTest(LoopTestCase):

    def test_end_ends_the_conversations_loop_and_names_its_job(self):
        """TEST-005: end records the end (by claude), names the job to delete; the next wake-up is blocked."""
        loop = self.started_with_job(A, J1)
        now = T0 + timedelta(hours=2, microseconds=500)
        result = self.cli("end", "--reason", "delivered", "--session", A, now=now)
        self.assertEqual(result.rc, 0, result)
        self.assertIn(loop, result.out)
        self.assertIn("delete its wake-up job %s (CronList, CronDelete)" % J1, result.out)
        self.assertEqual(self.ended(loop), {"at": stamp(now), "reason": "delivered", "by": "claude"})

        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        self.assertEqual(reason, b_ended(loop, "delivered", [J1]))
        self.assertEqual(self.state(loop)["ended"]["reason"], "delivered")

        again = self.cli("end", "--reason", "delivered", "--session", A)
        self.assertEqual(again.rc, 0, again)
        self.assertIn("no active loop", again.out + again.err)
        self.assertEqual(self.ended(loop)["at"], stamp(now), "a second end replaced the first")

        self.assertEqual(self.cli("end", "--reason", "delivered").rc, 2, "end without a session is misuse")

    def test_stop_ends_every_active_loop_of_the_account(self):
        """TEST-006: stop (the person) ends every active loop, lists them, and keeps an earlier end."""
        loop_a = self.started_with_job(A, J1)
        loop_b = self.started_with_job(B, J2)
        loop_c = self.start(C)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", C).rc, 0)
        ended_c = self.ended(loop_c)

        result = self.cli("stop", now=T0 + timedelta(hours=3))
        self.assertEqual(result.rc, 0, result)
        for token in (loop_a, loop_b, A, B, self.notes, J1, J2):
            self.assertIn(token, result.out)
        for loop in (loop_a, loop_b):
            ended = self.ended(loop)
            self.assertEqual((ended["by"], ended["reason"]), ("person", "stopped by the person"))
            self.assertEqual(ended["at"], stamp(T0 + timedelta(hours=3)))
        self.assertEqual(self.ended(loop_c), ended_c)

        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop_a)))
        self.assertEqual(reason, b_ended(loop_a, "stopped by the person", [J1]))

    def test_status_shows_the_loops_and_changes_nothing(self):
        """TEST-007: status is read-only and shows each loop, its conversation, state, notes and jobs."""
        loop = self.started_with_job(A, J1)
        pid = self.let_through(loop, 1, 2)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)])))
        before = self.snapshot()
        for argv in (["status"], ["status", "--session", A]):
            result = self.cli(*argv)
            self.assertEqual(result.rc, 0, result)
            for token in (loop, A, self.notes, J1, "active"):
                self.assertIn(token, result.out)
            self.assertEqual(self.snapshot(), before, "status wrote a file")

        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        result = self.cli("status")
        self.assertEqual(result.rc, 0, result)
        self.assertIn("ended", result.out)
        self.assertIn("delivered", result.out)


class FilesAndProcessTest(LoopTestCase):

    def test_state_lives_below_the_given_home_only(self):
        """TEST-008: the state root is $HOME/.local/state/loop-to-delivery of the environ passed to main()."""
        decoy = os.path.join(self.tmp, "decoy-home")
        os.makedirs(decoy)
        with mock.patch.dict(os.environ, {"HOME": decoy}):
            loop = self.started_with_job(A, J1)
            pid = self.let_through(loop, 1, 2)
            self.hook(self.stop(A, pid, [(J1, loop)]))
            self.cli("status")
        self.assertEqual(self.files(decoy), [])
        self.assertTrue(os.path.isfile(self.path("loops", loop, "state.json")))
        self.assertTrue(os.path.isfile(self.path("sessions", A + ".json")))

    def test_the_commands_take_none_of_the_hook_options(self):
        """TEST-101 (IF-102): --max-hours and --budget-guard belong to hook mode; start, end, stop and status are a
        usage error (exit 2, a usage line) with them, and change nothing."""
        loop = self.started_with_job(A, J1)
        before = self.snapshot()
        for command in (["status"], ["stop"], ["end", "--reason", "x", "--session", A],
                        ["start", "--notes", self.notes, "--session", A]):
            for extra in (["--max-hours", "24"], ["--budget-guard", GUARD]):
                with self.subTest(command=command[0], extra=extra[0]):
                    result = self.cli(*(command + extra))
                    self.assertEqual((result.rc, result.out), (2, ""), result)
                    self.assertTrue(result.err.startswith("loop-to-delivery: usage: "), result.err)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.state(loop)["wakes"], 0)

    def test_the_hook_usage_names_all_three_options(self):
        """TEST-102 (IF-102): the program's usage text for hook names --max-wakes, --max-hours and --budget-guard."""
        usage = self.prog.USAGE["hook"]
        for option in ("--max-wakes", "--max-hours", "--budget-guard"):
            self.assertIn(option, usage)

    def test_timestamps_are_utc_seconds_that_later_calls_read_back(self):
        """TEST-010: every time is isoformat(timespec=seconds) with +00:00, read back by later calls (G0 N7)."""
        loop = self.start(A, now=T0 + timedelta(microseconds=999999))
        state = self.state(loop)
        # IF-102: start writes no deadline; the limit is derived from max_hours, which the first hook write records.
        self.assertEqual(state["started"], stamp(T0))
        self.assertNotIn("deadline", state)
        self.assertIsNone(state["max_hours"])
        pid = self.let_through(loop, 1, 2, now=T0 + timedelta(minutes=37, microseconds=1))
        self.assertEqual(self.state(loop)["max_hours"], MAX_HOURS)
        self.assertNotIn("deadline", self.state(loop))
        self.assertIn(stamp(DEADLINE)[:10], self.cli("status").out, "status gives started + max_hours")
        self.hook(self.stop(A, pid, [(J1, loop)]))
        self.assertEqual(self.cli("status").rc, 0)
        end_time = T0 + timedelta(hours=1, microseconds=42)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A, now=end_time).rc, 0)
        self.assertEqual(self.ended(loop)["at"], "2026-10-20T13:00:00+00:00")
        self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        self.assertEqual(self.cli("status").rc, 0)
        text = self.all_text()
        self.assertNotRegex(text, r"\d\d:\d\d:\d\d\.\d", "a time with fractions of a second")
        self.assertNotRegex(text, r"\d\d:\d\d:\d\dZ", "a time ending in Z, which Python 3.9 cannot read")
        for line in self.log(loop).splitlines():
            self.assertRegex(line, "^" + STAMP_RE + " ")

    def run_program(self, args, stdin="", env=None):
        environ = {"HOME": self.home, "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                   "CLAUDE_CONFIG_DIR": self.claude}   # the guard reads this test's folder, never the machine's
        environ.update(env or {})
        return subprocess.run([sys.executable, "-I", PROGRAM] + args, input=stdin, capture_output=True,
                              text=True, env=environ, timeout=60)

    def test_the_program_runs_as_claude_code_runs_it(self):
        """TEST-009: run as a process (python3 -I P hook ...): exit 0 or 1, never 2; output as the protocol says."""
        hook = hook_argv()
        unknown = json.dumps(self.prompt(C, "an ordinary prompt"))
        wake = json.dumps(self.wake(C, NO_STATE_LOOP))

        proc = self.run_program(hook, unknown)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""), proc)
        self.assertEqual(self.files(), [], "a conversation without a loop got a file")

        proc = self.run_program(hook, wake)
        self.assertEqual(proc.returncode, 0, proc)
        self.assertTrue(proc.stdout.strip(), "a wake-up got no decision: %r" % (proc,))
        self.assertEqual(json.loads(proc.stdout), {"decision": "block", "reason": b_missing(NO_STATE_LOOP)})

        no_hours = ["hook", "--max-wakes", "2", "--budget-guard", GUARD]
        no_guard = ["hook", "--max-wakes", "2", "--max-hours", "24"]
        for args in (["hook", "--max-wakes", "x"], ["hook"], hook + ["--bogus"], no_hours, no_guard,
                     hook_argv(max_hours=0), hook_argv(max_hours=MAX_HOURS + 1), hook_argv(max_hours="x")):
            with self.subTest(args=args):
                proc = self.run_program(args, unknown)
                self.assertEqual((proc.returncode, proc.stdout), (1, ""), proc)
                self.assertTrue(proc.stderr.startswith("loop-to-delivery: "), proc.stderr)
                proc = self.run_program(args, wake)
                self.assertEqual(proc.returncode, 0, proc)
                self.assertTrue(proc.stdout.strip(), "a wake-up got no decision: %r" % (proc,))
                self.assertEqual(json.loads(proc.stdout)["decision"], "block")

        proc = self.run_program(hook, "this is not JSON")
        self.assertEqual((proc.returncode, proc.stdout), (1, ""), proc)

        proc = self.run_program(["start", "--notes", self.notes], env={"CLAUDE_CODE_SESSION_ID": A})
        self.assertEqual(proc.returncode, 0, proc)
        self.assertTrue(proc.stdout.rstrip("\n").split("\n")[-1].startswith("CronCreate "), proc.stdout)
