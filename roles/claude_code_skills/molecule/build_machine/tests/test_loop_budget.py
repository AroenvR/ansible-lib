"""A budget stop ends the loop, and the hours limit (FR-3, FR-2; IF-101, IF-102; AC-2, AC-3; architecture section 8).

The program asks qa-budget's guard (--budget-guard PATH, its prompt_block(moment)) only for a wake-up that would be
let through. A ceiling or the limit ends the loop at that wake-up; a guard that cannot answer ends it too. The tests
set the status line's reading in a CLAUDE_CONFIG_DIR of their own (the harness does, per test), never this
machine's. Stub guards stand in where the failure of the guard is the point. B-numbers and H-numbers are the
architecture's section 8."""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

from harness import (A, B, B_NONE, BUDGET_PREFIX, DROP, ERROR_TEXT_RE, GUARD, J1, MAX_HOURS, NO_STATE_LOOP, PROGRAM,
                     SECRET, T0, LoopTestCase, b_ended, b_missing, b_other, event, failing_create, hook_argv,
                     item_job, load_guard, removal_notice, stamp, write)

MAX = 5   # the tests' --max-wakes: room for a few wake-ups before the maximum


class BudgetTestCase(LoopTestCase):
    """A conversation A with a started loop and its job, the hook's guard being the repository's."""

    def setUp(self):
        super().setUp()
        self.loop = self.started_with_job(A, J1, MAX)

    def wake_up(self, now=None, guard=None, session=A, max_hours=MAX_HOURS):
        return self.hook(self.wake(session, self.loop), MAX, now=now, guard=guard, max_hours=max_hours)

    def ended_why(self, reason, loop=None):
        """The reason inside a B-ENDED text of this loop."""
        head, tail = b_ended(loop or self.loop, "\0", [J1]).split("\0")
        self.assertTrue(reason.startswith(head) and reason.endswith(tail), "not B-ENDED: %r" % reason)
        return reason[len(head):len(reason) - len(tail)]

    def assertBudgetEnd(self, why, wakes=0):
        """The loop's end is recorded with this reason by the hook, in ended.json and in state.json."""
        ended = self.ended(self.loop)
        self.assertIsNotNone(ended, "no ended.json")
        self.assertEqual((ended["by"], ended["reason"]), ("hook", why))
        state = self.state(self.loop)
        self.assertEqual(state["ended"]["reason"], why)
        self.assertEqual(state["wakes"], wakes, "a blocked wake-up was counted")

    def assertNotEnded(self, loop=None):
        self.assertIsNone(self.ended(loop or self.loop))
        self.assertIsNone(self.state(loop or self.loop)["ended"])


