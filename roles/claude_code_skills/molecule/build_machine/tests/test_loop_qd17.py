"""QD17: a Stop while a background task runs (`background_tasks` a list with at least one entry) is held: it never
blocks, so no continuation, end notice or job request; everything else in it still happens (IF-010 Stop steps 2,
6b, 6c, 6e; architecture §9 QD17 (a)..(f)). Hooks run with --max-wakes 2 unless a test says otherwise."""

from harness import (A, B, CONTINUATION_HEAD, DROP, J1, J2, LoopTestCase, append, b_ended, end_notice_head,
                     item_job, j_create, removal_notice, stamp)

# A task in flight, in the documented shape [D: hooks.md l.2742-2747].
T = [{"id": "t1", "type": "subagent", "status": "running", "description": "an expert", "agent_type": "architect"}]
# Held: any list with an entry, whatever the entries are. Not held: everything else, as with [].
HELD = (("a subagent running", T), ("an empty entry", [{}]), ("an entry that is not an object", ["x"]))
NOT_HELD = (("empty", []), ("missing", DROP), ("null", None), ("an object", {}), ("a string", "t1"),
            ("a number", 0))

# The task's completion notice, a prompt that is not a wake-up (a new prompt_id).
TASK_DONE = ("<task-notification>\n<task-id>t1</task-id>\n<status>completed</status>\n"
             "<summary>Agent \"an expert\" completed</summary>\n</task-notification>")

MAX_REASON = "2 wake-ups used"


