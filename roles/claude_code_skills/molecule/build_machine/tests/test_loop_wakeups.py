"""Wake-ups and prompts (IF-010 UserPromptSubmit, Stop steps 4-5): who passes, who is blocked, what Claude is told."""

import json
import os
from unittest import mock

from harness import (A, B, C, ERROR_TEXT_RE, ITEM_NO_LOOP, J1, J2, J3, NO_STATE_LOOP, DROP, B_NONE, LoopTestCase,
                     b_ended, b_missing, b_other, b_unreadable_re, cron, event, item_job, item_loop, job_prompt,
                     recorded, removal_notice, write)


class LetThroughTest(LoopTestCase):

    def test_a_wake_up_of_the_conversations_own_loop_passes_and_is_counted(self):
        """TEST-020: the owner's wake-up gets the context "wake-up k of N of loop L" and counts (AC-041)."""
        loop = self.started_with_job(A, J1)
        pid = self.pid()
        result = self.hook(self.wake(A, loop, pid), 2)
        context = self.assertContext(result, loop, 1, 2)
        self.assertIn(self.notes, context)
        self.assertIn("2026-10-27", context, "the context does not give the deadline's date")
        self.assertEqual(result.err, "")
        state = self.state(loop)
        self.assertEqual((state["wakes"], state["max"], state["wake_prompt_id"], state["idle_counted"],
                          state["failed"], state["stop_blocks"]), (1, 2, pid, False, False, 0))
        self.assertEqual(self.record_of(A)["loop"], loop)
        self.assertIsNone(self.ended(loop))

        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)])))
        self.let_through(loop, 2, 2)
        self.assertEqual(self.state(loop)["wakes"], 2)

    def test_a_marker_after_white_space_is_still_a_wake_up(self):
        """TEST-021: the prompt is classified after lstrip()."""
        loop = self.started_with_job(A, J1)
        result = self.hook(self.prompt(A, " \n\t" + job_prompt(loop)))
        self.assertContext(result, loop, 1, 2)

    def test_a_loop_with_several_jobs_asks_to_delete_all_but_one(self):
        """TEST-022: more than one wake-up job of the loop: the context says to delete all but one."""
        loop = self.start(A)
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop), (J2, loop)])))
        self.assertEqual(self.state(loop)["jobs"], [J1, J2])
        context = self.assertContext(self.hook(self.wake(A, loop)), loop, 1, 2)
        # The let-through text is not marked exact (IF-010): its key parts.
        for part in ("This loop has 2 wake-up jobs", J1, J2, "delete all but one with CronDelete"):
            self.assertIn(part, context)


class PassTest(LoopTestCase):

    def test_conversations_without_a_loop_pass_untouched_and_get_no_file(self):
        """TEST-023: prompts that are not wake-ups and every event of a conversation without a record pass, writing nothing."""
        loop = self.started_with_job(A, J1)
        before = self.snapshot()
        events = {
            "a person's prompt": self.prompt(C, "Fix the parser, please."),
            "the marker inside a prompt": self.prompt(C, "Look at [auto loop-to-delivery %s] in the notes." % loop),
            "a prompt that is not a string": self.prompt(C, None),
            "a Stop with another job": self.stop(C, self.pid(), crons=[cron("aa11bb22", prompt="Nightly report")]),
            "a Stop without session_crons": self.stop(C, self.pid(), crons=DROP),
            "a StopFailure": self.failure(C, self.pid()),
            "SessionStart": event("session-start", session_id=C),
            "SessionEnd": event("session-end", session_id=C),
        }
        for case, data in events.items():
            with self.subTest(case):
                self.assertPass(self.hook(data))
                self.assertEqual(self.snapshot(), before, "a file was written or changed")
        self.assertIsNone(self.record(C))
        # The owner's ordinary prompt while its loop is active: no context.
        self.assertPass(self.hook(self.prompt(A, "What is the status?")))

    def test_a_prompt_with_the_old_marker_is_not_a_wake_up(self):
        """TEST-087: QD18: [loop-to-delivery <id>] (without auto) is unmarked: any session's prompt passes untouched,
        is not blocked and counts no wake-up."""
        loop = self.started_with_job(A, J1)
        old = job_prompt(loop).replace("[auto loop-to-delivery", "[loop-to-delivery", 1)
        self.assertTrue(old.startswith("[loop-to-delivery %s]" % loop), old)
        before = self.snapshot()
        for case, session in (("the loop's own conversation", A), ("another conversation", C)):
            with self.subTest(case):
                self.assertPass(self.hook(self.prompt(session, old)))
                self.assertEqual(self.snapshot(), before, "a file was written or changed")
        self.assertEqual(self.state(loop)["wakes"], 0)
        self.assertIsNone(self.ended(loop))
        self.assertIsNone(self.record(C))

    def test_subagents_are_untouched(self):
        """TEST-024: any input with agent_id passes, writes nothing and ends nothing (FR-044, FR-047)."""
        loop = self.started_with_job(A, J1)
        before = self.snapshot()
        marked = self.wake(A, loop)
        marked.update(agent_id="a6a6426aff7977e1e", agent_type="tester")
        stop_elsewhere = self.stop(B, self.pid(), [(J1, loop)])
        stop_elsewhere.update(agent_id="a6a6426aff7977e1e", agent_type="tester")
        events = {
            "a subagent's marked prompt": marked,
            "SubagentStop as recorded": recorded("subagent-stop"),
            "SubagentStop listing the job": event("subagent-stop", session_id=A, session_crons=[cron(J1, loop)]),
            "a subagent's Stop elsewhere listing the job": stop_elsewhere,
        }
        for case, data in events.items():
            with self.subTest(case):
                self.assertPass(self.hook(data))
                self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.ended(loop))