class OverACeilingTest(BudgetTestCase):

    def test_a_wake_up_over_the_weekly_ceiling_is_blocked_and_the_loop_ends(self):
        """TEST-110 (AC-3, B1): a reading of 61% of the week (ceiling 60): the wake-up is blocked with B-ENDED whose
        reason is the budget prefix and the guard's own text; not counted; ended.json and state.json say so."""
        self.reading(weekly=61)
        text = self.guard_text()
        self.assertIn("the weekly ceiling (61% of the week used, ceiling 60%) is reached", text)
        why = BUDGET_PREFIX + text
        self.assertLessEqual(len(why), 200, "the program keeps a reason to one line of 200 characters")

        result = self.wake_up()
        self.assertEqual(self.assertWakeBlocked(result), b_ended(self.loop, why, [J1]))
        self.assertEqual(result.err, "")

        self.assertBudgetEnd(why)
        state = self.state(self.loop)
        self.assertEqual(state["ended"], {"at": stamp(T0), "reason": why})
        self.assertEqual((state["max"], state["max_hours"]), (MAX, MAX_HOURS), "every hook write stores the limits")
        self.assertEqual(self.ended(self.loop)["at"], stamp(T0))
        self.assertIn("wake-up blocked: the loop has ended (%s)" % why, self.log(self.loop))
        status = self.cli("status").out
        self.assertIn(why, status, "status does not name the budget as the reason")
        self.assertIn("ended (", status)

    def test_a_later_wake_up_with_the_reading_back_under_the_ceiling_stays_blocked(self):
        """TEST-111 (AC-3, B2): the budget recovers (10%); the next wake-up is still blocked as ended, with the first
        reason; nothing is counted, the record of the end is not rewritten."""
        self.reading(weekly=61)
        why = BUDGET_PREFIX + self.guard_text()
        self.assertWakeBlocked(self.wake_up())
        ended_before = self.ended(self.loop)

        for minutes in (30, 60):
            later = T0 + timedelta(minutes=minutes)
            self.reading(weekly=10, five_hour=10, moment=later)
            reason = self.assertWakeBlocked(self.wake_up(now=later))
            self.assertEqual(reason, b_ended(self.loop, why, [J1]))
            self.assertEqual(self.ended(self.loop), ended_before, "the first end must stay as it was recorded")
            self.assertBudgetEnd(why)
            self.assertEqual(self.state(self.loop)["ended"]["at"], stamp(T0))

    def test_the_guard_is_not_asked_again_once_the_loop_has_ended(self):
        """TEST-112 (B2): a later wake-up of the ended loop is judged by ended.json alone: the guard sees one call."""
        guard, record = self.recording_guard('"a ceiling is reached; it resets soon"')
        self.assertWakeBlocked(self.wake_up(guard=guard))
        self.assertEqual(len(self.calls(record)), 1)
        later = T0 + timedelta(minutes=30)
        reason = self.assertWakeBlocked(self.wake_up(now=later, guard=guard))
        self.assertEqual(reason, b_ended(self.loop, BUDGET_PREFIX + "a ceiling is reached; it resets soon", [J1]))
        self.assertEqual(len(self.calls(record)), 1, "the guard was asked about a loop that had ended")

    def test_the_persons_next_prompt_is_told_the_loop_ended_because_of_the_budget(self):
        """TEST-113 (FR-3, B3): the next prompt a person starts in the conversation gets the removal notice (never a
        block) naming the job and the budget as why; it is repeated while a Stop still lists the job."""
        self.reading(weekly=61)
        why = BUDGET_PREFIX + self.guard_text()
        self.assertWakeBlocked(self.wake_up())
        self.reading(weekly=10)
        notice = self.assertNotice(self.hook(self.prompt(A, "What happened?"), MAX))
        self.assertEqual(notice, removal_notice(item_job(J1, self.loop, why)))

    def test_each_ceiling_and_the_limit_ends_the_loop(self):
        """TEST-114 (AC-3, B5): the 5-hour ceiling (91 of 90), the weekly ceiling (61 of 60) and the limit (98, in
        either window) each end the loop at the wake-up, with the guard's words for it."""
        cases = (("the 5-hour ceiling", dict(five_hour=91)), ("the weekly ceiling", dict(weekly=61)),
                 ("the subscription's limit", dict(weekly=98)), ("the subscription's limit", dict(five_hour=98)))
        for words, reading in cases:
            with self.subTest(words=words, reading=reading):
                self.new_home()
                self.loop = self.started_with_job(A, J1, MAX)
                self.reading(**reading)
                text = self.guard_text()
                self.assertIn(words, text)
                reason = self.assertWakeBlocked(self.wake_up())
                self.assertEqual(reason, b_ended(self.loop, BUDGET_PREFIX + text, [J1]))
                self.assertBudgetEnd(BUDGET_PREFIX + text)

    def test_the_guards_environment_limits_apply_to_the_loop_as_to_the_guard(self):
        """TEST-115 (B11): one set of limits: QA_BUDGET_WEEKLY moves the ceiling for the loop's check too."""
        self.reading(weekly=55)
        with mock.patch.dict(os.environ, {"QA_BUDGET_WEEKLY": "56"}):
            self.assertContext(self.wake_up(), self.loop, 1, MAX)
        self.assertNotEnded()
        with mock.patch.dict(os.environ, {"QA_BUDGET_WEEKLY": "50"}):
            text = self.guard_text()
            self.assertIn("ceiling 50%", text)
            reason = self.assertWakeBlocked(self.wake_up(now=T0 + timedelta(minutes=1)))
        self.assertIn("ceiling 50%", reason)
        self.assertEqual(self.state(self.loop)["wakes"], 1)

    def test_a_budget_end_while_another_end_won_first_keeps_the_first_reason(self):
        """TEST-116 (B10): ended.json appears between the loop's check and the guard's answer (another end won the
        race): the first reason stays, in ended.json, in state.json and in the block."""
        path = self.path("loops", self.loop, "ended.json")
        guard = self.stub_guard("""
            import json

            def prompt_block(moment):
                with open(PATH, "x") as handle:
                    handle.write(json.dumps({"at": "2026-10-20T12:00:00+00:00", "reason": "stopped by the person",
                                             "by": "person"}) + "\\n")
                return "the weekly ceiling (61% of the week used, ceiling 60%) is reached; it resets soon"
            """.replace("PATH", repr(path)))
        first = self.assertWakeBlocked(self.wake_up(guard=guard))
        self.assertEqual(first, b_ended(self.loop, "stopped by the person", [J1]))
        ended = self.ended(self.loop)
        self.assertEqual((ended["by"], ended["reason"]), ("person", "stopped by the person"))
        self.assertEqual(self.state(self.loop)["ended"]["reason"], "stopped by the person")
        self.assertEqual(self.state(self.loop)["wakes"], 0)

    def test_ended_json_that_cannot_be_written_blocks_the_wake_up_without_ending_the_loop(self):
        """TEST-117 (B9): the end cannot be recorded: B-ERROR (write ended), not counted, not ended; the next fire
        asks the guard again and then ends the loop."""
        self.reading(weekly=61)
        why = BUDGET_PREFIX + self.guard_text()
        before = self.state(self.loop)
        with failing_create("ended.json"):
            error = self.assertBError(self.wake_up(), self.loop)
        self.assertRegex(error, ERROR_TEXT_RE)
        self.assertTrue(error.startswith("write ended: "), error)
        self.assertNotEnded()
        self.assertEqual(self.state(self.loop)["wakes"], before["wakes"])

        reason = self.assertWakeBlocked(self.wake_up(now=T0 + timedelta(minutes=1)))
        self.assertEqual(reason, b_ended(self.loop, why, [J1]))
        self.assertBudgetEnd(why)


