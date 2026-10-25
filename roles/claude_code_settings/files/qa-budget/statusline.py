#!/usr/bin/env python3
"""Claude Code's status line for qa-budget: saves the subscription's usage, prints it.

Claude Code runs this after a response, with the session's state as JSON on stdin.
Only the status line receives rate_limits (the 5-hour and the 7-day window, each
with used_percentage and resets_at); hooks do not. So this saves them where the
hooks and later sessions read them, in $CLAUDE_CONFIG_DIR/qa-budget (~/.claude):
  rate-limits.json   the latest reading, replaced atomically
  rate-limits.jsonl  every changed reading, one per line, for how usage moves
A reading lags one response behind. Never fails Claude Code: on any error it
prints what it can and exits 0.
"""
import datetime
import json
import os
import sys
import tempfile

WINDOWS = ("five_hour", "seven_day")
LABELS = {"five_hour": "5h", "seven_day": "7d"}


def state_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "qa-budget")


def reset_time(value):
    """resets_at as UTC text; Claude Code gives epoch seconds (ISO text is taken too)."""
    try:
        if isinstance(value, (int, float)):
            moment = datetime.datetime.fromtimestamp(value, datetime.timezone.utc)
        else:
            moment = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
        return moment.strftime("%a %H:%M UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def save(limits, session):
    folder = state_dir()
    os.makedirs(folder, mode=0o700, exist_ok=True)
    latest = os.path.join(folder, "rate-limits.json")
    try:
        with open(latest) as f:
            before = json.load(f).get("rate_limits")
    except (OSError, ValueError, AttributeError):
        before = None
    # Usage never falls within a window: a lower value for the same reset is an
    # older reading (another session's), so the higher one stays.
    limits = dict(limits)
    for window in WINDOWS:
        old, new = (before or {}).get(window), limits.get(window)
        if (isinstance(old, dict) and isinstance(new, dict) and old.get("resets_at") == new.get("resets_at")
                and (old.get("used_percentage") or 0) > (new.get("used_percentage") or 0)):
            limits[window] = old
    reading = {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "session_id": session.get("session_id"),
        "model": (session.get("model") or {}).get("id"),
        "rate_limits": limits,
    }
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".rate-limits.")
    with os.fdopen(fd, "w") as f:
        json.dump(reading, f)
    os.replace(tmp, latest)
    if limits != before:
        with open(os.path.join(folder, "rate-limits.jsonl"), "a") as f:
            f.write(json.dumps(reading) + "\n")


def main():
    try:
        session = json.load(sys.stdin)
    except ValueError:
        session = {}
    if not isinstance(session, dict):
        session = {}
    limits = session.get("rate_limits")
    parts = [(session.get("model") or {}).get("display_name") or "Claude"]
    if isinstance(limits, dict):
        try:
            save(limits, session)
        except OSError as error:
            parts.append("qa-budget: not saved (%s)" % error.strerror)
        for window in WINDOWS:
            usage = limits.get(window) or {}
            percent = usage.get("used_percentage")
            if percent is None:
                continue
            text = "%s %.0f%%" % (LABELS[window], percent)
            reset = reset_time(usage.get("resets_at"))
            parts.append(text + (" (resets %s)" % reset if reset else ""))
    else:
        parts.append("usage: no reading yet")
    print(" | ".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a status line must never break the session
        print("qa-budget status line failed")
    sys.exit(0)