class BlockedTest(LoopTestCase):

    def test_a_wake_up_that_names_no_loop_is_blocked(self):
        """TEST-025: a marked prompt without a well-formed loop id: B-NONE, recorded once, then the removal notice."""
        prompts = ["[auto loop-to-delivery] Wake-up: continue.",
                   "[auto loop-to-delivery 0123ABCD] Wake-up: continue.",
                   "[auto loop-to-delivery 0123abcd1] Wake-up: continue.",
                   "[auto loop-to-delivery"]
        for text in prompts:
            with self.subTest(text):
                reason = self.assertWakeBlocked(self.hook(self.prompt(C, text)))
                self.assertEqual(reason, B_NONE)
        jobs = self.record_of(C)["jobs"]
        self.assertEqual([(entry["id"], entry["loop"]) for entry in jobs], [(None, None)])
        self.assertIsNone(self.record_of(C)["loop"])
        notice = self.assertNotice(self.hook(self.prompt(C, "Hello")))
        self.assertEqual(notice, removal_notice(ITEM_NO_LOOP))

    def test_a_wake_up_of_a_loop_without_state_is_blocked(self):
        """TEST-026: B-MISSING; the job is recorded; the next prompt there gets the removal notice."""
        reason = self.assertWakeBlocked(self.hook(self.wake(C, NO_STATE_LOOP)))
        self.assertEqual(reason, b_missing(NO_STATE_LOOP))
        jobs = self.record_of(C)["jobs"]
        self.assertEqual([(entry["id"], entry["loop"]) for entry in jobs], [(None, NO_STATE_LOOP)])
        self.assertFalse(os.path.exists(self.path("loops", NO_STATE_LOOP, "state.json")))
        notice = self.assertNotice(self.hook(self.prompt(C, "Hello")))
        self.assertEqual(notice, removal_notice(item_loop(NO_STATE_LOOP, "it has no state")))

    def test_a_wake_up_of_a_loop_with_unreadable_state_is_blocked_and_ends_it(self):
        """TEST-027: B-UNREADABLE with IF-008's error text; ended.json by the hook; the notice follows."""
        def garbage(state):
            return "{not json"

        def wrong_type(state):
            state["wakes"] = "seven"
            return json.dumps(state)

        def naive_time(state):
            state["started"] = "2026-10-20T12:00:00"
            return json.dumps(state)

        def wrong_hours(state):
            state["max_hours"] = "168"
            return json.dumps(state)

        def not_an_object(state):
            return "[]"

        for corrupt in (garbage, wrong_type, naive_time, wrong_hours, not_an_object):
            with self.subTest(corrupt.__name__):
                self.new_home()
                loop = self.started_with_job(A, J1)
                write(self.path("loops", loop, "state.json"), corrupt(self.state(loop)))
                reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
                match = b_unreadable_re(loop).match(reason)
                self.assertIsNotNone(match, reason)
                self.assertRegex(match.group("error"), ERROR_TEXT_RE)
                ended = self.ended(loop)
                self.assertEqual((ended["by"], ended["reason"]), ("hook", "its state could not be read"))
                notice = self.assertNotice(self.hook(self.prompt(A, "Hello")))
                self.assertIn(item_job(J1, loop, "its state could not be read"), notice)


