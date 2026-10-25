#!/usr/bin/env python3
"""Claude Code hook for qa-budget: keeps agents within a budget of the subscription.

Run on UserPromptSubmit and PreToolUse with the hook's JSON on stdin. It reads the
status line's latest usage reading and the ledger (see statusline.py, ledger.py)
and decides with the limits below, each overridable by an environment variable
(in a settings file's env, for example):

  QA_BUDGET_WEEKLY=60          weekly ceiling for agent work, % of the 7-day window
  QA_BUDGET_FIVE_HOUR=90       ceiling, % of the 5-hour window
  QA_BUDGET_LIMIT=98           the subscription's limit as the guard sees it (readings lag one response)
  QA_BUDGET_SPEND_DOWN_HOURS=4 hours before the weekly reset from which the weekly ceiling rises to the limit,
  QA_BUDGET_INACTIVE_HOURS=3     once the person has been inactive this long
  QA_BUDGET_RUNS=12            expert runs (subagents) per session
  QA_BUDGET_RUN_TOKENS=1500000 tokens per run, weighted by price: input 1, cache write 1.25, cache read 0.1, output 5
  QA_BUDGET_STALE_MINUTES=10   a usage reading older than this is unknown
  QA_BUDGET_AUTO_PROMPT=...    regular expression for prompts no person typed; default: a leading [auto ...] tag
                               (e.g. "[auto qa-budget step 3] Read ...") or an autonomous-loop sentinel

A turn is automatic when its prompt matches QA_BUDGET_AUTO_PROMPT: every wake-up and loop prompt must carry the
tag. A session the guard has not seen a prompt of counts as automatic, unless the person typed a prompt within
QA_BUDGET_INACTIVE_HOURS.
- An automatic prompt is blocked (costs nothing) at a ceiling or the limit.
- A new expert run (the Agent or Workflow tool) at a ceiling, the limit or the run cap is denied in an automatic
  turn, and asked of the person in theirs: only they may go on, into extra usage too. In an automatic turn, it is
  also denied while the usage is unknown (no reading, or a stale one).
- In an automatic turn at the limit, every tool is denied: pause, never into extra usage.
- An expert over its token budget gets its tool calls denied: it reports now, with what remains as improvements.
The person is active while they typed a prompt within QA_BUDGET_INACTIVE_HOURS, or while the weekly usage rose
by more than a point between two readings at least 30 minutes apart (someone else used the subscription).
Never fails Claude Code: on an error it allows and exits 0.
"""
import datetime
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402  (same folder)

DEFAULTS = {"WEEKLY": 60, "FIVE_HOUR": 90, "LIMIT": 98, "SPEND_DOWN_HOURS": 4, "INACTIVE_HOURS": 3,
            "RUNS": 12, "RUN_TOKENS": 1500000, "STALE_MINUTES": 10}
AUTO_PROMPT = r"^\s*\[auto\b[^\]\n]*\]|<<autonomous-loop"
RUN_TOOLS = ("Agent", "Task", "Workflow")
WEIGHTS = {"input_tokens": 1, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5}
GAP = datetime.timedelta(minutes=30)


def limit(name):
    try:
        return float(os.environ.get("QA_BUDGET_" + name, DEFAULTS[name]))
    except ValueError:
        return float(DEFAULTS[name])


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse(text):
    try:
        return datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def path(name):
    return os.path.join(ledger.state_dir(), name)


