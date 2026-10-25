"""loop-to-delivery: keeps long work going across interruptions, within limits.

Claude Code runs this program as a hook (UserPromptSubmit, Stop, StopFailure) with
`hook --max-wakes N`; Claude and the person run its commands (start, end, stop,
status). A loop belongs to the conversation that started it; its wake-up job's
prompt carries the loop's id, and this program lets a wake-up through only for a
loop of that conversation that is within its limits. State lives in
$HOME/.local/state/loop-to-delivery/. Standard library only, Python 3.9.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from datetime import datetime, timedelta, timezone

MARK = "[auto loop-to-delivery"
DAYS = 7
IDLE_MAX = 6
STOP_CAP = 20
NOT_RUN_ERRORS = {"rate_limit", "overloaded", "server_error", "billing_error"}
WALK_CAP = 20000
CRON = "7,37 * * * *"

LOOP_IN_PROMPT = re.compile(r"\[auto loop-to-delivery ([0-9a-f]{8})\]")
LOOP_ID = re.compile(r"[0-9a-f]{8}")
SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
ERROR_VALUE = re.compile(r"[a-z_]{1,40}")
EVENT_NAME = re.compile(r"[A-Za-z]{1,40}")

PROGRAM = os.path.abspath(__file__)

OK, MISSING, UNREADABLE = "ok", "missing", "unreadable"

JOB_PROMPT = ("[auto loop-to-delivery {loop}] Wake-up: continue the work from your notes, as the loop-to-delivery "
              "hook's context says. If no such context came with this prompt, the loop's hooks are not active: "
              "delete this job (CronList, CronDelete) and tell the person.")
STARTED = "loop-to-delivery: loop {loop} started for this conversation ({session}); notes: {notes}."
RUNNING = ("loop-to-delivery: loop {loop} is already running for this conversation; its notes and watched paths are "
           "updated.")
CREATE_ONCE = ('Create its wake-up job once; skip this if CronList already shows a job whose prompt starts with '
               '"[auto loop-to-delivery {loop}]":')
REFUSED = ("this conversation's loop {loop} ended ({why}) and nobody has asked for more since: do not start another "
           "for the same work; tell the person.")

LET_THROUGH = ("loop-to-delivery: wake-up {k} of {max} of loop {loop}; it ends after {idle} in a row without progress, "
               "and on {deadline}. Read your notes, {notes}, and continue the work from them, recording progress "
               "there. If the work can only wait, end your turn without writing anything.")
SEVERAL_JOBS = " This loop has {n} wake-up jobs ({ids}): delete all but one with CronDelete."

B_OTHER = ("loop-to-delivery blocked a wake-up of loop {loop}{job}: that loop belongs to another conversation, so it "
           "has ended. Claude will be asked to delete the job at your next prompt here.")
B_ENDED = ("loop-to-delivery blocked a wake-up of loop {loop}{job}: the loop has ended ({why}). Claude will be asked "
           "to delete the job at your next prompt here.")
B_MISSING = ("loop-to-delivery blocked a wake-up of loop {loop}: there is no state for that loop. Claude will be "
             "asked to delete the job at your next prompt here.")
B_UNREADABLE = ("loop-to-delivery blocked a wake-up of loop {loop}{job}: its state cannot be read ({error}), so the "
                "loop has ended. Claude will be asked to delete the job at your next prompt here.")
B_NONE = ("loop-to-delivery blocked a wake-up that names no loop. Claude will be asked to delete its job at your next "
          "prompt here.")
B_ERROR = ("loop-to-delivery blocked a wake-up{of_loop}: it could not be judged ({error}). Details: python3 "
           "{program} status")

REMOVAL = ("loop-to-delivery: this conversation still has wake-up jobs that must go: {items}. Before anything else, "
           "find them with CronList and delete them with CronDelete, then go on with the person's request. Do not "
           "continue or restart those loops' work unless the person asks for it.")
ITEM_JOB = "job {job} of loop {loop} ({why})"
ITEM_LOOP = 'the job of loop {loop}, whose prompt starts with "[auto loop-to-delivery {loop}]" ({why})'
ITEM_NO_LOOP = 'a job whose prompt starts with "[auto loop-to-delivery" but names no loop'

END_NOTICE = ("loop-to-delivery: loop {loop} has ended: {why}. Before you end this turn: delete its wake-up job {ids} "
              "with CronDelete, write in your notes ({notes}) where the work stands and that the loop ended, and tell "
              "the person what is left. Do not start another loop for this work.")
J_CREATE = ("loop-to-delivery: loop {loop} was started in this conversation, but no wake-up job of it exists, so it "
            "would never wake up. Create it now, exactly as start printed it: {create} If you made a job with another "
            "prompt for this work, delete that one (CronList, CronDelete).")
CONTINUATION = ("loop-to-delivery: the work is not delivered yet and your notes moved. Do the next step from them "
                "({notes}) and record it there. If it can only wait (CI running, an answer from a person), end your "
                "turn without writing: a wake-up comes about every 30 minutes. Once the work's definition of done is "
                "met: `python3 {program} end --reason delivered`, then delete the wake-up job {ids}.")

USAGE = {
    "hook": "hook --max-wakes N",
    "start": "start --notes FILE [--watch PATH]... [--session ID]",
    "end": "end --reason TEXT [--session ID]",
    "stop": "stop",
    "status": "status [--session ID]",
}


def state_defaults(**fields):
    """A loop's state.json fields that have a default, with the given ones."""
    state = {"version": 1, "watch": [], "wakes": 0, "max": None, "idle": 0, "check_fp": "", "stop_fp": "",
             "wake_prompt_id": None, "idle_counted": False, "failed": False, "job_asked": False, "stop_blocks": 0,
             "jobs": [], "ended": None, "end_notice": False}
    state.update(fields)
    return state