class OtherConversationTest(LoopTestCase):
    """QD5, QD9, QD12: a loop belongs to the conversation that started it."""

    def test_after_clear_the_jobs_fires_are_blocked_and_end_the_loop(self):
        """TEST-028: R1's recorded /clear sequence: B-OTHER in the new conversation, B-ENDED in the old, the notice."""
        seq = recorded("r1-clear")
        names = [(e["hook_event_name"], e["session_id"]) for e in seq]
        self.assertEqual(names[:5], [("SessionStart", A), ("UserPromptSubmit", A), ("Stop", A), ("SessionEnd", A),
                                     ("SessionStart", B)])

        def as_loop(data, loop):
            data = dict(data)
            if data.get("prompt") == "[loop-test] wake up":
                data["prompt"] = job_prompt(loop)
            if isinstance(data.get("session_crons"), list):
                data["session_crons"] = [dict(c, prompt=job_prompt(loop)) for c in data["session_crons"]]
            return data

        self.assertPass(self.hook(seq[0]))
        self.assertPass(self.hook(seq[1]))
        self.assertEqual(self.files(), [])
        loop = self.start(A)                              # in the turn of A's prompt
        self.assertPass(self.hook(as_loop(seq[2], loop)))  # its Stop lists the job CronCreate made
        self.assertEqual(self.state(loop)["jobs"], [J1])
        self.assertPass(self.hook(seq[3]))               # /clear: SessionEnd of A ...
        self.assertPass(self.hook(seq[4]))               # ... SessionStart of B
        state_before = self.state_bytes(loop)

        fires = [e for e in seq[5:] if e["hook_event_name"] == "UserPromptSubmit"]
        self.assertEqual(len(fires), 3)
        first_end = None
        for fire in fires:   # a blocked fire runs no turn, so the recorded Stops after them do not happen
            reason = self.assertWakeBlocked(self.hook(as_loop(fire, loop)))
            self.assertEqual(reason, b_other(loop, [J1]))
            ended = self.ended(loop)
            self.assertEqual((ended["by"], ended["reason"]), ("hook", "a wake-up arrived in another conversation"))
            first_end = first_end or ended
            self.assertEqual(ended, first_end, "a later fire replaced the first end")
        self.assertEqual(self.state_bytes(loop), state_before, "another conversation wrote the loop's state")
        jobs = self.record_of(B)["jobs"]
        self.assertEqual([(entry["id"], entry["loop"]) for entry in jobs], [(J1, loop)])
        self.assertIsNone(self.record_of(B)["loop"])

        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        self.assertEqual(reason, b_ended(loop, "a wake-up arrived in another conversation", [J1]))

        pid = self.pid()
        notice = self.assertNotice(self.hook(self.prompt(B, "Let us do something else.", pid)))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, "a wake-up arrived in another conversation")))
        self.assertPass(self.hook(self.stop(B, pid, crons=[])))   # Claude deleted the job in that turn
        self.assertPass(self.hook(self.prompt(B, "And now?")))

    def test_a_fork_that_gets_the_job_ends_the_loop_for_the_origin_too(self):
        """TEST-029: QD9: a fork (new session id) whose first Stop lists the job ends the loop; the origin's next
        fire is B-ENDED and its next prompt gets the removal notice."""
        loop = self.started_with_job(A, J1, max_wakes=5)
        _pid, result = self.woken_turn(loop, 1, 5)
        self.assertPass(result)
        self.assertPass(self.hook(event("session-start", session_id=B, source="fork"), 5))
        pid = self.pid()
        self.assertPass(self.hook(self.prompt(B, "Try the other approach here.", pid), 5))
        self.assertPass(self.hook(self.stop(B, pid, [(J1, loop)]), 5))
        cause = "its wake-up job turned up in another conversation"
        self.assertEqual(self.ended(loop)["reason"], cause)

        self.assertEqual(self.assertWakeBlocked(self.hook(self.wake(A, loop), 5)), b_ended(loop, cause, [J1]))
        notice = self.assertNotice(self.hook(self.prompt(A, "Back here: what is the state?"), 5))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, cause)))
        notice = self.assertNotice(self.hook(self.prompt(B, "And here?"), 5))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, cause)))

    def test_a_job_listed_in_another_conversation_ends_its_loop(self):
        """TEST-030: QD12: a Stop elsewhere listing the job ends the loop (no output there); fires then blocked."""
        loop = self.started_with_job(A, J1)          # a Stop in A listing A's own job ends nothing
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop)])))
        self.assertIsNone(self.ended(loop))
        state_before = self.state_bytes(loop)

        self.assertPass(self.hook(self.stop(B, self.pid(), [(J1, loop)])))
        cause = "its wake-up job turned up in another conversation"
        ended = self.ended(loop)
        self.assertEqual((ended["by"], ended["reason"]), ("hook", cause))
        self.assertEqual(self.state_bytes(loop), state_before)

        notice = self.assertNotice(self.hook(self.prompt(B, "Hello")))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, cause)))
        reason = self.assertWakeBlocked(self.hook(self.wake(A, loop)))
        self.assertEqual(reason, b_ended(loop, cause, [J1]))
        reason = self.assertWakeBlocked(self.hook(self.wake(B, loop)))
        self.assertEqual(reason, b_other(loop, [J1]))
        self.assertEqual(self.ended(loop), ended, "the first end's reason must stay")

    def test_a_job_listed_elsewhere_keeps_an_earlier_end_and_ignores_loops_without_state(self):
        """TEST-031: QD12 never replaces an end that has a reason; a job of a loop without state ends nothing."""
        loop = self.started_with_job(A, J1)
        self.assertEqual(self.cli("end", "--reason", "delivered", "--session", A).rc, 0)
        ended = self.ended(loop)
        self.assertPass(self.hook(self.stop(B, self.pid(), [(J1, loop)])))
        self.assertEqual(self.ended(loop), ended)
        self.assertEqual(ended["reason"], "delivered")

        self.assertPass(self.hook(self.stop(C, self.pid(), [(J3, NO_STATE_LOOP)])))
        self.assertFalse(os.path.exists(self.path("loops", NO_STATE_LOOP, "ended.json")))
        notice = self.assertNotice(self.hook(self.prompt(C, "Hello")))
        self.assertEqual(notice, removal_notice(item_job(J3, NO_STATE_LOOP, "it has no state")))


