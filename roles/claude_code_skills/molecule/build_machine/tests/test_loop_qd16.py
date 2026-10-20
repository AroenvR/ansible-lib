"""QD16: end_reason decides every end, recorded or not, and `start` begins a new loop only after a prompt that came
after the end (architecture §9 (a)..(h), G0 N11). Hooks run with --max-wakes 2 unless a test says otherwise."""

import os

from harness import (A, J1, LoopTestCase, b_ended, item_job, removal_notice, stamp, write)


def refusal(loop, why):
    return ("this conversation's loop %s ended (%s) and nobody has asked for more since: do not start another for "
            "the same work; tell the person." % (loop, why))


class UnrecordedEndTest(LoopTestCase):

    def start_refused(self, loop, why):
        result = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(result.rc, 2, result)
        self.assertNotIn("CronCreate", result.out)
        self.assertIn(refusal(loop, why), result.err)

    def assertUnrecordedEnd(self, loop, why):
        """The end holds without being written: status shows it, start refuses (no prompt since the end)."""
        self.assertIsNone(self.state(loop)["ended"], "the end was recorded")
        self.assertIsNone(self.ended(loop))
        status = self.cli("status")
        self.assertEqual(status.rc, 0, status)
        for part in (loop, "ended", why, "not recorded yet"):
            self.assertIn(part, status.out)
        self.start_refused(loop, why)

    def assertNewLoopAfterPrompt(self, loop, why, max_wakes=2):
        """A prompt that is not a wake-up records the end and gets the notice; start then makes a new loop."""
        notice = self.assertNotice(self.hook(self.prompt(A, "What happened?"), max_wakes))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, why)))
        self.assertEqual(self.record_of(A)["prompt_after_end"], loop)
        state = self.state(loop)
        self.assertEqual(state["ended"], {"at": stamp(self.now), "reason": why})
        self.assertEqual(state["max"], max_wakes)
        self.assertIn("end recorded at a prompt", self.log(loop))
        new = self.start(A)
        self.assertNotEqual(new, loop)
        record = self.record(A)
        self.assertEqual((record["loop"], record["prompt_after_end"]), (new, None))
        self.assertIsNone(self.state(new)["max"], "a new loop starts with max null (§9 (h))")
        return new

    def last_wake_up(self, max_wakes=2):
        loop = self.started_with_job(A, J1, max_wakes)
        for k in range(1, max_wakes):
            self.woken_turn(loop, k, max_wakes)
        return loop, self.let_through(loop, max_wakes, max_wakes)

    def test_a_counted_failure_of_the_last_wake_up(self):
        """TEST-070 (a): wake-up 2 of 2 fails with max_output_tokens, no Stop: ended unrecorded; the next prompt
        records it and gets the notice; start then begins a new loop."""
        loop, pid = self.last_wake_up()
        self.assertPass(self.hook(self.failure(A, pid, "max_output_tokens")))
        self.assertUnrecordedEnd(loop, "2 wake-ups used")
        self.assertNewLoopAfterPrompt(loop, "2 wake-ups used")

    def test_an_interrupted_last_wake_up(self):
        """TEST-071 (b): wake-up 2 of 2 let through, then neither Stop nor StopFailure (the person interrupted)."""
        loop, _pid = self.last_wake_up()
        self.assertUnrecordedEnd(loop, "2 wake-ups used")
        self.assertNewLoopAfterPrompt(loop, "2 wake-ups used")

    def test_a_lowered_maximum(self):
        """TEST-072 (c): 3 wake-ups under --max-wakes 5, then a deploy lowers it to 2: the next prompt records the end
        (state.max 2); without that prompt, the next fire is B-ENDED and rule 6 records it."""
        loop = self.started_with_job(A, J1, max_wakes=5)
        for k in (1, 2, 3):
            self.woken_turn(loop, k, 5)
        self.assertNewLoopAfterPrompt(loop, "2 wake-ups used", max_wakes=2)

        self.new_home()
        loop = self.started_with_job(A, J1, max_wakes=5)
        for k in (1, 2, 3):
            self.woken_turn(loop, k, 5)
        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop), 2))
        self.assertEqual(reason, b_ended(loop, "2 wake-ups used", [J1]))
        state = self.state(loop)
        self.assertEqual((state["ended"], state["max"], state["wakes"]),
                         ({"at": stamp(self.now), "reason": "2 wake-ups used"}, 2, 3))

    def test_order_not_time_decides(self):
        """TEST-073 (d): a prompt while the loop is active, then `end`, then `start`, all at the same time: refused."""
        loop = self.started_with_job(A, J1)
        self.assertPass(self.hook(self.prompt(A, "Is it done?")))
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        self.start_refused(loop, "delivered")

    def test_an_end_once_recorded_is_for_good(self):
        """TEST-074 (e): after a prompt recorded the end at the maximum, a raised --max-wakes does not revive it."""
        loop, pid = self.last_wake_up()
        self.assertPass(self.hook(self.failure(A, pid, "max_output_tokens")))
        self.assertNotice(self.hook(self.prompt(A, "What happened?")))
        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop), 5))
        self.assertEqual(reason, b_ended(loop, "2 wake-ups used", [J1]))
        status = self.cli("status")
        self.assertIn("ended", status.out)
        self.assertIn("2 wake-ups used", status.out)
        self.assertNotIn("not recorded yet", status.out)

    def test_the_commands_judge_with_the_stored_maximum(self):
        """TEST-075 (f): in the last wake-up's turn, before its Stop, start refuses and status shows the end
        (state.max); a rate_limit StopFailure of that turn un-counts it: no notice, start continues the loop."""
        loop, pid = self.last_wake_up()
        self.start_refused(loop, "2 wake-ups used")
        status = self.cli("status")
        self.assertIn("ended", status.out)
        self.assertIn("2 wake-ups used", status.out)

        self.assertPass(self.hook(self.failure(A, pid, "rate_limit")))
        self.assertEqual(self.state(loop)["wakes"], 1)
        self.assertPass(self.hook(self.prompt(A, "Still there?")))
        self.assertIsNone(self.record_of(A)["prompt_after_end"])
        result = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(result.rc, 0, result)
        self.assertTrue(result.out.startswith("loop-to-delivery: loop %s is already running" % loop), result.out)

    def test_a_loop_without_readable_state_allows_a_new_loop_after_a_prompt(self):
        """TEST-076 (g): the record's loop has no state.json, or one that does not parse: start refuses; after a
        prompt that is not a wake-up, start makes a new loop."""
        for case, why in (("missing", "it has no state"), ("unreadable", "its state cannot be read")):
            with self.subTest(case):
                self.new_home()
                loop = self.started_with_job(A, J1)
                if case == "missing":
                    os.remove(self.path("loops", loop, "state.json"))
                else:
                    write(self.path("loops", loop, "state.json"), "{not json")
                result = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
                self.assertEqual(result.rc, 2, result)
                self.assertIn(refusal(loop, why), result.err)
                notice = self.assertNotice(self.hook(self.prompt(A, "Start again, please.")))
                self.assertIn(loop, notice)
                self.assertEqual(self.record_of(A)["prompt_after_end"], loop)
                self.assertNotEqual(self.start(A), loop)

    def test_every_hook_write_sets_the_maximum(self):
        """TEST-077 (h): each hook write of state.json stores that hook's --max-wakes; the owner's prompt with a
        changed --max-wakes writes it although nothing else changes, with the same one writes nothing."""
        loop = self.start(A)
        self.assertIsNone(self.state(loop)["max"])
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop)]), 7))
        self.assertEqual(self.state(loop)["max"], 7, "Stop")
        pid = self.let_through(loop, 1, 3)
        self.assertEqual(self.state(loop)["max"], 3, "a wake-up let through")
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)]), 4))
        self.assertEqual(self.state(loop)["max"], 4, "the wake-up's Stop")
        pid = self.let_through(loop, 2, 6)
        self.assertPass(self.hook(self.failure(A, pid, "rate_limit"), 5))
        self.assertEqual((self.state(loop)["max"], self.state(loop)["wakes"]), (5, 1), "StopFailure")

        before = self.state(loop)
        self.assertPass(self.hook(self.prompt(A, "Carry on."), 9))
        after = self.state(loop)
        self.assertEqual(after.pop("max"), 9, "the owner's prompt")
        before.pop("max")
        self.assertEqual(after, before, "the prompt changed more than max")
        unchanged = self.state_bytes(loop)
        self.assertPass(self.hook(self.prompt(A, "Carry on."), 9))
        self.assertEqual(self.state_bytes(loop), unchanged, "a prompt with the same maximum wrote state.json")


class RecordedEndTest(LoopTestCase):

    def test_start_after_an_end_needs_a_prompt_that_is_not_a_wake_up(self):
        """TEST-078: after `end`, start is refused, also after a (blocked) wake-up or a subagent's prompt; after the
        person's prompt it makes a loop with a new id."""
        loop = self.started_with_job(A, J1)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        refused = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(refused.rc, 2, refused)
        self.assertIn(refusal(loop, "delivered"), refused.err)

        self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        subagent = self.prompt(A, "Report from the tester.")
        subagent.update(agent_id="a6a6426aff7977e1e", agent_type="tester")
        self.assertPass(self.hook(subagent))
        again = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(again.rc, 2, "a wake-up or a subagent's prompt let start begin a new loop: %r" % (again,))

        self.assertNotice(self.hook(self.prompt(A, "Thanks. Now the next change, please.")))
        new = self.start(A)
        self.assertNotEqual(new, loop)
        self.assertEqual(self.record_of(A)["loop"], new)