# Small helpers

def stamp(moment):
    return moment.isoformat(timespec="seconds")


def parse_time(text):
    """An aware time written by stamp(), or None."""
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.utcoffset() is not None else None


def is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def one_line(text, limit=200):
    return " ".join(str(text).split())[:limit] or "no reason given"


def job_prompt(loop):
    return JOB_PROMPT.format(loop=loop)


def create_line(loop):
    return "CronCreate " + json.dumps({"cron": CRON, "prompt": job_prompt(loop), "recurring": True, "durable": False})


def job_part(jobs):
    """{job} of the block reasons."""
    return " (job %s)" % ", ".join(jobs) if jobs else ""


def job_ids(loop, jobs):
    """The loop's job ids for Claude, or how to find the job when none is known."""
    if jobs:
        return ", ".join(jobs)
    return '(its prompt starts with "[auto loop-to-delivery %s]")' % loop


def loop_in_prompt(prompt):
    match = LOOP_IN_PROMPT.match(prompt.lstrip())
    return match.group(1) if match else None


def is_marked(prompt):
    return isinstance(prompt, str) and prompt.lstrip().startswith(MARK)


def entry_key(job, loop):
    """A job of a conversation's record: by its id, or by its loop when the id is unknown."""
    return job if job is not None else (None, loop)


def is_wake_up(data):
    return (data.get("hook_event_name") == "UserPromptSubmit" and "agent_id" not in data
            and is_marked(data.get("prompt")))


# Failures: texts built from the program's own data only (step, class, an OSError's strerror and filename)

class Failure(Exception):
    def __init__(self, step, cause):
        Exception.__init__(self, step)
        self.step = step
        self.text = "%s: %s" % (step, type(cause).__name__)
        if isinstance(cause, OSError) and cause.strerror and cause.filename:
            self.text += ": %s (%s)" % (cause.strerror, cause.filename)
        self.line = innermost_line(cause.__traceback__)


class UsageError(Exception):
    pass


def innermost_line(trace):
    line = 0
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == __file__ or not line:
            line = trace.tb_lineno
        trace = trace.tb_next
    return line


@contextlib.contextmanager
def step(name):
    try:
        yield
    except Failure:
        raise
    except Exception as cause:
        raise Failure(name, cause) from cause


class Parser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self, add_help=False, allow_abbrev=False)

    def error(self, message):
        raise UsageError()


def parse(command, args):
    parser = Parser()
    if command == "hook":
        parser.add_argument("--max-wakes", type=int, required=True)
    elif command == "start":
        parser.add_argument("--notes", required=True)
        parser.add_argument("--watch", action="append", default=[])
        parser.add_argument("--session")
    elif command == "end":
        parser.add_argument("--reason", required=True)
        parser.add_argument("--session")
    elif command == "status":
        parser.add_argument("--session")
    return parser.parse_args(args)


# State files

def checked_state(data, loop):
    """A loop's state.json with its defaults; ValueError when a field has a wrong type."""
    if not isinstance(data, dict):
        raise ValueError()
    state = state_defaults(loop=loop)
    state.update(data)
    ended = state["ended"]
    good = (state["version"] == 1 and is_count(state["version"]) and state["loop"] == loop
            and matches(SESSION_ID, state.get("session_id"))
            and parse_time(state.get("started")) is not None and parse_time(state.get("deadline")) is not None
            and isinstance(state.get("notes"), str) and os.path.isabs(state["notes"])
            and isinstance(state["watch"], list)
            and all(isinstance(path, str) and os.path.isabs(path) for path in state["watch"])
            and all(is_count(state[name]) for name in ("wakes", "idle", "stop_blocks"))
            and (state["max"] is None or is_count(state["max"]) and state["max"] > 0)
            and isinstance(state["check_fp"], str) and isinstance(state["stop_fp"], str)
            and (state["wake_prompt_id"] is None or isinstance(state["wake_prompt_id"], str))
            and all(isinstance(state[name], bool) for name in ("idle_counted", "failed", "job_asked", "end_notice"))
            and isinstance(state["jobs"], list) and all(matches(JOB_ID, job) for job in state["jobs"])
            and (ended is None or isinstance(ended, dict) and parse_time(ended.get("at")) is not None
                 and isinstance(ended.get("reason"), str)))
    if not good:
        raise ValueError()
    return state