class UnderTheCeilingsTest(BudgetTestCase):

    def test_a_wake_up_under_the_ceilings_is_let_through_and_counted(self):
        """TEST-118 (AC-3, B4): a reading just under both ceilings (59, 89): wake-up 1 of N, as before the budget."""
        self.reading(weekly=59, five_hour=89)
        self.assertContext(self.wake_up(), self.loop, 1, MAX)
        self.assertNotEnded()
        self.assertEqual(self.state(self.loop)["wakes"], 1)

    def test_unknown_usage_passes_as_it_does_for_the_guard(self):
        """TEST-119 (B4): no reading, and a reading from before the guard's 10 minutes that is under the ceilings:
        the wake-up passes (only a ceiling, the limit or a broken guard ends the loop)."""
        self.no_reading()
        self.assertContext(self.wake_up(), self.loop, 1, MAX)
        self.reading(weekly=20, moment=T0 - timedelta(minutes=11))
        self.assertContext(self.wake_up(now=T0 + timedelta(minutes=1)), self.loop, 2, MAX)
        self.assertNotEnded()

    def test_a_reading_of_a_window_that_has_reset_counts_as_zero(self):
        """TEST-120 (B4): 99% in a window whose reset has passed does not stop the wake-up (the guard's rule)."""
        os.makedirs(self.budget_dir, exist_ok=True)
        write(os.path.join(self.budget_dir, "rate-limits.json"), json.dumps({"time": stamp(T0), "rate_limits": {
            "five_hour": {"used_percentage": 99, "resets_at": int(T0.timestamp()) - 60},
            "seven_day": {"used_percentage": 99, "resets_at": int(T0.timestamp()) - 60}}}))
        self.assertContext(self.wake_up(), self.loop, 1, MAX)

    def test_a_loop_at_its_maximum_of_wake_ups_does_not_ask_the_guard(self):
        """TEST-121 (B7): rule 6 comes before the guard: every wake-up that is let through asks it once, the one
        after the maximum is blocked "N wake-ups used" without a call."""
        guard, record = self.recording_guard()
        for k in range(1, MAX + 1):
            when = T0 + timedelta(minutes=30 * k)
            pid = self.pid()
            self.assertContext(self.hook(self.wake(A, self.loop, pid), MAX, now=when, guard=guard), self.loop, k, MAX)
            self.hook(self.stop(A, pid, [(J1, self.loop)]), MAX, now=when, guard=guard)
        self.assertEqual(len(self.calls(record)), MAX)
        reason = self.assertWakeBlocked(self.wake_up(guard=guard, now=T0 + timedelta(hours=4)))
        self.assertEqual(reason, b_ended(self.loop, "%d wake-ups used" % MAX, [J1]))
        self.assertEqual(len(self.calls(record)), MAX, "the guard was asked about a loop at its maximum")