def load(name, default):
    try:
        with open(path(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def usage_now(moment):
    """Used % per window from the latest reading; a window whose reset has passed counts as 0. "known" is False
    without a reading, or with one older than QA_BUDGET_STALE_MINUTES."""
    latest = load("rate-limits.json", {})
    latest = latest if isinstance(latest, dict) else {}
    limits = latest.get("rate_limits") or {}
    read_at = parse(latest.get("time"))
    used = {"known": bool(limits) and read_at is not None
            and moment - read_at <= datetime.timedelta(minutes=limit("STALE_MINUTES"))}
    for window in ("five_hour", "seven_day"):
        reading = limits.get(window) or {}
        reset = reading.get("resets_at")
        passed = isinstance(reset, (int, float)) and reset <= moment.timestamp()
        used[window] = 0.0 if passed else float(reading.get("used_percentage") or 0)
        used[window + "_reset"] = reset if isinstance(reset, (int, float)) and not passed else None
    return used


def foreign_use(moment):
    """When the weekly usage last rose more than a point across a gap of 30 minutes or more."""
    last, previous = None, None
    try:
        with open(path("rate-limits.jsonl")) as f:
            for line in f:
                try:
                    reading = json.loads(line)
                except ValueError:
                    continue
                at = parse(reading.get("time"))
                week = (reading.get("rate_limits") or {}).get("seven_day") or {}
                if at is None or week.get("used_percentage") is None:
                    continue
                if (previous and at - previous[0] >= GAP and week.get("resets_at") == previous[2]
                        and week["used_percentage"] - previous[1] > 1):
                    last = at
                previous = (at, week["used_percentage"], week.get("resets_at"))
    except OSError:
        pass
    return last


def person_active(activity, moment):
    times = [t for t in (parse(activity.get("person_prompt_at")), foreign_use(moment)) if t]
    return bool(times) and moment - max(times) < datetime.timedelta(hours=limit("INACTIVE_HOURS"))


def weekly_ceiling(used, activity, moment):
    """The weekly ceiling, raised to the limit in the spend-down before the reset while the person is inactive."""
    reset = used["seven_day_reset"]
    if reset is not None:
        left = datetime.datetime.fromtimestamp(reset, datetime.timezone.utc) - moment
        if left <= datetime.timedelta(hours=limit("SPEND_DOWN_HOURS")) and not person_active(activity, moment):
            return limit("LIMIT")
    return limit("WEEKLY")


def over(used, activity, moment):
    """The first ceiling reached, as text, or None."""
    if max(used["seven_day"], used["five_hour"]) >= limit("LIMIT"):
        return "the subscription's limit (%.0f%%)" % limit("LIMIT")
    ceiling = weekly_ceiling(used, activity, moment)
    if used["seven_day"] >= ceiling:
        return "the weekly ceiling (%.0f%% of the week used, ceiling %.0f%%)" % (used["seven_day"], ceiling)
    if used["five_hour"] >= limit("FIVE_HOUR"):
        return "the 5-hour ceiling (%.0f%% used, ceiling %.0f%%)" % (used["five_hour"], limit("FIVE_HOUR"))
    return None


def resets(used):
    texts = []
    for window, label in (("seven_day", "weekly"), ("five_hour", "5-hour")):
        if used[window + "_reset"]:
            at = datetime.datetime.fromtimestamp(used[window + "_reset"], datetime.timezone.utc)
            texts.append("%s window resets %s" % (label, at.strftime("%a %Y-%m-%d %H:%M UTC")))
    return "; ".join(texts)


def runs(session):
    count = 0
    try:
        with open(path("ledger.jsonl")) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                count += entry.get("event") == "SubagentStart" and entry.get("session_id") == session
    except OSError:
        pass
    return count


def weighted(tokens):
    return sum(tokens.get(k, 0) * w for k, w in WEIGHTS.items())


def agent_transcript(event):
    base = event.get("transcript_path") or ""
    if not base.endswith(".jsonl"):
        return None
    return os.path.join(base[:-len(".jsonl")], "subagents", "agent-%s.jsonl" % event["agent_id"])


def save_activity(activity):
    """Best effort: a failed save must not change the decision."""
    try:
        os.makedirs(ledger.state_dir(), mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=ledger.state_dir(), prefix=".activity.")
        with os.fdopen(fd, "w") as f:
            json.dump(activity, f)
        os.replace(tmp, path("activity.json"))
    except OSError as error:
        sys.stderr.write("qa-budget guard: activity not saved: %s\n" % error)


def on_prompt(event, activity, moment):
    automatic = re.search(os.environ.get("QA_BUDGET_AUTO_PROMPT") or AUTO_PROMPT, event.get("prompt") or "") is not None
    sessions = {k: v for k, v in (activity.get("sessions") or {}).items()
                if (parse(v.get("at")) or moment) > moment - datetime.timedelta(days=8)}
    sessions[event.get("session_id") or "?"] = {"turn": "automatic" if automatic else "person", "at": moment.isoformat()}
    activity["sessions"] = sessions
    if not automatic:
        activity["person_prompt_at"] = moment.isoformat()
    answer = None
    if automatic:
        used = usage_now(moment)
        reached = over(used, activity, moment)
        if reached:
            answer = {"decision": "block", "reason": "qa-budget: automatic prompt not run, %s is reached; %s. "
                      "It runs again after the reset, or when a person starts the turn." % (reached, resets(used))}
    save_activity(activity)
    return answer


def automatic_turn(activity, session, moment):
    turn = ((activity.get("sessions") or {}).get(session) or {}).get("turn")
    if turn:
        return turn == "automatic"
    person = parse(activity.get("person_prompt_at"))
    return person is None or moment - person >= datetime.timedelta(hours=limit("INACTIVE_HOURS"))


def decide(kind, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind,
                                   "permissionDecisionReason": "qa-budget: " + reason}}


def on_tool(event, activity, moment):
    session = event.get("session_id")
    automatic = automatic_turn(activity, session, moment)
    used = usage_now(moment)
    reached = over(used, activity, moment)
    pause = ("Pause: write what is done and what comes next to the task's handoff file, then stop; %s." % resets(used))
    if automatic and reached and reached.startswith("the subscription's limit"):
        return decide("deny", "%s is reached in an automatic turn, which never goes into extra usage. %s" % (reached, pause))
    if event.get("agent_id"):
        transcript = agent_transcript(event)
        if transcript and os.path.exists(transcript):
            spent = weighted(ledger.usage(transcript))
            if spent >= limit("RUN_TOKENS"):
                return decide("deny", "this run used %.0f of its %.0f weighted tokens. Use no more tools: write your "
                              "report now, with what remains as a list of improvements." % (spent, limit("RUN_TOKENS")))
        return None
    if event.get("tool_name") not in RUN_TOOLS:
        return None
    count = runs(session)
    if count >= limit("RUNS"):
        reached = reached or "the cap of %.0f expert runs in this session (%d run)" % (limit("RUNS"), count)
    if automatic and not used["known"]:
        reached = reached or "an unknown usage (no status line reading of the last %.0f minutes)" % limit("STALE_MINUTES")
    if not reached:
        return None
    if automatic:
        return decide("deny", "no new expert run: %s. Deliver what passed, with the open findings as a list of "
                      "improvements, or pause. %s" % (reached, pause))
    return decide("ask", "%s. Start this expert run anyway?" % reached)


def main():
    event = json.load(sys.stdin)
    moment = now()
    activity = load("activity.json", {})
    if not isinstance(activity, dict):
        activity = {}
    name = event.get("hook_event_name")
    answer = on_prompt(event, activity, moment) if name == "UserPromptSubmit" else (
        on_tool(event, activity, moment) if name == "PreToolUse" else None)
    if answer:
        print(json.dumps(answer))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # a broken guard must not stop the session
        sys.stderr.write("qa-budget guard: %s\n" % error)
    sys.exit(0)