def checked_record(data, session):
    """A conversation's record with its defaults; ValueError when a field has a wrong type."""
    if not isinstance(data, dict):
        raise ValueError()
    record = {"version": 1, "session_id": session, "loop": None, "prompt_after_end": None, "jobs": []}
    record.update(data)
    good = (record["version"] == 1 and is_count(record["version"]) and record["session_id"] == session
            and all(value is None or matches(LOOP_ID, value) for value in (record["loop"], record["prompt_after_end"]))
            and isinstance(record["jobs"], list))
    jobs = []
    for entry in record["jobs"] if good else ():
        good = (isinstance(entry, dict) and (entry.get("id") is None or matches(JOB_ID, entry.get("id")))
                and (entry.get("loop") is None or matches(LOOP_ID, entry.get("loop")))
                and isinstance(entry.get("noticed", False), bool))
        if not good:
            break
        jobs.append({"id": entry.get("id"), "loop": entry.get("loop"), "noticed": entry.get("noticed", False)})
    if not good:
        raise ValueError()
    record["jobs"] = jobs
    return record


def new_record(session):
    return {"version": 1, "session_id": session, "loop": None, "prompt_after_end": None, "jobs": []}


def notes_fingerprint(notes):
    try:
        info = os.stat(notes)
    except FileNotFoundError:
        return "missing"
    return "%d:%d" % (info.st_size, info.st_mtime_ns)


def full_fingerprint(notes, watch):
    """SHA-256 over the notes' and the watched paths' sizes and times (no content read); and the paths whose walk
    reached WALK_CAP."""
    digest = hashlib.sha256(notes_fingerprint(notes).encode())
    capped = []
    for path in watch:
        digest.update(b"\0")
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            digest.update(("%s missing" % path).encode("utf-8", "surrogateescape"))
            continue
        if not stat.S_ISDIR(info.st_mode):
            digest.update(("%s %d %d" % (path, info.st_size, info.st_mtime_ns)).encode("utf-8", "surrogateescape"))
            continue
        count = 0
        for folder, folders, files in os.walk(path):
            if os.path.basename(folder) == ".git" and "objects" in folders:
                folders.remove("objects")   # git's content store: its refs, index and logs stay
            folders.sort()
            for name in folders + sorted(files):
                entry = os.path.join(folder, name)
                try:
                    info = os.lstat(entry)
                except FileNotFoundError:
                    continue
                digest.update(("%s %d %d\n" % (os.path.relpath(entry, path), info.st_size, info.st_mtime_ns))
                              .encode("utf-8", "surrogateescape"))
                count += 1
                if count >= WALK_CAP:
                    break
            if count >= WALK_CAP:
                capped.append(path)
                break
    return digest.hexdigest(), capped