class HeldStopTest(LoopTestCase):

    # The three Stops that block without a task: (a) continuation, (b) J-CREATE, (c) end notice.

    def notes_moved_first_stop(self, tasks, max_wakes=2):
        """A wake-up, its notes changed, its first Stop listing the loop's job; returns (loop, pid, result)."""
        loop = self.started_with_job(A, J1, max_wakes)
        pid = self.let_through(loop, 1, max_wakes)
        append(self.notes, "Step 1 started by an expert.\n")
        return loop, pid, self.hook(self.stop(A, pid, [(J1, loop)], background_tasks=tasks), max_wakes)

    def start_turn_stop(self, tasks):
        """start without a job, then that turn's Stop without one; returns (loop, result)."""
        loop = self.start(A)
        return loop, self.hook(self.stop(A, self.pid(), crons=[], background_tasks=tasks))

    def last_wake_up_stop(self, tasks):
        """Wake-up 1 as usual, then wake-up 2 of 2 and its first Stop listing the loop's job; returns (loop, result)."""
        loop = self.started_with_job(A, J1)
        _pid, result = self.woken_turn(loop, 1, 2)
        self.assertPass(result)
        pid = self.let_through(loop, 2, 2)
        return loop, self.hook(self.stop(A, pid, [(J1, loop)], background_tasks=tasks))

    def test_a_held_first_stop_does_not_continue_but_is_judged(self):
        """TEST-080 (a): notes changed, first Stop held: no stdout, stop_blocks 0 and stop_fp unchanged, judged as
        without a task (idle_counted, check_fp updated, idle 0; idle + 1 when nothing changed); a second Stop of
        that turn with [] continues it, so the hold used up nothing."""
        loop = self.started_with_job(A, J1)
        pid = self.let_through(loop, 1, 2)
        woken = self.state(loop)
        append(self.notes, "Step 1 started by an expert.\n")
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)], background_tasks=T)), "a held Stop printed")
        state = self.state(loop)
        self.assertEqual((state["stop_blocks"], state["stop_fp"]), (0, woken["stop_fp"]), "the hold used up a step")
        self.assertEqual((state["idle_counted"], state["idle"]), (True, 0))
        self.assertNotEqual(state["check_fp"], woken["check_fp"], "the held Stop was not judged")

        reason = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)], active=True)))
        self.assertTrue(reason.startswith(CONTINUATION_HEAD), reason)
        self.assertEqual(self.state(loop)["stop_blocks"], 1)

        self.new_home()
        loop = self.started_with_job(A, J1)
        pid = self.let_through(loop, 1, 2)
        self.assertPass(self.hook(self.stop(A, pid, [(J1, loop)], background_tasks=T)), "a held Stop printed")
        state = self.state(loop)
        self.assertEqual((state["idle_counted"], state["idle"]), (True, 1), "an unchanged held turn was not idle")

    def test_a_held_stop_defers_the_job_request(self):
        """TEST-081 (b): start without a job, that turn's Stop held: no stdout, job_asked false; the next Stop of A
        without a task: J-CREATE, and never again for that loop."""
        loop, result = self.start_turn_stop(T)
        self.assertPass(result, "a held Stop printed")
        self.assertFalse(self.state(loop)["job_asked"], "a held Stop used up the job request")

        report = self.pid()
        self.assertPass(self.hook(self.prompt(A, TASK_DONE, report)))
        self.assertEqual(self.assertBlocked(self.hook(self.stop(A, report, crons=[]))), j_create(loop))
        self.assertTrue(self.state(loop)["job_asked"])
        self.assertPass(self.hook(self.stop(A, report, crons=[], active=True)), "J-CREATE came twice")
        self.assertPass(self.hook(self.stop(A, self.pid(), crons=[])), "J-CREATE came twice")

    def test_an_end_at_a_held_stop_is_recorded_and_the_removal_notice_follows(self):
        """TEST-082 (c): wake-up 2 of 2, its first Stop held: no stdout, ended "2 wake-ups used", end_notice false;
        the next fire: B-ENDED; A's next prompt that is not a wake-up: the removal notice naming the loop's job."""
        loop, result = self.last_wake_up_stop(T)
        self.assertPass(result, "a held Stop printed")
        state = self.state(loop)
        self.assertEqual(state["ended"], {"at": stamp(self.now), "reason": MAX_REASON})
        self.assertFalse(state["end_notice"])

        self.assertEqual(self.assertWakeBlocked(self.hook(self.wake(A, loop))), b_ended(loop, MAX_REASON, [J1]))
        notice = self.assertNotice(self.hook(self.prompt(A, TASK_DONE)))
        self.assertEqual(notice, removal_notice(item_job(J1, loop, MAX_REASON)))

    def test_a_held_stop_still_keeps_the_job_lists_and_ends_a_loop_whose_job_turns_up_here(self):
        """TEST-083 (d): steps 4-5 and state.jobs while held: in A, the jobs listed become the loop's and the
        record's; in B, a Stop listing A's job: ended.json (by hook, QD12's reason), no stdout, B's record lists
        it, the loop's state.json unchanged."""
        loop = self.started_with_job(A, J1)
        self.assertPass(self.hook(self.stop(A, self.pid(), [(J1, loop), (J2, loop)], background_tasks=T)))
        self.assertEqual(self.state(loop)["jobs"], [J1, J2])
        self.assertEqual([(entry["id"], entry["loop"]) for entry in self.record_of(A)["jobs"]],
                         [(J1, loop), (J2, loop)])
        self.assertIsNone(self.ended(loop))

        before = self.state_bytes(loop)
        self.assertPass(self.hook(self.stop(B, self.pid(), [(J1, loop)], background_tasks=T)))
        ended = self.ended(loop)
        self.assertIsNotNone(ended, "a held Stop listing another conversation's job ended nothing")
        self.assertEqual((ended["by"], ended["reason"]), ("hook", "its wake-up job turned up in another conversation"))
        self.assertEqual([(entry["id"], entry["loop"]) for entry in self.record_of(B)["jobs"]], [(J1, loop)])
        self.assertEqual(self.state_bytes(loop), before, "another conversation wrote the loop's state")

    def test_only_a_list_with_an_entry_holds(self):
        """TEST-084 (e): background_tasks [], missing, null, {}, "t1" and 0 are judged as without a task (the
        continuation of (a), J-CREATE of (b), the end notice of (c)); [{}] and ["x"] hold like a running task."""
        for case, tasks in NOT_HELD:
            with self.subTest("not held: " + case):
                self.new_home()
                _loop, _pid, result = self.notes_moved_first_stop(tasks)
                reason = self.assertBlocked(result)
                self.assertTrue(reason.startswith(CONTINUATION_HEAD), reason)

                self.new_home()
                loop, result = self.start_turn_stop(tasks)
                self.assertEqual(self.assertBlocked(result), j_create(loop))

                self.new_home()
                loop, result = self.last_wake_up_stop(tasks)
                notice = self.assertBlocked(result)
                self.assertTrue(notice.startswith(end_notice_head(loop, MAX_REASON)), notice)
                self.assertTrue(self.state(loop)["end_notice"])

        for case, tasks in HELD:
            with self.subTest("held: " + case):
                self.new_home()
                loop, _pid, result = self.notes_moved_first_stop(tasks)
                self.assertPass(result, "continued")
                self.assertEqual(self.state(loop)["stop_blocks"], 0)

                self.new_home()
                loop, result = self.start_turn_stop(tasks)
                self.assertPass(result, "J-CREATE")
                self.assertFalse(self.state(loop)["job_asked"])

                self.new_home()
                loop, result = self.last_wake_up_stop(tasks)
                self.assertPass(result, "end notice")
                state = self.state(loop)
                self.assertEqual((state["ended"]["reason"], state["end_notice"]), (MAX_REASON, False))

    def test_after_the_task_finishes_the_next_wake_up_continues_as_usual(self):
        """TEST-085 (f), --max-wakes 3: after (a)'s held first Stop, the task's completion notice (a prompt that is
        not a wake-up) passes; that turn's Stop with [] and changed notes passes, as it is not the wake-up's turn
        (idle, idle_counted, stop_blocks, stop_fp unchanged); wake-up 2 of 3, notes changed, its first Stop with []:
        the continuation (stop_blocks 1)."""
        loop, _pid, result = self.notes_moved_first_stop(T, max_wakes=3)
        self.assertPass(result, "a held Stop printed")

        report = self.pid()
        self.assertPass(self.hook(self.prompt(A, TASK_DONE, report), 3))
        fields = ("idle", "idle_counted", "stop_blocks", "stop_fp")
        before = {name: self.state(loop)[name] for name in fields}
        append(self.notes, "Read the expert's report.\n")
        self.assertPass(self.hook(self.stop(A, report, [(J1, loop)]), 3), "the report's turn was continued")
        self.assertEqual({name: self.state(loop)[name] for name in fields}, before)

        pid = self.let_through(loop, 2, 3)
        append(self.notes, "Step 2 done.\n")
        reason = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)]), 3))
        self.assertTrue(reason.startswith(CONTINUATION_HEAD), reason)
        self.assertEqual(self.state(loop)["stop_blocks"], 1)
