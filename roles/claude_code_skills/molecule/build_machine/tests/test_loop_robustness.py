"""Failures (IF-008 classification, IF-010 rule 8 and write order, FR-046, QD6; G0 N6, N8): a wake-up that cannot
be judged is blocked, every other event passes, nothing half-done is announced, no prompt text leaks."""

import io
import json
import os
import re

from harness import (A, B, DROP, ERROR_TEXT_RE, J1, SECRET, LoopTestCase, cron, event, failing_replace,
                     j_create, job_prompt, write)

# IF-008's trace line; <event> may be empty where the input names none.
TRACE_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00 (?P<event>\S*) ?error (?P<error>.+) line \d+$")
ERRORS_LOG = os.path.join(".local", "state", "loop-to-delivery", "errors.log")


def ends_with(*parts):
    tail = os.sep + os.path.join(*parts)
    return lambda path: path.endswith(tail)


class UnjudgeableWakeUpTest(LoopTestCase):

    def test_an_invalid_session_or_maximum_blocks_a_wake_up(self):
        """TEST-060: a wake-up with an invalid session id or a bad --max-wakes (rule 1, bad argv): B-ERROR with
        IF-008's error text, never let through; only a log is written."""
        loop = self.started_with_job(A, J1)
        hook = ["hook", "--max-wakes", "2"]
        cases = {
            "a session id with a slash": ({"session_id": "../" + A}, hook),
            "a session id of 129 characters": ({"session_id": "a" * 129}, hook),
            "an empty session id": ({"session_id": ""}, hook),
            "a session id that is not a string": ({"session_id": 42}, hook),
            "no session id": ({"session_id": DROP}, hook),
            "--max-wakes 0": ({}, ["hook", "--max-wakes", "0"]),
            "--max-wakes -1": ({}, ["hook", "--max-wakes", "-1"]),
            "--max-wakes 1.5": ({}, ["hook", "--max-wakes", "1.5"]),
            "--max-wakes x": ({}, ["hook", "--max-wakes", "x"]),
            "no --max-wakes": ({}, ["hook"]),
            "an unknown option": ({}, ["hook", "--max-wakes", "2", "--bogus"]),
        }
        logs = {ERRORS_LOG, os.path.join(".local", "state", "loop-to-delivery", "loops", loop, "log")}
        for case, (fields, argv) in cases.items():
            with self.subTest(case):
                before = self.snapshot()
                data = self.wake(A, loop)
                for key, value in fields.items():
                    if value is DROP:
                        data.pop(key)
                    else:
                        data[key] = value
                error = self.assertBError(self.hook(data, argv=argv), loop)
                self.assertRegex(error, ERROR_TEXT_RE)
                after = self.snapshot()
                changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
                self.assertLessEqual(changed, logs, "rule 1 wrote more than a log")
        self.assertEqual(self.state(loop)["wakes"], 0)
        self.let_through(loop, 1, 2)


