"""End conditions (FR-043), idle judgement, continuations, the end notice and the job request (IF-010 Stop 6)."""

import os
from datetime import timedelta

from harness import (A, CONTINUATION_HEAD, DEADLINE, DROP, J1, J2, J3, NO_STATE_LOOP, LoopTestCase, append,
                     b_ended, cron, end_notice_head, j_create, stamp, write)



class MaximumTest(LoopTestCase):

    def test_the_last_allowed_wake_up_gets_the_end_notice_and_the_next_fire_is_blocked(self):
        """TEST-040: max: wake-up N's first Stop gives the end notice once; the next fire: B-ENDED "N wake-ups used"."""
        loop = self.started_with_job(A, J1)
        _pid, result = self.woken_turn(loop, 1, 2)
        self.assertPass(result)
        pid = self.let_through(loop, 2, 2)
        notice = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)])))
        self.assertTrue(notice.startswith(end_notice_head(loop, "2 wake-ups used")), notice)
        for part in (J1, self.notes, "CronDelete"):
            self.assertIn(part, notice)
        state = self.state(loop)
        self.assertEqual(state["ended"], {"at": stamp(self.now), "reason": "2 wake-ups used"})
        self.assertTrue(state["end_notice"])

        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)], active=True)), "the end notice came twice")
        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        self.assertEqual(reason, b_ended(loop, "2 wake-ups used", [J1]))
        self.assertEqual(self.state(loop)["wakes"], 2, "a blocked wake-up was counted")


class DeadlineTest(LoopTestCase):

    def test_after_seven_days_the_next_fire_is_blocked(self):
        """TEST-041: deadline (injected now): let through before it; at it B-ENDED "7 days passed", recorded by rule 6."""
        loop = self.started_with_job(A, J1, max_wakes=100)
        just_before = DEADLINE - timedelta(seconds=1)
        pid = self.let_through(loop, 1, 100, now=just_before)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 100, now=just_before))

        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop), 100, now=DEADLINE))
        self.assertEqual(reason, b_ended(loop, "7 days passed", [J1]))
        state = self.state(loop)
        self.assertEqual(state["ended"], {"at": stamp(DEADLINE), "reason": "7 days passed"})
        self.assertEqual(state["wakes"], 1)

    def test_a_deadline_passed_during_the_turn_gives_the_end_notice(self):
        """TEST-041b: the deadline passes between a wake-up and its first Stop: the end notice at that Stop."""
        loop = self.started_with_job(A, J1, max_wakes=100)
        pid = self.let_through(loop, 1, 100, now=DEADLINE - timedelta(minutes=1))
        notice = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)]), 100,
                                              now=DEADLINE + timedelta(minutes=1)))
        self.assertTrue(notice.startswith(end_notice_head(loop, "7 days passed")), notice)


class IdleTest(LoopTestCase):

    def test_six_wake_ups_in_a_row_without_progress_end_the_loop(self):
        """TEST-042: idle is judged at each wake-up's first Stop; the 6th unchanged one ends the loop (end notice)."""
        loop = self.started_with_job(A, J1, max_wakes=100)
        for k in range(1, 6):
            _pid, result = self.woken_turn(loop, k, 100)
            self.assertPass(result)
            self.assertEqual(self.state(loop)["idle"], k)
        pid = self.let_through(loop, 6, 100)
        reason = "6 wake-ups in a row without progress"
        notice = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)]), 100))
        self.assertTrue(notice.startswith(end_notice_head(loop, reason)), notice)
        self.assertEqual(self.assertWakeBlocked(self.hook(self.wake(A, loop), 100)), b_ended(loop, reason, [J1]))

    def test_progress_in_the_notes_or_a_watched_path_resets_the_count(self):
        """TEST-043: a change of the notes or of a watched path, also between wake-ups, is progress (idle 0); a
        change inside .git/objects only is not (N4); the person's turns and continuations are never judged."""
        git = os.path.join(self.repo, ".git")
        os.makedirs(os.path.join(git, "objects", "ab"))
        os.makedirs(os.path.join(git, "refs", "heads"))
        write(os.path.join(git, "objects", "ab", "cdef01"), "blob\n")
        write(os.path.join(git, "refs", "heads", "main"), "1111\n")
        loop = self.started_with_job(A, J1, max_wakes=100)

        def persons_turn():   # a person's turn in between: never judged
            pid = self.pid()
            self.assertPass(self.hook(self.prompt(A, "How is it going?", pid), 100))
            self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 100))

        steps = [
            ("nothing changed", None, 1),
            ("a person's turn, nothing changed", persons_turn, 2),
            ("a watched file changed", lambda: append(os.path.join(self.repo, "file.txt"), "two\n"), 0),
            ("nothing changed", None, 1),
            ("a new file in a watched folder", lambda: write(os.path.join(self.repo, "new.txt"), "x\n"), 0),
            ("the notes changed between wake-ups", lambda: append(self.notes, "Waiting on CI.\n"), 0),
            ("only git's object store changed",
             lambda: write(os.path.join(git, "objects", "ab", "cdef02"), "blob 2\n"), 1),
            ("a ref changed", lambda: write(os.path.join(git, "refs", "heads", "main"), "222222\n"), 0),
            ("a file removed", lambda: os.remove(os.path.join(self.repo, "new.txt")), 0),
        ]
        for k, (case, change, idle) in enumerate(steps, 1):
            with self.subTest(case, k=k):
                if change:
                    change()
                _pid, result = self.woken_turn(loop, k, 100)
                self.assertPass(result)
                self.assertEqual(self.state(loop)["idle"], idle)