class GuardCallTest(BudgetTestCase):

    def test_the_guard_is_asked_once_with_the_programs_own_now_as_an_aware_utc_time(self):
        """TEST-122 (B8): one call to prompt_block, one positional argument, an aware datetime in UTC equal to the
        injected now (also when the clock is given in another zone)."""
        guard, record = self.recording_guard()
        self.assertContext(self.wake_up(guard=guard), self.loop, 1, MAX)
        calls = self.calls(record)
        self.assertEqual(calls, [{"args": [["datetime", "2026-10-20T12:00:00+00:00", "0:00:00"]], "kwargs": []}])

        elsewhere = (T0 + timedelta(minutes=30)).astimezone(timezone(timedelta(hours=2)))
        self.assertContext(self.wake_up(guard=guard, now=elsewhere), self.loop, 2, MAX)
        self.assertEqual(self.calls(record)[1]["args"], [["datetime", "2026-10-20T12:30:00+00:00", "0:00:00"]])

    def test_a_guard_that_answers_none_lets_the_wake_up_through_as_before(self):
        """TEST-123 (B4): a stub that answers None: rule 7 unchanged (wake-up 1 of N, counted, nothing ended)."""
        guard, record = self.recording_guard("None")
        result = self.wake_up(guard=guard)
        self.assertContext(result, self.loop, 1, MAX)
        self.assertEqual(self.state(self.loop)["wakes"], 1)
        self.assertNotEnded()
        self.assertEqual(len(self.calls(record)), 1)

    def test_loading_the_guard_leaves_the_programs_process_as_it_was(self):
        """TEST-124 (IF-101): the guard is loaded without registering it, and sys.path is as it was (guard.py puts its
        own folder first); with a ceiling reached, the same."""
        self.reading(weekly=61)
        path = list(sys.path)
        self.assertWakeBlocked(self.wake_up())
        self.assertEqual(sys.path, path)
        for name in ("qa_budget_guard", "guard"):
            self.assertNotIn(name, sys.modules)

    def test_the_guard_leaves_no_bytecode_next_to_it(self):
        """TEST-125 (IF-101): sys.dont_write_bytecode while loading: no __pycache__ in the guard's folder, which is
        read-only in the image. Run on a copy of the folder, with bytecode otherwise allowed."""
        folder = os.path.join(self.tmp, "copy-of-qa-budget")
        shutil.copytree(os.path.dirname(GUARD), folder, ignore=shutil.ignore_patterns("__pycache__"))
        with mock.patch.dict(sys.modules), mock.patch.object(sys, "dont_write_bytecode", False):
            sys.modules.pop("ledger", None)   # guard.py imports it from its own folder: a fresh import, the copy's
            self.assertContext(self.wake_up(guard=os.path.join(folder, os.path.basename(GUARD))), self.loop, 1, MAX)
        self.assertNotIn("__pycache__", os.listdir(folder))


