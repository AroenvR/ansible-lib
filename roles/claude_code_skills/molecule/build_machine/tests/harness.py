"""Shared harness of the unit tests of loop-to-delivery's hook program.

The program is found through LOOP_TO_DELIVERY_PROGRAM (default: the role's own
copy in files/skills/loop-to-delivery/) and imported from that path, so the same
suite runs from a venv and, with read-only mounts, inside Claude Code's image
(`python3 -I -B -m unittest discover -s <tests> -t <tests>`). qa-budget's guard,
which the program asks when a wake-up arrives (--budget-guard), is found through
LOOP_TO_DELIVERY_GUARD (default: claude_code_settings' copy in the repository).
Tests and program meet at main(argv, stdin, stdout, stderr, environ, now), at the
files under $HOME/.local/state/loop-to-delivery/, at the guard's files under
$CLAUDE_CONFIG_DIR/qa-budget/ and at the texts the contract fixes.

Standard library only, Python 3.9 syntax. Every test gets temporary folders of
its own: HOME (the program's state root) apart from the work folder (notes,
watched paths), so the program's own writes never count as progress.
"""

import builtins
import contextlib
import errno
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "inputs")
PROGRAM = os.environ.get("LOOP_TO_DELIVERY_PROGRAM") or os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "files", "skills", "loop-to-delivery", "loop_to_delivery.py"))
GUARD = os.environ.get("LOOP_TO_DELIVERY_GUARD") or os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "..", "claude_code_settings", "files", "qa-budget", "guard.py"))

T0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
MAX_HOURS = 168   # the most a loop may run (a recurring job expires after 7 days), and what the tests' hooks get
DEADLINE = T0 + timedelta(hours=MAX_HOURS)
BUDGET_PREFIX = "qa-budget stopped the loop: "   # IF-101: the reason of a loop the budget ended

# Conversations (session ids) and wake-up job ids, stand-ins for Claude Code's.
A = "aaaaaaaa-1111-4111-8111-111111111111"
B = "bbbbbbbb-2222-4222-8222-222222222222"
C = "cccccccc-3333-4333-8333-333333333333"
J1 = "f95aac81"
J2 = "0d1e2f3a"
J3 = "5b6c7d8e"
NO_STATE_LOOP = "0123abcd"   # a well-formed loop id that no start made

SECRET = "SECRET-7f3c-must-never-be-logged"

NOT_RUN_ERRORS = ("rate_limit", "overloaded", "server_error", "billing_error")
# StopFailure values that keep the wake-up counted (QD14, QD15), with how the log
# names them (IF-008): itself when it matches ^[a-z_]{1,40}$, else "other".
COUNTED_ERRORS = (
    ("max_output_tokens", "max_output_tokens"),
    ("invalid_request", "invalid_request"),
    ("authentication_failed", "authentication_failed"),
    ("unknown", "unknown"),
    ("oauth_org_not_allowed", "oauth_org_not_allowed"),
    ("account_on_hold", "account_on_hold"),
    ("model_not_found", "model_not_found"),
    ("cloud_credential_error", "cloud_credential_error"),
    ("context_window_exceeded", "context_window_exceeded"),   # a value of a later Claude Code
    ("x" * 40, "x" * 40),                                     # the longest value logged as itself
    ("context_window_exceeded_v2", "other"),                  # a later value with a digit
    ("x" * 41, "other"),                                      # one character too long
    ("Rate_Limit", "other"),                                  # a case variant of a transient one
    ("rate-limit", "other"),                                  # a hyphen
    ("", "other"),                                            # empty
    ("max_output_tokens\n", "other"),                        # a trailing newline: full match, not "$" (GA-8)
)

JOB_PROMPT = (
    "[auto loop-to-delivery {loop}] Wake-up: continue the work from your notes, as the loop-to-delivery hook's "
    "context says. If no such context came with this prompt, the loop's hooks are not active: delete this "
    "job (CronList, CronDelete) and tell the person.")

DROP = object()   # an event field to leave out

Result = namedtuple("Result", "rc out err")

_loaded = {}