class WriteOrderTest(LoopTestCase):
    """N8: the write that commits an outcome comes last before stdout; a failed write announces nothing."""

    def test_a_failed_write_while_letting_through_blocks_and_counts_nothing(self):
        """TEST-061: the record's write fails (record first) or state.json's (last): B-ERROR, wakes unchanged on disk;
        the next fire is judged again and let through as wake-up 1."""
        loop = self.started_with_job(A, J1)
        os.remove(self.path("sessions", A + ".json"))   # so rule 7 must write the record (loop = L)
        state_before = self.state_bytes(loop)
        with failing_replace(ends_with("sessions", A + ".json")):
            error = self.assertBError(self.hook(self.wake(A, loop)), loop)
        self.assertRegex(error, ERROR_TEXT_RE)
        self.assertTrue(error.startswith("write record: "), error)
        self.assertEqual(self.state_bytes(loop), state_before, "state.json was written before the record")
        self.assertIsNone(self.ended(loop), "a failed write ended the loop")

        with failing_replace(ends_with("loops", loop, "state.json")):
            error = self.assertBError(self.hook(self.wake(A, loop)), loop)
        self.assertTrue(error.startswith("write state: "), error)
        self.assertEqual(self.state(loop)["wakes"], 0, "a blocked wake-up was counted")
        self.let_through(loop, 1, 2)

    def test_a_failed_write_announces_no_job_request_notice_or_end(self):
        """TEST-062: J-CREATE, the removal notice and the end notice are printed only after their state is saved:
        a failed write passes the event (exit 1, no stdout), and the next event asks again."""
        loop = self.start(A)
        pid = self.pid()
        with failing_replace(ends_with("loops", loop, "state.json")):
            self.assertFailOpen(self.hook(self.stop(A, pid, crons=[])))
        self.assertFalse(self.state(loop)["job_asked"], "job_asked saved although the write failed")
        self.assertEqual(self.assertBlocked(self.hook(self.stop(A, pid, crons=[], active=True))), j_create(loop))

        self.new_home()
        loop = self.started_with_job(A, J1)
        self.assertEqual(self.cli("stop").rc, 0)
        with failing_replace(ends_with("sessions", A + ".json")):
            self.assertFailOpen(self.hook(self.prompt(A, "Hello")))
        self.assertNotice(self.hook(self.prompt(A, "Hello")))

        self.new_home()
        loop = self.started_with_job(A, J1)
        self.woken_turn(loop, 1, 2)
        pid = self.let_through(loop, 2, 2)
        with failing_replace(ends_with("loops", loop, "state.json")):
            self.assertFailOpen(self.hook(self.stop(A, pid, [(J1, loop)])))
        self.assertFalse(self.state(loop)["end_notice"])
        notice = self.assertBlocked(self.hook(self.stop(A, pid, [(J1, loop)], active=True)))
        self.assertTrue(notice.startswith("loop-to-delivery: loop %s has ended: " % loop), notice)

    def test_start_announces_no_job_when_its_writes_fail(self):
        """TEST-063: start writes the new loop's state.json, then the record; either failing: exit 2, no CronCreate
        line, and no record pointing at a loop without state."""
        with failing_replace(ends_with("state.json")):
            result = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(result.rc, 2, result)
        self.assertNotIn("CronCreate", result.out)
        record = self.record(A)
        self.assertTrue(record is None or record["loop"] is None, record)

        with failing_replace(ends_with("sessions", A + ".json")):
            result = self.main(["start", "--session", A, "--notes", self.notes], environ={"HOME": self.home})
        self.assertEqual(result.rc, 2, result)
        self.assertNotIn("CronCreate", result.out)
        record = self.record(A)
        self.assertTrue(record is None or record["loop"] is None, record)
        self.start(A)


class FailOpenTest(LoopTestCase):
    """FR-046, QD6: every event that is not a wake-up passes on a failure, with a trace; a wake-up is blocked."""

    def traces(self, loop=None):
        """The trace lines of errors.log and of the loop's log, per file (both logs are append-only, IF-009)."""
        logs = {"errors.log": self.log()}
        if loop:
            logs["loop log"] = self.log(loop)
        return {name: [line for line in text.splitlines() if TRACE_RE.match(line)] for name, text in logs.items()}

    def assertTraced(self, before, event_name, loop=None):
        """The event under test added exactly one trace line (IF-008: in the loop's log or in errors.log), naming
        that event and an IF-008 error text; lines that earlier events wrote are not judged."""
        after = self.traces(loop)
        added = [line for name, lines in after.items() for line in lines[len(before.get(name, [])):]]
        self.assertEqual(len(added), 1, "%s should add one trace line, added: %r" % (event_name, added))
        match = TRACE_RE.match(added[0])
        if event_name is not None:
            self.assertEqual(match.group("event"), event_name)
        self.assertRegex(match.group("error"), ERROR_TEXT_RE)

    def test_an_unreadable_record_passes_other_events_and_blocks_a_wake_up(self):
        """TEST-064: the conversation's record does not parse: its prompt, Stop and StopFailure pass (exit 1, one
        stderr line, a trace of their own); its wake-up is blocked and not counted."""
        loop = self.started_with_job(A, J1)
        pid = self.let_through(loop, 1, 2)
        for corrupt in ("{not json", "[]", json.dumps({"version": 1, "session_id": A, "loop": 7, "jobs": "x"})):
            with self.subTest(corrupt):
                write(self.path("sessions", A + ".json"), corrupt)
                for name, data in (("UserPromptSubmit", self.prompt(A, "Hello")),
                                   ("Stop", self.stop(A, pid, [(J1, loop)])),
                                   ("StopFailure", self.failure(A, pid, "rate_limit"))):
                    before = self.traces(loop)
                    result = self.hook(data)
                    self.assertFailOpen(result)
                    self.assertTraced(before, name, loop)
                self.assertBlocked(self.hook(self.wake(A, loop)))
                self.assertEqual(self.state(loop)["wakes"], 1)

    def test_input_that_is_not_a_json_object_passes(self):
        """TEST-065: stdin that is not a JSON object: exit 1, no stdout, a trace each; an object of another or no
        event passes with exit 0 and writes nothing."""
        for text in ("this is not JSON", "", "[]", "42", "null", '"[auto loop-to-delivery 0123abcd] Wake-up"'):
            with self.subTest(text):
                before = self.traces()
                result = self.hook(text)
                self.assertFailOpen(result)
                self.assertTraced(before, None)   # no event name can be read from such input
        before = self.snapshot()
        for data in ({"session_id": A}, event("session-start"),
                     dict(event("user-prompt-submit"), hook_event_name="PreToolUse", prompt=job_prompt("0123abcd"))):
            with self.subTest(data.get("hook_event_name")):
                self.assertPass(self.hook(data))
        self.assertEqual(self.snapshot(), before)

    def test_a_block_that_cannot_be_written_exits_1(self):
        """TEST-065b: only a failure to write a wake-up's block to stdout ends in exit 1 (never 2)."""
        class BrokenStdout(io.StringIO):
            def write(self, text):
                raise OSError(32, "Broken pipe")

        data = json.dumps(self.wake(B, "0123abcd"))
        try:
            rc = self.prog.main(["hook", "--max-wakes", "2"], io.StringIO(data), BrokenStdout(), io.StringIO(),
                                {"HOME": self.home}, self.now)
        except SystemExit as exit_:
            rc = exit_.code
        self.assertEqual(rc, 1)