class GuardThatCannotAnswerTest(BudgetTestCase):
    """B6: qa-budget is required, so a guard that cannot be asked ends the loop: the wake-up is never let through
    unchecked. The text names the step (budget) and the class, for an OSError also its strerror and filename, never
    an exception's message."""

    def missing(self):
        return os.path.join(self.tmp, "no-such-guard.py")

    def cases(self):
        folder = os.path.join(self.tmp, "a-folder")
        os.makedirs(os.path.join(folder, "guard.py"))
        unreadable = self.stub_guard("def prompt_block(moment):\n    return None\n", "unreadable-guard.py")
        os.chmod(unreadable, 0)
        cases = {
            "the path is missing": (self.missing(), r"FileNotFoundError: No such file or directory \("),
            "the path is a folder": (os.path.join(folder, "guard.py"), r"IsADirectoryError: Is a directory \("),
            "a syntax error": (self.stub_guard("def prompt_block(:\n"), r"SyntaxError"),
            "an import that fails": (self.stub_guard("import no_such_module_in_any_python\n"), r"ModuleNotFoundError"),
            "no prompt_block": (self.stub_guard("answer = 42\n"), r"[A-Za-z_][A-Za-z0-9_.]*"),
            "a prompt_block that is not callable": (self.stub_guard("prompt_block = 'text'\n"),
                                                    r"[A-Za-z_][A-Za-z0-9_.]*"),
            "a prompt_block that raises": (self.stub_guard(
                "def prompt_block(moment):\n    raise RuntimeError(%r)\n" % SECRET), r"RuntimeError"),
            "an answer of 5": (self.stub_guard("def prompt_block(moment):\n    return 5\n"),
                               r"[A-Za-z_][A-Za-z0-9_.]*"),
            "an empty answer": (self.stub_guard("def prompt_block(moment):\n    return ''\n"),
                                r"[A-Za-z_][A-Za-z0-9_.]*"),
            "an answer that is not text": (self.stub_guard("def prompt_block(moment):\n    return ['over']\n"),
                                           r"[A-Za-z_][A-Za-z0-9_.]*"),
        }
        if os.geteuid() != 0:   # root reads a file of mode 000
            cases["an unreadable file"] = (unreadable, r"PermissionError: Permission denied \(")
        return cases

    def test_a_guard_that_cannot_answer_ends_the_loop_and_blocks_the_wake_up(self):
        """TEST-126 (AC-3, B6): each failure: rc 0, the wake-up blocked with B-ENDED, nothing counted, the end recorded
        (ended.json by the hook and state.json), no exception message anywhere."""
        head = BUDGET_PREFIX + "its guard could not be asked (budget: "
        for case, (guard, detail) in self.cases().items():
            with self.subTest(case):
                self.new_home()
                self.loop = self.started_with_job(A, J1, MAX)
                result = self.wake_up(guard=guard)
                why = self.ended_why(self.assertWakeBlocked(result))
                self.assertRegex(why, r"^" + re.escape(head) + detail)
                if detail.endswith(r"\("):   # an OSError: strerror and the file's name; the reason is cut at 200
                    self.assertTrue(why.endswith("))") and os.path.basename(guard) in why or len(why) == 200, why)
                else:
                    self.assertTrue(why.endswith(")") and "(" not in why[len(head):], why)
                self.assertBudgetEnd(why)
                self.assertNotIn(SECRET, self.all_text() + result.out + result.err)
                self.assertEqual(result.err, "")
                # It is an end: the next wake-up is blocked with the same reason, also with a working guard.
                self.reading(weekly=10)
                again = self.assertWakeBlocked(self.wake_up(now=T0 + timedelta(minutes=30)))
                self.assertEqual(again, b_ended(self.loop, why, [J1]))

    def test_a_missing_guard_leaves_every_other_event_as_it_was(self):
        """TEST-127 (B7): with the guard path missing, a person's prompt, a Stop, a StopFailure and a subagent's event
        behave as they do with any guard (no output, exit 0; a person's prompt never blocked), and a wake-up that
        the program blocks before the guard is blocked with its usual text."""
        guard = self.missing()
        subagent = self.wake(A, self.loop)
        subagent.update(agent_id="a6a6426aff7977e1e", agent_type="tester")
        passes = {
            "a person's prompt": self.prompt(A, "Please go on."),
            "a Stop": self.stop(A, self.pid(), [(J1, self.loop)]),
            "a StopFailure": self.failure(A, self.pid()),
            "a subagent's marked prompt": subagent,
            "a Stop in a conversation without a loop": self.stop(B, self.pid(), crons=DROP),
        }
        for case, data in passes.items():
            with self.subTest(case):
                self.assertPass(self.hook(data, MAX, guard=guard))
        self.assertNotEnded()
        self.assertEqual(self.state(self.loop)["wakes"], 0)

        blocked = {
            "a wake-up of a loop without state": (self.wake(A, NO_STATE_LOOP), b_missing(NO_STATE_LOOP)),
            "a wake-up that names no loop": (self.prompt(A, "[auto loop-to-delivery] Wake-up: continue."), B_NONE),
            "a wake-up of another conversation's loop": (self.wake(B, self.loop), b_other(self.loop, [J1])),
        }
        for case, (data, text) in blocked.items():
            with self.subTest(case):
                self.assertEqual(self.assertWakeBlocked(self.hook(data, MAX, guard=guard)), text)