def load_program():
    """The program as a module, or None when it does not exist."""
    if "module" not in _loaded:
        if not os.path.isfile(PROGRAM):
            _loaded["module"] = None
        else:
            spec = importlib.util.spec_from_file_location("loop_to_delivery_under_test", PROGRAM)
            module = importlib.util.module_from_spec(spec)
            # No __pycache__ next to the program, also when the suite runs without -B.
            write_bytecode = sys.dont_write_bytecode
            sys.dont_write_bytecode = True
            try:
                spec.loader.exec_module(module)
            finally:
                sys.dont_write_bytecode = write_bytecode
            _loaded["module"] = module
    return _loaded["module"]


def recorded(name):
    """A hook input as Claude Code 2.1.292 sent it (sanitised), from inputs/<name>.json."""
    with open(os.path.join(INPUTS, name + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def event(name, **fields):
    data = recorded(name)
    for key, value in fields.items():
        if value is DROP:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def job_prompt(loop):
    return JOB_PROMPT.format(loop=loop)


def cron(job, loop=None, prompt=None):
    """An entry of a Stop's session_crons, as CronCreate makes it from start's line."""
    return {"id": job, "schedule": "7,37 * * * *", "recurring": True,
            "prompt": prompt if prompt is not None else job_prompt(loop)}


def create_line(loop):
    return "CronCreate " + json.dumps(
        {"cron": "7,37 * * * *", "prompt": job_prompt(loop), "recurring": True, "durable": False})


def stamp(moment):
    return moment.isoformat(timespec="seconds")


# Exact texts of IF-010 (block reasons, the removal notice, J-CREATE).

def job_part(jobs):
    return " (job %s)" % ", ".join(jobs) if jobs else ""


def b_other(loop, jobs=()):
    return ("loop-to-delivery blocked a wake-up of loop %s%s: that loop belongs to another conversation, so it "
            "has ended. Claude will be asked to delete the job at your next prompt here." % (loop, job_part(jobs)))


def b_ended(loop, why, jobs=()):
    return ("loop-to-delivery blocked a wake-up of loop %s%s: the loop has ended (%s). Claude will be asked to "
            "delete the job at your next prompt here." % (loop, job_part(jobs), why))


def b_missing(loop):
    return ("loop-to-delivery blocked a wake-up of loop %s: there is no state for that loop. Claude will be "
            "asked to delete the job at your next prompt here." % loop)


B_NONE = ("loop-to-delivery blocked a wake-up that names no loop. Claude will be asked to delete its job at "
          "your next prompt here.")


def b_unreadable_re(loop):
    return re.compile(r"^loop-to-delivery blocked a wake-up of loop %s: its state cannot be read \((?P<error>.+)\), "
                      r"so the loop has ended\. Claude will be asked to delete the job at your next prompt here\.$"
                      % loop)


B_ERROR_RE = re.compile(r"^loop-to-delivery blocked a wake-up(?: of loop (?P<loop>[0-9a-f]{8}))?: it could not be "
                        r"judged \((?P<error>.+)\)\. Details: python3 \S*loop_to_delivery\.py status$")

# IF-008 "Error texts": <step>: <Class>[: <strerror> (<filename>)]
ERROR_TEXT_RE = re.compile(r"^(argv|input|read state|read record|write state|write record|write ended|fingerprint|"
                           r"output): [A-Za-z_][A-Za-z0-9_.]*(: .+ \(.+\))?$")


def removal_notice(*items):
    return ("loop-to-delivery: this conversation still has wake-up jobs that must go: %s. Before anything else, "
            "find them with CronList and delete them with CronDelete, then go on with the person's request. Do "
            "not continue or restart those loops' work unless the person asks for it." % "; ".join(items))


def item_job(job, loop, why):
    return "job %s of loop %s (%s)" % (job, loop, why)


def item_loop(loop, why):
    return 'the job of loop %s, whose prompt starts with "[auto loop-to-delivery %s]" (%s)' % (loop, loop, why)


ITEM_NO_LOOP = 'a job whose prompt starts with "[auto loop-to-delivery" but names no loop'


def j_create(loop):
    return ("loop-to-delivery: loop %s was started in this conversation, but no wake-up job of it exists, so it "
            "would never wake up. Create it now, exactly as start printed it: %s If you made a job with another "
            "prompt for this work, delete that one (CronList, CronDelete)." % (loop, create_line(loop)))


# Texts IF-010 does not mark exact: tests check their first sentence and key parts.

def end_notice_head(loop, reason):
    """The end notice's first sentence (IF-010 Stop 6b)."""
    return "loop-to-delivery: loop %s has ended: %s." % (loop, reason)


CONTINUATION_HEAD = "loop-to-delivery: the work is not delivered yet and your notes moved."   # IF-010 Stop 6e


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def append(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def hook_argv(max_wakes=2, max_hours=MAX_HOURS, guard=GUARD):
    """The policy's hook arguments (IF-102): all three required, as the installed command gives them."""
    return ["hook", "--max-wakes", str(max_wakes), "--max-hours", str(max_hours), "--budget-guard", str(guard)]


def load_guard(path=None):
    """qa-budget's guard as a module, loaded like the program loads it (IF-101): not registered, no bytecode,
    sys.path as it was (guard.py puts its own folder first to import ledger)."""
    path = path or GUARD
    spec = importlib.util.spec_from_file_location("qa_budget_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    write_bytecode, saved = sys.dont_write_bytecode, list(sys.path)
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = write_bytecode
        sys.path[:] = saved
    return module


class LoopTestCase(unittest.TestCase):
    """Runs the program's main() with a temporary HOME and an injected clock."""

    maxDiff = None

    def setUp(self):
        self.prog = load_program()
        if self.prog is None:
            self.fail("the hook program does not exist at %s (IF-008: loop_to_delivery.py)" % PROGRAM)
        self.assertTrue(callable(getattr(self.prog, "main", None)), "the program has no main() (IF-008)")
        folder = tempfile.TemporaryDirectory(prefix="loop-to-delivery-test-")
        self.addCleanup(folder.cleanup)
        self.tmp = folder.name
        # The process's own environment too: a program that reads os.environ or "~"
        # instead of main()'s environ must not reach the runner's real state or session.
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        # qa-budget's guard, which the program asks when a wake-up arrives, reads os.environ: this machine's own
        # reading (~/.claude/qa-budget/) must never reach a test, and no QA_BUDGET_* override may change a ceiling.
        for name in [name for name in os.environ if name.startswith("QA_BUDGET_")]:
            del os.environ[name]
        self.claude = os.path.join(self.tmp, "claude")
        os.makedirs(self.claude)
        os.environ["CLAUDE_CONFIG_DIR"] = self.claude
        self.budget_dir = os.path.join(self.claude, "qa-budget")
        self.now = T0
        self.pids = 0
        self.new_home()

    def new_home(self):
        """Fresh HOME, notes and watched folder (also for each subTest that needs a clean account)."""
        base = tempfile.mkdtemp(dir=self.tmp)
        self.home = os.path.join(base, "home")
        self.work = os.path.join(base, "work")
        self.repo = os.path.join(self.work, "repo")
        self.notes = os.path.join(self.work, "notes.md")
        os.makedirs(self.home)
        os.environ["HOME"] = self.home
        os.makedirs(self.repo)
        write(self.notes, "# Goal\nDone when the tests pass.\n")
        write(os.path.join(self.repo, "file.txt"), "one\n")
        self.root = os.path.join(self.home, ".local", "state", "loop-to-delivery")

    # Running the program

    def main(self, argv, stdin="", now=None, environ=None):
        out, err = io.StringIO(), io.StringIO()
        env = {"HOME": self.home} if environ is None else environ
        try:
            rc = self.prog.main(list(argv), io.StringIO(stdin), out, err, env, now or self.now)
        except SystemExit as exit_:
            rc = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
        return Result(rc, out.getvalue(), err.getvalue())

    def hook(self, data, max_wakes=2, now=None, argv=None, max_hours=MAX_HOURS, guard=None):
        if argv is None:
            argv = hook_argv(max_wakes, max_hours, guard or GUARD)
        stdin = data if isinstance(data, str) else json.dumps(data)
        result = self.main(argv, stdin, now=now)
        self.assertNotEqual(result.rc, 2, "hook mode exited 2, which blocks the prompt or the stop: %r" % (result,))
        return result

    def cli(self, *args, now=None, env_session=None):
        environ = {"HOME": self.home}
        if env_session is not None:
            environ["CLAUDE_CODE_SESSION_ID"] = env_session
        return self.main(list(args), now=now, environ=environ)

    def start(self, session=A, notes=None, watch=None, now=None):
        """start for a conversation; returns the loop id read from its last line."""
        argv = ["start", "--notes", notes or self.notes, "--session", session]
        for path in (watch if watch is not None else [self.repo]):
            argv += ["--watch", path]
        result = self.main(argv, now=now, environ={"HOME": self.home})
        self.assertEqual(result.rc, 0, "start failed: %r" % (result,))
        lines = result.out.strip().splitlines()
        self.assertTrue(lines, "start printed nothing: %r" % (result,))
        last = lines[-1]
        self.assertTrue(last.startswith("CronCreate "), "start's last line is not the CronCreate line: %r" % last)
        prompt = json.loads(last[len("CronCreate "):])["prompt"]
        match = re.match(r"^\[auto loop-to-delivery ([0-9a-f]{8})\]", prompt)
        self.assertIsNotNone(match, "start's job prompt names no loop: %r" % prompt)
        return match.group(1)

    # Events

    def pid(self):
        self.pids += 1
        return "00000000-0000-4000-8000-%012d" % self.pids

    def prompt(self, session=A, text="Please go on with the change.", pid=None, **fields):
        return event("user-prompt-submit", session_id=session, prompt_id=pid or self.pid(), prompt=text, **fields)

    def wake(self, session, loop, pid=None, suffix=""):
        return self.prompt(session, job_prompt(loop) + suffix, pid)

    def stop(self, session, pid, jobs=(), crons=None, active=False, **fields):
        """A Stop; jobs = ((job id, loop id), ...) listed in session_crons, or crons given as is (DROP: none)."""
        if crons is None:
            crons = [cron(job, loop) for job, loop in jobs]
        return event("stop", session_id=session, prompt_id=pid, stop_hook_active=active, session_crons=crons,
                     last_assistant_message="Done for now.", **fields)

    def failure(self, session, pid, error="rate_limit"):
        return event("stop-failure", session_id=session, prompt_id=pid, error=error)

    # Sequences

    def let_through(self, loop, k, n, session=A, max_wakes=None, now=None):
        """A wake-up of the loop that must be let through as wake-up k of n; returns its prompt id."""
        pid = self.pid()
        result = self.hook(self.wake(session, loop, pid), max_wakes or n, now=now)
        self.assertContext(result, loop, k, n)
        return pid

    def woken_turn(self, loop, k, n, job=J1, session=A, max_wakes=None, now=None):
        """A wake-up let through, then its turn's first Stop listing the loop's job; returns (pid, Stop's result)."""
        pid = self.let_through(loop, k, n, session, max_wakes, now)
        return pid, self.hook(self.stop(session, pid, [(job, loop)]), max_wakes or n, now=now)

    def started_with_job(self, session=A, job=J1, max_wakes=2):
        """start in the person's turn, then that turn's Stop listing the job CronCreate made."""
        loop = self.start(session)
        result = self.hook(self.stop(session, self.pid(), [(job, loop)]), max_wakes)
        self.assertPass(result)
        return loop

    # qa-budget's reading and guards (IF-101, section 8)

    def reading(self, weekly=10, five_hour=10, moment=None):
        """The status line's latest reading as the guard reads it ($CLAUDE_CONFIG_DIR/qa-budget/rate-limits.json):
        `moment` (default: the injected now) is the reading's time; both windows reset in the future. With the
        guard's defaults 61 weekly is over its ceiling (60), 91 five-hour is over (90), 98 either is the limit."""
        moment = moment or self.now
        os.makedirs(self.budget_dir, mode=0o700, exist_ok=True)
        data = {"time": stamp(moment), "rate_limits": {
            "five_hour": {"used_percentage": five_hour, "resets_at": int((moment + timedelta(hours=3)).timestamp())},
            "seven_day": {"used_percentage": weekly, "resets_at": int((moment + timedelta(days=3)).timestamp())}}}
        write(os.path.join(self.budget_dir, "rate-limits.json"), json.dumps(data))

    def no_reading(self):
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(self.budget_dir, "rate-limits.json"))

    def guard_text(self, moment=None):
        """What the guard's prompt_block(moment) says now (the reading set up): the text a budget end carries."""
        guard = load_guard()
        self.assertTrue(callable(getattr(guard, "prompt_block", None)), "the guard has no prompt_block (IF-101)")
        text = guard.prompt_block(moment or self.now)
        self.assertIsInstance(text, str, "prompt_block gave no reason although the reading is over a ceiling")
        self.assertTrue(text, "prompt_block gave an empty reason")
        return text

    def stub_guard(self, body, name="stub-guard.py"):
        """A guard of a few lines (the body of the module) in a folder of its own; returns its path."""
        folder = tempfile.mkdtemp(dir=self.tmp)
        path = os.path.join(folder, name)
        write(path, textwrap.dedent(body))
        return path

    def recording_guard(self, answer="None"):
        """A stub guard whose prompt_block records each call as a line of JSON in a file and answers with the
        Python expression `answer`; returns (guard path, record path). A call is {"args": [[type name, isoformat,
        utcoffset], ...], "kwargs": [names]}."""
        record = os.path.join(tempfile.mkdtemp(dir=self.tmp), "calls.jsonl")
        path = self.stub_guard("""
            import json

            def prompt_block(*args, **kwargs):
                seen = [[type(a).__name__, a.isoformat() if hasattr(a, "isoformat") else repr(a),
                         str(a.utcoffset()) if hasattr(a, "utcoffset") else None] for a in args]
                with open(%r, "a") as handle:
                    handle.write(json.dumps({"args": seen, "kwargs": sorted(kwargs)}) + "\\n")
                return %s
            """ % (record, answer))
        return path, record

    def calls(self, record):
        """The calls a recording guard saw."""
        if not os.path.exists(record):
            return []
        with open(record, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle.read().splitlines()]

    # Files

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def read_json(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as handle:
            return json.load(handle)

    def state_bytes(self, loop):
        with open(self.path("loops", loop, "state.json"), "rb") as handle:
            return handle.read()

    def record(self, session):
        if not os.path.exists(self.path("sessions", session + ".json")):
            return None
        return self.read_json("sessions", session + ".json")

    def record_of(self, session):
        """The conversation's record, which must exist."""
        record = self.record(session)
        self.assertIsNotNone(record, "no record for conversation %s" % session)
        return record

    def state(self, loop):
        name = self.path("loops", loop, "state.json")
        self.assertTrue(os.path.isfile(name), "no state.json for loop %s" % loop)
        with open(name, encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except ValueError:
                self.fail("state.json of loop %s does not parse" % loop)

    def ended(self, loop):
        if not os.path.exists(self.path("loops", loop, "ended.json")):
            return None
        return self.read_json("loops", loop, "ended.json")

    def log(self, loop=None):
        name = self.path("loops", loop, "log") if loop else self.path("errors.log")
        if not os.path.exists(name):
            return ""
        with open(name, encoding="utf-8") as handle:
            return handle.read()

    def files(self, top=None):
        """Every file below HOME (or top), as paths relative to it."""
        top = top or self.home
        found = []
        for folder, _dirs, names in os.walk(top):
            found += [os.path.relpath(os.path.join(folder, name), top) for name in names]
        return sorted(found)

    def snapshot(self):
        contents = {}
        for name in self.files():
            with open(os.path.join(self.home, name), "rb") as handle:
                contents[name] = handle.read()
        return contents

    def all_text(self):
        """Every file below HOME, decoded, for searches."""
        return "\n".join(data.decode("utf-8", "replace") for data in self.snapshot().values())

    # Assertions

    def assertPass(self, result, msg=None):
        self.assertEqual((result.rc, result.out), (0, ""),
                         "%sexpected a pass (exit 0, no output): %r" % (msg + ": " if msg else "", result))

    def output(self, result):
        self.assertEqual(result.rc, 0, result)
        self.assertTrue(result.out.strip(), "no output: %r" % (result,))
        try:
            data = json.loads(result.out)
        except ValueError:
            self.fail("the output is not one JSON object: %r" % (result.out,))
        self.assertIsInstance(data, dict, result.out)
        return data

    def assertContext(self, result, loop, k, n):
        """A wake-up let through: context naming wake-up k of n of the loop; returns the context."""
        data = self.output(result)
        self.assertNotIn("decision", data, "the wake-up was blocked: %r" % (data,))
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith("loop-to-delivery: wake-up %d of %d of loop %s" % (k, n, loop)), context)
        return context

    def assertNotice(self, result):
        """Context for Claude on a prompt that is not a wake-up (never a block); returns the context."""
        data = self.output(result)
        self.assertNotIn("decision", data, "a prompt that is not a wake-up was blocked: %r" % (data,))
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        return data["hookSpecificOutput"]["additionalContext"]

    def assertBlocked(self, result):
        """A block (wake-up or Stop); returns the reason."""
        data = self.output(result)
        self.assertEqual(data.get("decision"), "block", "not a block: %r" % (data,))
        self.assertNotIn("hookSpecificOutput", data)
        return data["reason"]

    def assertWakeBlocked(self, result):
        """A blocked wake-up: one line for the person; returns it."""
        reason = self.assertBlocked(result)
        self.assertNotIn("\n", reason)
        return reason

    def assertBError(self, result, loop=None):
        reason = self.assertWakeBlocked(result)
        match = B_ERROR_RE.match(reason)
        self.assertIsNotNone(match, "not B-ERROR: %r" % reason)
        if loop is not None and match.group("loop") is not None:
            self.assertEqual(match.group("loop"), loop)
        return match.group("error")

    def assertFailOpen(self, result):
        """A failure in an event that is not a wake-up: exit 1, no stdout, one stderr line."""
        self.assertEqual(result.rc, 1, result)
        self.assertEqual(result.out, "", result)
        lines = result.err.strip().splitlines()
        self.assertEqual(len(lines), 1, "expected one stderr line: %r" % (result.err,))
        self.assertTrue(lines[0].startswith("loop-to-delivery: "), lines[0])


def failing_replace(predicate, error=None):
    """Patches os.replace (IF-009's atomic write) to fail for the destinations the predicate picks."""
    real = os.replace

    def replace(src, dst, *args, **kwargs):
        if predicate(os.fspath(dst)):
            if error is not None:
                raise error
            raise OSError(errno.EIO, "Input/output error", os.fspath(dst))
        return real(src, dst, *args, **kwargs)

    return mock.patch.object(os, "replace", side_effect=replace)


@contextlib.contextmanager
def failing_create(suffix):
    """Every way to create or write a file whose path ends in `suffix` (os.open for writing, open() for writing,
    os.link, os.replace, os.rename) fails with EIO, whatever the program uses: for ended.json, which IF-009 creates
    exclusively."""
    real = {"os.open": os.open, "open": builtins.open, "link": os.link, "replace": os.replace, "rename": os.rename}

    def named(path):
        return isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path).endswith(suffix)

    def failure(path):
        return OSError(errno.EIO, "Input/output error", os.fsdecode(path))

    def os_open(path, flags, *args, **kwargs):
        if named(path) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            raise failure(path)
        return real["os.open"](path, flags, *args, **kwargs)

    def builtin_open(file, mode="r", *args, **kwargs):
        if named(file) and any(letter in mode for letter in "wxa+"):
            raise failure(file)
        return real["open"](file, mode, *args, **kwargs)

    def moving(name):
        def move(src, dst, *args, **kwargs):
            if named(dst):
                raise failure(dst)
            return real[name](src, dst, *args, **kwargs)
        return move

    with mock.patch.object(os, "open", os_open), mock.patch.object(builtins, "open", builtin_open), \
            mock.patch.object(os, "link", moving("link")), mock.patch.object(os, "replace", moving("replace")), \
            mock.patch.object(os, "rename", moving("rename")):
        yield