class Store:
    """The files under $HOME/.local/state/loop-to-delivery/ (folders 0700, files 0600)."""

    def __init__(self, home):
        self.home = home

    def path(self, *parts):
        if not isinstance(self.home, str) or not os.path.isabs(self.home):
            raise KeyError("HOME")
        return os.path.join(self.home, ".local", "state", "loop-to-delivery", *parts)

    def folders(self, *parts):
        """Makes the state root and each folder below it, one level at a time, so each gets 0700."""
        os.makedirs(os.path.dirname(self.path()), exist_ok=True)
        for depth in range(len(parts) + 1):
            try:
                os.mkdir(self.path(*parts[:depth]), 0o700)
            except FileExistsError:
                pass

    def read_json(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as handle:
            return json.load(handle)

    def write_json(self, data, *parts):
        """Atomic: a temporary file in the same folder, then os.replace."""
        target = self.path(*parts)
        handle, temporary = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
            os.replace(temporary, target)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temporary)
            raise

    def state(self, loop):
        """(OK, state, None), (MISSING, None, None) or (UNREADABLE, None, error text)."""
        try:
            with step("read state"):
                try:
                    data = self.read_json("loops", loop, "state.json")
                except FileNotFoundError:
                    return MISSING, None, None
                return OK, checked_state(data, loop), None
        except Failure as failure:
            return UNREADABLE, None, failure.text

    def write_state(self, state):
        with step("write state"):
            self.write_json(state, "loops", state["loop"], "state.json")

    def record(self, session):
        with step("read record"):
            try:
                data = self.read_json("sessions", session + ".json")
            except FileNotFoundError:
                return None
            return checked_record(data, session)

    def write_record(self, record):
        with step("write record"):
            self.folders("sessions")
            self.write_json(record, "sessions", record["session_id"] + ".json")

    def ended(self, loop):
        """ended.json's reason, "unreadable" for one that does not parse, or None when there is none."""
        try:
            data = self.read_json("loops", loop, "ended.json")
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return "unreadable"
        if not isinstance(data, dict) or not isinstance(data.get("reason"), str):
            return "unreadable"
        return one_line(data["reason"])

    def ended_at(self, loop):
        with contextlib.suppress(OSError, ValueError, AttributeError):
            return self.read_json("loops", loop, "ended.json").get("at")
        return None

    def end(self, loop, reason, by, now):
        """Creates ended.json once (the first end wins); False when it was there already."""
        with step("write ended"):
            try:
                handle = os.open(self.path("loops", loop, "ended.json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return False
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps({"at": stamp(now), "reason": reason, "by": by}) + "\n")
            return True

    def loops(self):
        try:
            names = os.listdir(self.path("loops"))
        except FileNotFoundError:
            return []
        return sorted(name for name in names if LOOP_ID.fullmatch(name))

    def sessions(self):
        try:
            names = os.listdir(self.path("sessions"))
        except FileNotFoundError:
            return []
        return sorted(name[:-5] for name in names if name.endswith(".json") and SESSION_ID.fullmatch(name[:-5]))

    def append(self, line, loop=None, fallback=False):
        """One line in the loop's log, when its folder exists; else, for a trace (fallback), in errors.log. Best
        effort: a log never changes an outcome."""
        with contextlib.suppress(Exception):
            if loop is not None and os.path.isdir(self.path("loops", loop)):
                target = self.path("loops", loop, "log")
            elif loop is None or fallback:
                self.folders()
                target = self.path("errors.log")
            else:
                return
            handle = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(handle, "a", encoding="utf-8") as stream:
                stream.write(line + "\n")

    def log_text(self, loop=None):
        with contextlib.suppress(OSError):
            with open(self.path("loops", loop, "log") if loop else self.path("errors.log"), encoding="utf-8",
                      errors="replace") as handle:
                return handle.read()
        return ""


# The program

class Program:

    def __init__(self, stdout, stderr, environ, now):
        self.out = stdout
        self.err = stderr
        self.environ = environ
        self.now = now.astimezone(timezone.utc)
        self.store = Store(environ.get("HOME"))
        self.loaded = {}
        self.pending = []
        self.known_loop = None
        self.event = "-"

    # Logs

    def log(self, loop, text):
        self.pending.append((loop, "%s %s" % (stamp(self.now), text)))

    def flush(self):
        for loop, line in self.pending:
            self.store.append(line, loop)
        self.pending = []

    def trace(self, failure):
        """The hook's trace: one line, never input other than the event's name."""
        self.store.append("%s %s error %s line %d" % (stamp(self.now), self.event, failure.text, failure.line),
                          self.known_loop, fallback=True)

    # Judging a loop

    def load(self, loop):
        if loop not in self.loaded:
            self.loaded[loop] = self.store.state(loop)
        return self.loaded[loop]

    def end_reason(self, loop, state, max_wakes):
        """The only place that decides whether a loop has ended (recorded or not)."""
        ended = self.store.ended(loop)
        if ended is not None:
            return ended
        if state is None:
            return None
        if state["ended"] is not None:
            return one_line(state["ended"]["reason"])
        if self.now >= parse_time(state["deadline"]):
            return "%d days passed" % DAYS
        if max_wakes is not None and state["wakes"] >= max_wakes:
            return "%d wake-ups used" % max_wakes
        if state["idle"] >= IDLE_MAX:
            return "%d wake-ups in a row without progress" % IDLE_MAX
        return None

    def own_active(self, loop, session, max_wakes):
        status, state, _error = self.load(loop)
        return (status == OK and state["session_id"] == session
                and self.end_reason(loop, state, max_wakes) is None)

    def why(self, loop, session, max_wakes):
        status, state, _error = self.load(loop)
        reason = self.end_reason(loop, state, max_wakes)
        if reason is not None:
            return reason
        if status == OK and state["session_id"] != session:
            return "it belongs to another conversation"
        return "it has no state" if status == MISSING else "its state cannot be read"

    def end_elsewhere(self, loop, session, cause, max_wakes):
        """hook end: ends another conversation's loop through its ended.json, never its state.json."""
        status, state, _error = self.load(loop)
        if status == UNREADABLE:
            with contextlib.suppress(Failure):
                if self.store.end(loop, "its state could not be read", "hook", self.now):
                    self.store.append("%s ended: its state could not be read" % stamp(self.now), loop)
        elif status == OK and state["session_id"] != session and self.end_reason(loop, state, max_wakes) is None:
            if self.store.end(loop, cause, "hook", self.now):
                self.store.append("%s ended in conversation %s: %s" % (stamp(self.now), session, cause), loop)

    # Output

    def say(self, data):
        with step("output"):
            self.out.write(json.dumps(data) + "\n")
            self.out.flush()
        return 0

    def block(self, reason):
        return self.say({"decision": "block", "reason": reason})

    def context(self, text):
        return self.say({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}})

    def fail_open(self, failure):
        self.trace(failure)
        with contextlib.suppress(Exception):
            self.err.write("loop-to-delivery: %s\n" % failure.text)
        return 1

    # Hook mode

    def hook(self, args, stdin):
        try:
            with step("input"):
                data = json.loads(stdin.read())
                if not isinstance(data, dict):
                    raise TypeError()
        except Failure as failure:
            return self.fail_open(failure)
        name = data.get("hook_event_name")
        self.event = name if matches(EVENT_NAME, name) else "-"
        wake = is_wake_up(data)
        loop = loop_in_prompt(data["prompt"]) if wake else None
        try:
            try:
                with step("argv"):
                    max_wakes = parse("hook", args).max_wakes
                    if max_wakes <= 0:
                        raise ValueError()
                if "agent_id" in data:
                    return 0
                if wake:
                    return self.wake_up(data, loop, max_wakes)
                if name == "UserPromptSubmit":
                    return self.prompt(data, max_wakes)
                if name == "Stop":
                    return self.stop_event(data, max_wakes)
                if name == "StopFailure":
                    return self.stop_failure(data, max_wakes)
                return 0
            except Failure:
                raise
            except Exception as cause:
                raise Failure("input", cause) from cause
        except Failure as failure:
            self.pending = []
            if not wake or failure.step == "output":
                return self.fail_open(failure)
            self.trace(failure)
            try:
                return self.block(B_ERROR.format(of_loop=" of loop %s" % loop if loop else "", error=failure.text,
                                                 program=PROGRAM))
            except Failure as output_failure:
                return self.fail_open(output_failure)

    def session_of(self, data):
        session = data.get("session_id")
        return session if matches(SESSION_ID, session) else None

    def record_job(self, session, loop, state):
        """Adds the job of the blocked wake-up to the conversation's record; a failure leaves the block as it is."""
        try:
            record = self.store.record(session) or new_record(session)
            wanted = [(job, loop) for job in state["jobs"]] if state is not None and state["jobs"] else [(None, loop)]
            changed = False
            for job, owner in wanted:
                if any(entry["id"] == job and (job is not None or entry["loop"] == owner) for entry in record["jobs"]):
                    continue
                record["jobs"].append({"id": job, "loop": owner, "noticed": False})
                changed = True
            if changed:
                self.store.write_record(record)
        except Failure as failure:
            self.trace(failure)

    def wake_up(self, data, loop, max_wakes):
        """UserPromptSubmit, a wake-up: exactly one outcome, let through or blocked."""
        with step("input"):
            session = self.session_of(data)
            if session is None:
                raise ValueError()
        if loop is None:
            self.record_job(session, None, None)
            return self.block(B_NONE)
        self.known_loop = loop
        status, state, error = self.load(loop)
        if status == MISSING:
            self.record_job(session, loop, None)
            return self.block(B_MISSING.format(loop=loop))
        if status == UNREADABLE:
            self.end_elsewhere(loop, session, None, max_wakes)
            self.record_job(session, loop, None)
            return self.block(B_UNREADABLE.format(loop=loop, job="", error=error))
        if state["session_id"] != session:
            self.end_elsewhere(loop, session, "a wake-up arrived in another conversation", max_wakes)
            self.record_job(session, loop, state)
            self.store.append("%s wake-up blocked in conversation %s: the loop belongs to another conversation"
                              % (stamp(self.now), session), loop)
            return self.block(B_OTHER.format(loop=loop, job=job_part(state["jobs"])))
        why = self.end_reason(loop, state, max_wakes)
        if why is not None:
            self.record_job(session, loop, state)
            before = dict(state)
            if state["ended"] is None:
                state["ended"] = {"at": stamp(self.now), "reason": why}
            state["max"] = max_wakes
            if state != before:
                self.store.write_state(state)
            self.log(loop, "wake-up blocked: the loop has ended (%s)" % why)
            self.flush()
            return self.block(B_ENDED.format(loop=loop, job=job_part(state["jobs"]), why=why))
        existing = self.store.record(session)
        record = existing or new_record(session)
        prompt_id = data.get("prompt_id")
        with step("fingerprint"):
            notes = notes_fingerprint(state["notes"])
        state.update(wakes=state["wakes"] + 1, max=max_wakes, idle_counted=False, failed=False, stop_blocks=0,
                     stop_fp=notes, wake_prompt_id=prompt_id if isinstance(prompt_id, str) else None)
        if existing is None or record["loop"] != loop:
            record["loop"] = loop
            self.store.write_record(record)
        self.store.write_state(state)
        self.log(loop, "wake-up %d of %d let through" % (state["wakes"], max_wakes))
        self.flush()
        text = LET_THROUGH.format(k=state["wakes"], max=max_wakes, loop=loop, idle=IDLE_MAX, notes=state["notes"],
                                  deadline=parse_time(state["deadline"]).date().isoformat())
        if len(state["jobs"]) > 1:
            text += SEVERAL_JOBS.format(n=len(state["jobs"]), ids=", ".join(state["jobs"]))
        return self.context(text)

    def prompt(self, data, max_wakes):
        """UserPromptSubmit, not a wake-up: never blocked; context only for the removal notice."""
        session = self.session_of(data)
        if session is None:
            return 0
        record = self.store.record(session)
        if record is None:
            return 0
        loop = record["loop"]
        self.known_loop = loop
        record_before = json.dumps(record, sort_keys=True)
        state = None
        if loop is not None:
            status, state, _error = self.load(loop)
            if status == OK and state["session_id"] == session:
                state_before = dict(state)
                state["max"] = max_wakes
                why = self.end_reason(loop, state, max_wakes)
                if state["ended"] is None and why is not None:
                    state["ended"] = {"at": stamp(self.now), "reason": why}
                    self.log(loop, "end recorded at a prompt (%s)" % why)
                if state == state_before:
                    state = None
            else:
                state = None
            if not self.own_active(loop, session, max_wakes):
                record["prompt_after_end"] = loop
        stale = [entry for entry in record["jobs"]
                 if entry["loop"] is None or not self.own_active(entry["loop"], session, max_wakes)]
        for entry in stale:
            entry["noticed"] = True
        if json.dumps(record, sort_keys=True) != record_before:
            self.store.write_record(record)
        if state is not None:
            self.store.write_state(state)
        if not stale:
            self.flush()
            return 0
        items = []
        for entry in stale:
            if entry["loop"] is None:
                item = ITEM_NO_LOOP
            else:
                template = ITEM_JOB if entry["id"] is not None else ITEM_LOOP
                item = template.format(job=entry["id"], loop=entry["loop"],
                                       why=self.why(entry["loop"], session, max_wakes))
                self.log(entry["loop"], "removal notice in conversation %s" % session)
            if item not in items:
                items.append(item)
        self.flush()
        return self.context(REMOVAL.format(items="; ".join(items)))

    def stop_event(self, data, max_wakes):
        """Stop: jobs, other conversations' loops, idle, end notice, job request, continuation."""
        session = self.session_of(data)
        if session is None:
            return 0
        crons = data.get("session_crons")
        listed = isinstance(crons, list)
        marked = []
        for entry in crons if listed else ():
            if isinstance(entry, dict) and is_marked(entry.get("prompt")):
                job = entry.get("id")
                marked.append((job if matches(JOB_ID, job) else None, loop_in_prompt(entry["prompt"])))
        tasks = data.get("background_tasks")
        held = isinstance(tasks, list) and len(tasks) > 0
        existing = self.store.record(session)
        if existing is None and not marked:
            return 0
        record = existing or new_record(session)
        self.known_loop = record["loop"]
        record_before = json.dumps(existing, sort_keys=True) if existing else None
        if listed:
            noticed = {entry_key(entry["id"], entry["loop"]): entry["noticed"] for entry in record["jobs"]}
            record["jobs"] = [{"id": job, "loop": owner, "noticed": noticed.get(entry_key(job, owner), False)}
                              for job, owner in marked]
        else:
            record["jobs"] = [entry for entry in record["jobs"] if not entry["noticed"]]
        for other in sorted({owner for _job, owner in marked if owner is not None}):
            self.end_elsewhere(other, session, "its wake-up job turned up in another conversation", max_wakes)
        loop = record["loop"]
        output = None
        state = None
        if loop is not None:
            status, state, _error = self.load(loop)
            if status != OK or state["session_id"] != session:
                state = None
        if state is not None:
            state_before = json.dumps(state, sort_keys=True)
            if listed:
                state["jobs"] = [job for job, owner in marked if owner == loop and job is not None]
            prompt_id = data.get("prompt_id")
            wake = isinstance(prompt_id, str) and prompt_id == state["wake_prompt_id"]
            if wake and not state["idle_counted"] and not state["failed"]:
                with step("fingerprint"):
                    check, capped = full_fingerprint(state["notes"], state["watch"])
                self.note_capped(loop, capped)
                state["idle"] = 0 if check != state["check_fp"] else state["idle"] + 1
                state["check_fp"] = check
                state["idle_counted"] = True
            why = self.end_reason(loop, state, max_wakes)
            has_job = any(owner == loop for _job, owner in marked)
            if wake and why is not None:
                if state["ended"] is None:
                    state["ended"] = {"at": stamp(self.now), "reason": why}
                    self.log(loop, "ended: %s" % why)
                if not held and has_job and not state["end_notice"]:
                    state["end_notice"] = True
                    output = END_NOTICE.format(loop=loop, why=why, ids=job_ids(loop, state["jobs"]),
                                               notes=state["notes"])
                    self.log(loop, "end notice")
            elif not held and why is None and listed and not has_job and not state["job_asked"]:
                state["job_asked"] = True
                output = J_CREATE.format(loop=loop, create=create_line(loop))
                self.log(loop, "job requested")
            elif wake and not held and state["stop_blocks"] < STOP_CAP:
                with step("fingerprint"):
                    notes = notes_fingerprint(state["notes"])
                if notes != state["stop_fp"]:
                    state["stop_blocks"] += 1
                    state["stop_fp"] = notes
                    output = CONTINUATION.format(notes=state["notes"], program=PROGRAM,
                                                 ids=job_ids(loop, state["jobs"]))
                    self.log(loop, "continuation %d" % state["stop_blocks"])
            state["max"] = max_wakes
            if json.dumps(state, sort_keys=True) == state_before:
                state = None
        if json.dumps(record, sort_keys=True) != record_before:
            self.store.write_record(record)
        if state is not None:
            self.store.write_state(state)
        self.flush()
        return self.block(output) if output is not None else 0

    def stop_failure(self, data, max_wakes):
        """StopFailure: only a transient failure before the turn's first Stop is un-counted."""
        session = self.session_of(data)
        if session is None:
            return 0
        record = self.store.record(session)
        if record is None or record["loop"] is None:
            return 0
        loop = record["loop"]
        self.known_loop = loop
        status, state, _error = self.load(loop)
        prompt_id = data.get("prompt_id")
        if (status != OK or state["session_id"] != session or not isinstance(prompt_id, str)
                or prompt_id != state["wake_prompt_id"]):
            return 0
        error = data.get("error") if isinstance(data.get("error"), str) else None
        logged = error if matches(ERROR_VALUE, error) else "other"
        k = state["wakes"]
        if state["idle_counted"] or state["failed"]:
            self.log(loop, "wake-up %d failed again (%s), after its turn's first Stop or failure: no change"
                     % (k, logged))
            self.flush()
            return 0
        state.update(failed=True, idle_counted=True, max=max_wakes)
        if error in NOT_RUN_ERRORS:
            state["wakes"] = max(k - 1, 0)
            self.log(loop, "wake %d failed (%s), not counted" % (k, logged))
        else:
            self.log(loop, "wake %d failed (%s), counted" % (k, logged))
        self.store.write_state(state)
        self.flush()
        return 0

    def note_capped(self, loop, capped):
        for path in capped:
            line = "the walk of %s stopped at %d entries" % (path, WALK_CAP)
            if line not in self.store.log_text(loop):
                self.log(loop, line)

    # Commands

    def command(self, argv):
        name = argv[0] if argv and argv[0] in USAGE else None
        try:
            if name is None or name == "hook":
                raise UsageError()
            options = parse(name, argv[1:])
            return getattr(self, "run_" + name)(options)
        except UsageError:
            text = "usage: python3 %s %s" % (PROGRAM, USAGE[name] if name else "start|end|stop|status ...")
        except Exception as cause:
            failure = cause if isinstance(cause, Failure) else Failure("input", cause)
            self.trace(failure)
            text = failure.text
        self.err.write("loop-to-delivery: %s\n" % text)
        return 2

    def refuse(self, text):
        self.err.write("loop-to-delivery: %s\n" % text)
        return 2

    def conversation(self, options):
        session = options.session if options.session is not None else self.environ.get("CLAUDE_CODE_SESSION_ID")
        return session if matches(SESSION_ID, session) else None

    def print_lines(self, *lines):
        self.out.write("".join(line + "\n" for line in lines))
        return 0

    def run_start(self, options):
        if not os.path.isabs(options.notes) or not all(os.path.isabs(path) for path in options.watch):
            return self.refuse("--notes and --watch need absolute paths.")
        session = self.conversation(options)
        if session is None:
            return self.refuse("this needs the conversation's id: --session ${CLAUDE_SESSION_ID}.")
        record = self.store.record(session)
        loop = record["loop"] if record else None
        if loop is not None:
            status, state, _error = self.load(loop)
            max_wakes = state["max"] if status == OK else None
            self.known_loop = loop
            if self.own_active(loop, session, max_wakes):
                state.update(notes=options.notes, watch=options.watch)
                self.store.write_state(state)
                self.log(loop, "start again: notes and watched paths updated")
                self.flush()
                return self.print_lines(RUNNING.format(loop=loop), CREATE_ONCE.format(loop=loop), create_line(loop))
            if record["prompt_after_end"] != loop:
                return self.refuse(REFUSED.format(loop=loop, why=self.why(loop, session, max_wakes)))
        with step("write state"):
            self.store.folders("loops")
            while True:
                loop = secrets.token_hex(4)
                try:
                    os.mkdir(self.store.path("loops", loop), 0o700)
                    break
                except FileExistsError:
                    continue
        self.known_loop = loop
        with step("fingerprint"):
            check, capped = full_fingerprint(options.notes, options.watch)
            notes = notes_fingerprint(options.notes)
        started = self.now.replace(microsecond=0)
        state = state_defaults(loop=loop, session_id=session, started=stamp(started),
                               deadline=stamp(started + timedelta(days=DAYS)), notes=options.notes,
                               watch=options.watch, check_fp=check, stop_fp=notes)
        self.store.write_state(state)
        record = record or new_record(session)
        record.update(loop=loop, prompt_after_end=None)
        self.store.write_record(record)
        self.log(loop, "start in conversation %s" % session)
        self.note_capped(loop, capped)
        self.flush()
        return self.print_lines(STARTED.format(loop=loop, session=session, notes=options.notes),
                                CREATE_ONCE.format(loop=loop), create_line(loop))

    def run_end(self, options):
        session = self.conversation(options)
        if session is None:
            return self.refuse("this needs the conversation's id: --session ${CLAUDE_SESSION_ID}.")
        record = self.store.record(session)
        loop = record["loop"] if record else None
        if loop is None:
            return self.print_lines("loop-to-delivery: no active loop in this conversation.")
        status, state, _error = self.load(loop)
        max_wakes = state["max"] if status == OK else None
        self.known_loop = loop
        if not self.own_active(loop, session, max_wakes):
            return self.print_lines(
                "loop-to-delivery: no active loop in this conversation; its loop %s has ended (%s). If CronList "
                'still shows a job whose prompt starts with "[auto loop-to-delivery %s]", delete it with CronDelete.'
                % (loop, self.why(loop, session, max_wakes), loop))
        reason = one_line(options.reason)
        self.store.end(loop, reason, "claude", self.now)
        self.log(loop, "end by claude (%s)" % reason)
        self.flush()
        return self.print_lines("loop-to-delivery: loop %s ended (%s); delete its wake-up job %s (CronList, "
                                "CronDelete)." % (loop, reason, job_ids(loop, state["jobs"])))

    def run_stop(self, _options):
        lines = []
        for loop in self.store.loops():
            status, state, _error = self.load(loop)
            if status != OK or self.end_reason(loop, state, state["max"]) is not None:
                continue
            self.known_loop = loop
            if self.store.end(loop, "stopped by the person", "person", self.now):
                self.log(loop, "stop by the person")
                lines.append("loop-to-delivery: stopped loop %s of conversation %s; notes: %s; its wake-up job: %s "
                             "(Claude is asked to delete it at the next prompt there)."
                             % (loop, state["session_id"], state["notes"], job_ids(loop, state["jobs"])))
        self.flush()
        return self.print_lines(*(lines or ["loop-to-delivery: no active loop to stop."]))

    def run_status(self, options):
        """Read-only: writes nothing."""
        only = options.session
        lines = []
        for loop in self.store.loops():
            status, state, error = self.load(loop)
            if only is not None and (status != OK or state["session_id"] != only):
                continue
            if status == MISSING:
                lines.append("loop %s: no state" % loop)
                continue
            if status == UNREADABLE:
                why = self.store.ended(loop)
                lines.append("loop %s: its state cannot be read (%s)%s"
                             % (loop, error, "; ended (%s)" % why if why else ""))
                continue
            why = self.end_reason(loop, state, state["max"])
            if why is None:
                standing = "active"
            else:
                at = self.store.ended_at(loop) if self.store.ended(loop) else None
                at = at or (state["ended"] or {}).get("at")
                standing = "ended (%s; %s)" % (why, "at %s" % at if at else "not recorded yet")
            lines.append("loop %s: conversation %s, %s; wake-ups %d of %s, %d in a row without progress, until %s; "
                         "notes %s; wake-up jobs %s"
                         % (loop, state["session_id"], standing, state["wakes"],
                            state["max"] if state["max"] is not None else "?", state["idle"], state["deadline"],
                            state["notes"], ", ".join(state["jobs"]) or "none known"))
            last = [line for line in self.store.log_text(loop).splitlines() if " error " in line]
            if last:
                lines.append("  last error: %s" % last[-1])
        for session in self.store.sessions():
            if only is not None and session != only:
                continue
            try:
                record = self.store.record(session)
            except Failure as failure:
                lines.append("conversation %s: its record cannot be read (%s)" % (session, failure.text))
                continue
            items = []
            for entry in record["jobs"]:
                owner = entry["loop"]
                if owner is None:
                    items.append(ITEM_NO_LOOP)
                    continue
                status, state, _error = self.load(owner)
                max_wakes = state["max"] if status == OK else None
                if not self.own_active(owner, session, max_wakes):
                    template = ITEM_JOB if entry["id"] is not None else ITEM_LOOP
                    items.append(template.format(job=entry["id"], loop=owner, why=self.why(owner, session, max_wakes)))
            if items:
                lines.append("conversation %s: wake-up jobs still to delete: %s" % (session, "; ".join(items)))
        errors = [line for line in self.store.log_text().splitlines() if line.strip()]
        if errors:
            lines.append("last error: %s" % errors[-1])
        return self.print_lines(*(lines or ["loop-to-delivery: no loops."]))


def main(argv, stdin, stdout, stderr, environ, now):
    """Entry point: `hook --max-wakes N` for Claude Code's hooks, or a command (start, end, stop, status)."""
    argv = list(argv)
    program = Program(stdout, stderr, environ, now)
    if argv[:1] == ["hook"]:
        return program.hook(argv[1:], stdin)
    return program.command(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr, os.environ, datetime.now(timezone.utc)))