class NotAskedTest(BudgetTestCase):
    """B7: the guard is asked for nothing but a wake-up that would be let through."""

    def test_the_guard_is_not_asked_for_anything_else(self):
        """TEST-128 (B7): a person's prompt, a Stop, a StopFailure, a subagent's event, and a wake-up of a loop that
        has ended, of another conversation's loop, of a loop without state or naming none: a stub that records its
        calls is never called."""
        guard, record = self.recording_guard('"a ceiling is reached; it resets soon"')
        subagent = self.wake(A, self.loop)
        subagent.update(agent_id="a6a6426aff7977e1e", agent_type="tester")
        for case, data in {"a person's prompt": self.prompt(A, "Please go on."),
                           "a Stop": self.stop(A, self.pid(), [(J1, self.loop)]),
                           "a StopFailure": self.failure(A, self.pid()),
                           "a subagent's marked prompt": subagent,
                           "SubagentStop": event("subagent-stop", session_id=A)}.items():
            with self.subTest(case):
                self.assertPass(self.hook(data, MAX, guard=guard))
        for case, data, text in (
                ("a loop without state", self.wake(A, NO_STATE_LOOP), b_missing(NO_STATE_LOOP)),
                ("a wake-up naming no loop", self.prompt(A, "[auto loop-to-delivery] Wake-up."), B_NONE)):
            with self.subTest(case):
                self.assertEqual(self.assertWakeBlocked(self.hook(data, MAX, guard=guard)), text)
        self.assertEqual(self.calls(record), [], "the guard was asked for an event that is not a wake-up to let through")

        # Another conversation's loop: blocked and ended without a call.
        self.assertEqual(self.assertWakeBlocked(self.wake_up(session=B, guard=guard)), b_other(self.loop, [J1]))
        self.assertEqual(self.calls(record), [])

        # A loop that has ended (here by the other conversation's wake-up).
        self.new_home()
        self.loop = self.started_with_job(A, J1, MAX)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        self.assertEqual(self.assertWakeBlocked(self.wake_up(guard=guard)), b_ended(self.loop, "delivered", [J1]))
        self.assertEqual(self.calls(record), [], "the guard was asked about a loop that had ended")

        # The hours limit is rule 6 too.
        self.new_home()
        self.loop = self.started_with_job(A, J1, MAX)
        limit = T0 + timedelta(hours=24)
        self.assertEqual(self.assertWakeBlocked(self.wake_up(guard=guard, now=limit, max_hours=24)),
                         b_ended(self.loop, "24 hours passed", [J1]))
        self.assertEqual(self.calls(record), [])