class NoPromptTextTest(LoopTestCase):
    """N6, CON-006: reasons, output, logs and files never hold prompt text beyond the marker and the loop id."""

    def assertClean(self, *results):
        for result in results:
            self.assertNotIn(SECRET, result.out)
            self.assertNotIn(SECRET, result.err)
        self.assertNotIn(SECRET, self.all_text(), "prompt text reached a file below the state root")

    def test_no_prompt_text_in_reasons_logs_or_files(self):
        """TEST-066: a wake-up with secret-like text after the marker, judged let through, with unreadable state,
        with forced errors (also exceptions whose message holds it) and with wrongly typed fields; the person's
        prompts, Stops and StopFailures carrying it."""
        loop = self.started_with_job(A, J1, max_wakes=5)
        secret_wake = job_prompt(loop) + " " + SECRET
        results = []

        pid = self.pid()
        results.append(self.hook(self.prompt(A, secret_wake, pid), 5))
        self.assertContext(results[-1], loop, 1, 5)
        stop = self.stop(A, pid, crons=[cron(J1, loop), cron("aa11bb22", prompt="Report " + SECRET)])
        stop["last_assistant_message"] = SECRET
        results.append(self.hook(stop, 5))
        results.append(self.hook(dict(self.failure(A, pid), error=SECRET), 5))
        results.append(self.hook(self.prompt(A, "Please use " + SECRET), 5))

        # Exceptions whose message repeats the secret (an OSError's strerror is the system's, IF-008 may show it).
        for error in (ValueError(SECRET), KeyError(SECRET), TypeError(SECRET)):
            with self.subTest(type(error).__name__):
                with failing_replace(ends_with("loops", loop, "state.json"), error):
                    woken = self.hook(self.prompt(A, secret_wake), 5)
                    other = self.hook(self.prompt(A, "Please use " + SECRET), 6)   # max changed: a state write
                results += [woken, other]
                self.assertEqual(self.assertBError(woken, loop), "write state: " + type(error).__name__)
                self.assertFailOpen(other)

        for fields in ({"prompt_id": [SECRET]}, {"session_id": [SECRET]}, {"session_crons": {"x": SECRET}}):
            with self.subTest(fields=list(fields)):
                data = self.prompt(A, secret_wake)
                data.update(fields)
                results.append(self.hook(data, 5))
                stop = self.stop(A, self.pid(), [(J1, loop)])
                stop.update(fields)
                results.append(self.hook(stop, 5))

        write(self.path("loops", loop, "state.json"), "{not json")
        result = self.hook(self.prompt(A, secret_wake), 5)
        self.assertBlocked(result)
        results.append(result)
        results.append(self.hook(self.prompt(A, "And " + SECRET), 5))
        self.assertClean(*results)
        self.assertEqual(self.cli("status").out.count(SECRET), 0)
