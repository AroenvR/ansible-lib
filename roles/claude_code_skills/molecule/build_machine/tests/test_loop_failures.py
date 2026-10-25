"""StopFailure (IF-010; QD11, QD14, QD15): which failed wake-ups count toward the maximum, and that none is idle."""

from datetime import timedelta

from harness import (A, B, COUNTED_ERRORS, DEADLINE, DROP, J1, NOT_RUN_ERRORS, LoopTestCase, b_ended, event)

# An `error` that is missing, null or not a string: counted, logged as "other" (IF-008, IF-010).
NO_STRING_ERRORS = (("missing", DROP), ("null", None), ("a number", 429), ("a list", ["rate_limit"]))


class FailureTest(LoopTestCase):

    def fail_turn(self, pid, error, max_wakes=2, now=None):
        data = self.failure(A, pid)
        if error is DROP:
            data.pop("error")
        else:
            data["error"] = error
        result = self.hook(data, max_wakes, now=now)
        self.assertPass(result)
        return result

    def judged(self, loop):
        state = self.state(loop)
        return state["idle"], state["check_fp"]

    def test_a_transient_failure_is_not_counted_and_not_idle(self):
        """TEST-050: each NOT_RUN_ERRORS value before the first Stop: wakes back, failed, not judged; the next fire
        is let through with the same k, also at k = max."""
        for error in NOT_RUN_ERRORS:
            with self.subTest(error):
                self.new_home()
                loop = self.started_with_job(A, J1)
                judged = self.judged(loop)
                pid = self.let_through(loop, 1, 2)
                self.fail_turn(pid, error)
                state = self.state(loop)
                self.assertEqual((state["wakes"], state["failed"], state["idle_counted"]), (0, True, True))
                self.assertEqual(self.judged(loop), judged, "a failed turn was judged idle")
                self.assertIn("wake 1 failed (%s), not counted" % error, self.log(loop))

                pid, result = self.woken_turn(loop, 1, 2)
                self.assertPass(result)
                pid = self.let_through(loop, 2, 2)
                self.fail_turn(pid, error)
                self.assertEqual(self.state(loop)["wakes"], 1)
                self.let_through(loop, 2, 2)

    def test_any_other_failure_is_counted_and_not_idle(self):
        """TEST-051: max_output_tokens, invalid_request, authentication_failed, unknown, documented values outside
        the set, a later value, a case variant, and no string at all: counted, failed, not judged; at k = max the
        next fire is B-ENDED "<max> wake-ups used"."""
        cases = [(value, logged) for value, logged in COUNTED_ERRORS]
        cases += [(value, "other") for _name, value in NO_STRING_ERRORS]
        for error, logged in cases:
            with self.subTest(error=error):
                self.new_home()
                loop = self.started_with_job(A, J1)
                judged = self.judged(loop)
                pid = self.let_through(loop, 1, 2)
                self.fail_turn(pid, error)
                state = self.state(loop)
                self.assertEqual((state["wakes"], state["failed"], state["idle_counted"]), (1, True, True))
                self.assertEqual(self.judged(loop), judged, "a failed turn was judged idle")
                self.assertIn("wake 1 failed (%s), counted" % logged, self.log(loop))
                self.assertNotIn("not counted", self.log(loop))

                pid = self.let_through(loop, 2, 2)
                self.fail_turn(pid, error)
                self.assertEqual(self.state(loop)["wakes"], 2)
                self.assertIsNone(self.state(loop)["ended"], "a StopFailure recorded an end")
                reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
                self.assertEqual(reason, b_ended(loop, "2 wake-ups used", [J1]))

    def test_only_the_first_failure_before_any_stop_acts(self):
        """TEST-052: a second StopFailure of the turn, or one after the turn's first Stop, changes no count; one of
        another turn or another conversation writes nothing."""
        loop = self.started_with_job(A, J1, max_wakes=5)
        pid = self.let_through(loop, 1, 5)
        self.fail_turn(pid, "max_output_tokens", 5)
        self.fail_turn(pid, "rate_limit", 5)
        self.assertEqual(self.state(loop)["wakes"], 1, "a second StopFailure of the turn un-counted it")

        pid, result = self.woken_turn(loop, 2, 5)
        self.assertPass(result)
        self.fail_turn(pid, "rate_limit", 5)    # a continuation's failure, after the first Stop
        self.assertEqual(self.state(loop)["wakes"], 2, "a failure after the first Stop un-counted the wake-up")

        pid = self.let_through(loop, 3, 5)
        before = self.state_bytes(loop)
        self.fail_turn(self.pid(), "rate_limit", 5)                     # another turn's prompt_id
        self.assertPass(self.hook(self.failure(B, pid), 5))              # another conversation
        self.assertPass(self.hook(event("stop-failure", session_id=A, prompt_id=DROP), 5))
        self.assertEqual(self.state_bytes(loop), before)
        self.assertIsNone(self.record(B))

    def test_a_loop_whose_wake_ups_all_fail_transiently_ends_only_at_the_deadline(self):
        """TEST-053: every wake-up fails with rate_limit: always wake-up 1, far beyond the maximum; the fire at the
        deadline is B-ENDED "7 days passed"."""
        loop = self.started_with_job(A, J1)
        when = self.now
        for _ in range(12):
            when += timedelta(hours=12)
            pid = self.let_through(loop, 1, 2, now=when)
            self.fail_turn(pid, "rate_limit", now=when)
        self.assertEqual(self.state(loop)["wakes"], 0)
        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop), now=DEADLINE))
        self.assertEqual(reason, b_ended(loop, "7 days passed", [J1]))

    def test_a_failed_wake_up_turn_is_never_continued_or_judged_later(self):
        """TEST-054: after a StopFailure, a later Stop of that turn neither judges idle nor counts again."""
        loop = self.started_with_job(A, J1, max_wakes=5)
        judged = self.judged(loop)
        pid = self.let_through(loop, 1, 5)
        self.fail_turn(pid, "max_output_tokens", 5)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 5))
        self.assertEqual(self.judged(loop), judged)
        self.assertEqual(self.state(loop)["wakes"], 1)