class HoursTest(BudgetTestCase):
    """FR-2 in the program (IF-102): --max-hours replaces the fixed 7 days."""

    def test_a_raised_maximum_does_not_undo_a_recorded_end(self):
        """TEST-129 (AC-2, H2): the loop ended at 24 hours; a later hook with --max-hours 168 (a deploy that raised
        the limit) still blocks it as ended with the first reason."""
        limit = T0 + timedelta(hours=24)
        reason = self.assertWakeBlocked(self.wake_up(now=limit, max_hours=24))
        self.assertEqual(reason, b_ended(self.loop, "24 hours passed", [J1]))
        self.assertEqual(self.state(self.loop)["max_hours"], 24, "a blocked wake-up stores the hook's limit")
        again = self.assertWakeBlocked(self.wake_up(now=limit + timedelta(minutes=30), max_hours=168))
        self.assertEqual(again, b_ended(self.loop, "24 hours passed", [J1]))
        self.assertEqual(self.state(self.loop)["ended"], {"at": stamp(limit), "reason": "24 hours passed"})

    def test_a_hook_uses_its_own_maximum_not_the_stored_one(self):
        """TEST-134 (AC-2, IF-102): the state holds 168 (the Stop of setUp wrote it); a hook that now gives 24 is
        judged by its own 24 at start + 24 hours, a hook that gives 168 is not."""
        limit = T0 + timedelta(hours=24)
        self.assertEqual(self.state(self.loop)["max_hours"], MAX_HOURS)
        self.assertContext(self.wake_up(now=limit, max_hours=168), self.loop, 1, MAX)
        self.new_home()
        self.loop = self.started_with_job(A, J1, MAX)
        reason = self.assertWakeBlocked(self.wake_up(now=limit, max_hours=24))
        self.assertEqual(reason, b_ended(self.loop, "24 hours passed", [J1]))

    def test_the_hours_are_unknown_until_a_hook_writes_them_and_then_the_commands_use_them(self):
        """TEST-130 (H3): between start and the first hook write max_hours is null and status says "not recorded
        yet"; a hook stores its value; status and start then judge by it, not by 168 hours."""
        self.new_home()
        loop = self.start(A)
        self.assertIsNone(self.state(loop)["max_hours"])
        self.assertIn("not recorded yet", self.cli("status", now=T0 + timedelta(hours=100)).out)
        later = T0 + timedelta(hours=100)
        self.assertEqual(self.cli("status", now=later).rc, 0)
        self.assertNotIn("hours passed", self.cli("status", now=later).out, "an unknown limit must not end the loop")

        result = self.hook(self.wake(A, loop), 3, now=T0 + timedelta(hours=1), max_hours=24)
        self.assertContext(result, loop, 1, 3)
        self.assertEqual(self.state(loop)["max_hours"], 24)
        status = self.cli("status", now=T0 + timedelta(hours=2)).out
        self.assertIn(stamp(T0 + timedelta(hours=24)), status, "status gives started + max_hours")
        self.assertNotIn("not recorded yet", status)
        status = self.cli("status", now=T0 + timedelta(hours=25)).out
        self.assertIn("24 hours passed", status)
        refused = self.main(["start", "--notes", self.notes, "--session", A], now=T0 + timedelta(hours=25),
                            environ={"HOME": self.home})
        self.assertEqual(refused.rc, 2, refused)
        self.assertIn("24 hours passed", refused.err)

    def test_a_state_of_the_bundles_program_is_read_with_the_hours_unknown(self):
        """TEST-131 (R5, IF-102): a state with a deadline and no max_hours is a readable state: the wake-up passes
        and the hook stores its --max-hours."""
        state = self.state(self.loop)
        state.pop("max_hours", None)
        state["deadline"] = stamp(T0 + timedelta(days=7))
        write(self.path("loops", self.loop, "state.json"), json.dumps(state))
        self.assertContext(self.wake_up(), self.loop, 1, MAX)
        self.assertEqual(self.state(self.loop)["max_hours"], MAX_HOURS)

    def test_the_hours_limit_comes_before_the_budget_check(self):
        """TEST-132 (IF-102 with IF-101): at the hours limit with a reading over a ceiling, the reason is the hours
        (rule 6 before 6b): the older cause wins, and the guard is not asked."""
        self.reading(weekly=61, moment=T0 + timedelta(hours=24))
        reason = self.assertWakeBlocked(self.wake_up(now=T0 + timedelta(hours=24), max_hours=24))
        self.assertEqual(reason, b_ended(self.loop, "24 hours passed", [J1]))