class RemovalNoticeTest(LoopTestCase):
    """QD7, QD10: after an end without Claude's turn, Claude is told at the next prompt that is not a wake-up."""

    def test_the_notice_comes_after_stop_before_any_fire_and_repeats_while_listed(self):
        """TEST-032: stop, then the owner's prompt: the notice (never a block); again while a Stop lists the job."""
        loop = self.started_with_job(A, J1)
        self.assertEqual(self.cli("stop").rc, 0)
        expected = removal_notice(item_job(J1, loop, "stopped by the person"))

        pid = self.pid()
        self.assertEqual(self.assertNotice(self.hook(self.prompt(A, "Hello", pid))), expected)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)])))     # the job is still there
        pid = self.pid()
        self.assertEqual(self.assertNotice(self.hook(self.prompt(A, "Hello again", pid))), expected)
        self.assertPass(self.hook(self.stop(A, pid, crons=[])))          # now it is gone
        self.assertPass(self.hook(self.prompt(A, "Thanks")))

    def test_without_session_crons_a_notice_is_given_once(self):
        """TEST-033: R8: a Stop without session_crons drops the noticed entries, so the notice cannot repeat forever."""
        self.started_with_job(A, J1)
        self.assertEqual(self.cli("stop").rc, 0)
        pid = self.pid()
        self.assertNotice(self.hook(self.prompt(A, "Hello", pid)))
        self.assertPass(self.hook(self.stop(A, pid, crons=DROP)))
        self.assertPass(self.hook(self.prompt(A, "Hello again")))


class WakePathTest(LoopTestCase):

    def test_judging_a_wake_up_never_walks_the_watched_paths(self):
        """TEST-034: the wake-up path reads state and stats the notes only, far from the 30 s timeout (IF-008)."""
        loop = self.started_with_job(A, J1)
        with mock.patch.object(os, "walk", side_effect=AssertionError("walked")), \
                mock.patch.object(os, "scandir", side_effect=AssertionError("scanned")):
            let_through = self.hook(self.wake(A, loop))
            other = self.hook(self.wake(B, loop))
        self.assertContext(let_through, loop, 1, 2)
        self.assertEqual(self.assertWakeBlocked(other), b_other(loop, [J1]))