class ContinuationTest(LoopTestCase):

    def test_a_wake_up_turn_continues_while_the_notes_move_at_most_twenty_times(self):
        """TEST-044: a continuation only in the wake-up's turn (prompt_id), only after the notes changed (not a
        watched path), at most STOP_CAP = 20 per wake-up."""
        loop = self.started_with_job(A, J1, max_wakes=10)

        pid = self.let_through(loop, 1, 10)
        append(self.notes, "Step 1 done.\n")
        reason = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)]), 10))
        self.assertTrue(reason.startswith(CONTINUATION_HEAD), reason)
        for part in (self.notes, "end --reason delivered", J1):
            self.assertIn(part, reason)
        self.assertEqual(self.state(loop)["stop_blocks"], 1)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)], active=True), 10), "no change, yet continued")

        pid = self.let_through(loop, 2, 10)
        self.assertEqual(self.state(loop)["stop_blocks"], 0, "a new wake-up starts its own count")
        for n in range(1, 21):
            append(self.notes, "Step %d.\n" % n)
            result = self.hook(self.stop(A, pid, [(J1, loop)], active=n > 1), 10)
            self.assertTrue(self.assertBlocked(result).startswith(CONTINUATION_HEAD), n)
        append(self.notes, "Step 21.\n")
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)], active=True), 10), "more than 20 continuations")
        self.assertEqual(self.state(loop)["stop_blocks"], 20)

        pid = self.let_through(loop, 3, 10)
        append(os.path.join(self.repo, "file.txt"), "changed by a subagent\n")
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 10), "a watched path made the turn continue")

        pid = self.pid()   # the person's turn
        self.assertPass(self.hook(self.prompt(A, "Please also update the README.", pid), 10))
        append(self.notes, "README updated.\n")
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 10), "the person's turn was continued")


class EndNoticeTest(LoopTestCase):

    def test_the_end_notice_needs_the_loops_job_in_the_stop(self):
        """TEST-045: the end notice only while session_crons lists a job of the loop; an end by `end` in the
        wake-up's turn with the job still listed gets it too."""
        loop = self.started_with_job(A, J1)
        self.woken_turn(loop, 1, 2)
        pid = self.let_through(loop, 2, 2)
        self.assertPass(self.hook(self.stop(A, pid, crons=[cron("aa11bb22", prompt="Nightly report")])))
        state = self.state(loop)
        self.assertEqual(state["ended"]["reason"], "2 wake-ups used")
        self.assertFalse(state["end_notice"])

        self.new_home()
        loop = self.started_with_job(A, J1, max_wakes=5)
        pid = self.let_through(loop, 1, 5)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        notice = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)]), 5))
        self.assertTrue(notice.startswith(end_notice_head(loop, "delivered")), notice)
        self.assertPass(self.hook(self.stop(A, pid, crons=[], active=True), 5))


class JobRequestTest(LoopTestCase):
    """QD13: a turn in which Claude started a loop must end with that loop's job; it is asked once."""

    def test_a_turn_that_started_a_loop_without_its_job_is_asked_once(self):
        """TEST-046: J-CREATE (exact) at the Stop of start's turn without the loop's job; never twice per loop."""
        cases = {
            "no jobs": [],
            "only unmarked jobs": [cron("aa11bb22", prompt="Nightly report")],
            "another loop's job": [cron(J3, NO_STATE_LOOP)],
            "a marked job that names no loop": [cron(J2, prompt="[loop-to-delivery] Wake-up")],
        }
        for case, crons in cases.items():
            with self.subTest(case):
                self.new_home()
                loop = self.start(A)
                pid = self.pid()
                self.assertEqual(self.assertBlocked(self.hook(self.stop(A, pid, crons=crons))), j_create(loop))
                self.assertTrue(self.state(loop)["job_asked"])
                self.assertPass(self.hook(self.stop(A, pid, crons=crons, active=True)))
                self.assertPass(self.hook(self.stop(A, self.pid(), crons=crons)))

    def test_no_job_request_when_the_job_exists_is_unknown_or_the_loop_ended(self):
        """TEST-047: no J-CREATE with the job listed, without session_crons, or after `end`; a new loop after an
        end gets its own single request; start again while active keeps job_asked (G0 run 3 residual)."""
        loop = self.start(A)
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop)])))
        self.assertFalse(self.state(loop)["job_asked"])

        self.new_home()
        loop = self.start(A)
        self.assertPass(self.hook(self.stop(A, self.pid(), crons=DROP)))
        self.assertFalse(self.state(loop)["job_asked"])

        self.new_home()
        loop = self.start(A)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        self.assertPass(self.hook(self.stop(A, self.pid(), crons=[])))
        self.assertFalse(self.state(loop)["job_asked"])

        self.assertPass(self.hook(self.prompt(A, "One more thing, please.")))
        second = self.start(A)
        self.assertNotEqual(second, loop)
        self.assertEqual(self.assertBlocked(self.hook(self.stop(A, self.pid(), crons=[]))), j_create(second))
        self.assertEqual(self.start(A), second, "start while active must continue the loop")
        self.assertTrue(self.state(second)["job_asked"], "start again reset job_asked")
        self.assertPass(self.hook(self.stop(A, self.pid(), crons=[])))