class ProcessTest(BudgetTestCase):
    """The program as Claude Code runs it: python3 -I loop_to_delivery.py hook ... with the guard's path."""

    def run_hook(self, data, guard):
        environ = {"HOME": self.home, "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CLAUDE_CONFIG_DIR": self.claude}
        return subprocess.run([sys.executable, "-I", PROGRAM] + hook_argv(MAX, MAX_HOURS, guard),
                              input=json.dumps(data), capture_output=True, text=True, env=environ, timeout=60)

    def test_a_budget_stop_works_in_a_process_under_isolated_mode(self):
        """TEST-133 (AC-3): with -I (no environment's PYTHONPATH, no cwd on sys.path) the guard loads from its
        path: under the ceiling the wake-up is let through, over it the process prints the block (exit 0) and writes
        no bytecode next to the guard. The guard is a copy of the folder, so a stray __pycache__ shows."""
        folder = os.path.join(self.tmp, "qa-budget")
        shutil.copytree(os.path.dirname(GUARD), folder, ignore=shutil.ignore_patterns("__pycache__"))
        guard = os.path.join(folder, os.path.basename(GUARD))
        now = datetime.now(timezone.utc).replace(microsecond=0)   # the child process reads the real clock
        self.new_home()
        loop = self.start(A, now=now)
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop)]), MAX, now=now))

        self.reading(weekly=10, moment=now)
        proc = self.run_hook(self.wake(A, loop), guard)
        self.assertEqual(proc.returncode, 0, proc)
        context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith("loop-to-delivery: wake-up 1 of %d of loop %s" % (MAX, loop)), context)

        self.reading(weekly=61, moment=now)
        text = self.guard_text(now)
        proc = self.run_hook(self.wake(A, loop), guard)
        self.assertEqual(proc.returncode, 0, proc)
        self.assertEqual(json.loads(proc.stdout), {"decision": "block", "reason": b_ended(
            loop, BUDGET_PREFIX + text, [J1])})
        self.assertEqual(self.ended(loop)["by"], "hook")
        self.assertNotIn("__pycache__", os.listdir(folder))

        other = self.start(B, now=now)
        self.assertPass(self.hook(self.stop(B, self.pid(), [(J1, other)]), MAX, now=now))
        proc = self.run_hook(self.wake(B, other), os.path.join(self.tmp, "no-such-guard.py"))
        self.assertEqual(proc.returncode, 0, proc)
        self.assertEqual(proc.stderr, "")
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "block")
        self.assertTrue(self.ended_why(data["reason"], other).startswith(
            BUDGET_PREFIX + "its guard could not be asked (budget: FileNotFoundError"), data)
