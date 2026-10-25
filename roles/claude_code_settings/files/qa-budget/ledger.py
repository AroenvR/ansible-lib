#!/usr/bin/env python3
"""Claude Code hook for qa-budget: a ledger of the tokens each agent used.

Run on SubagentStart, SubagentStop and Stop with the hook's JSON on stdin. Appends
one line to $CLAUDE_CONFIG_DIR/qa-budget/ledger.jsonl (~/.claude): which session
and agent, its transcript's token totals so far (each API response counted
once: input, cache write, cache read, output), and the subscription's usage
from the status line's latest reading (rate-limits.json). A start line has no
tokens; it marks the usage when the agent began. A Stop line holds the main
session's totals so far: the last line of a transcript is its total.
Never blocks Claude Code: prints nothing and exits 0, also on errors.
"""
import datetime
import json
import os
import sys

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def state_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "qa-budget")


def usage(path):
    """Token totals of a transcript, each response once (a streamed one is logged more than once)."""
    responses, models = {}, set()
    with open(path, errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") if isinstance(entry, dict) else None
            if entry.get("type") != "assistant" or not isinstance(message, dict) or not message.get("usage"):
                continue
            counts = [message["usage"].get(k) or 0 for k in FIELDS]
            key = message.get("id") or len(responses)
            if key not in responses or counts[3] >= responses[key][3]:
                responses[key] = counts
            if message.get("model"):
                models.add(message["model"])
    totals = [sum(c[i] for c in responses.values()) for i in range(len(FIELDS))]
    result = dict(zip(FIELDS, totals))
    result["responses"] = len(responses)
    result["models"] = sorted(models)
    return result


def reading():
    try:
        with open(os.path.join(state_dir(), "rate-limits.json")) as f:
            latest = json.load(f)
        limits = latest.get("rate_limits") or {}
        return {
            "read_at": latest.get("time"),
            "five_hour": (limits.get("five_hour") or {}).get("used_percentage"),
            "seven_day": (limits.get("seven_day") or {}).get("used_percentage"),
        }
    except (OSError, ValueError, AttributeError):
        return None


def main():
    event = json.load(sys.stdin)
    name = event.get("hook_event_name")
    line = {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "event": name,
        "session_id": event.get("session_id"),
        "agent_id": event.get("agent_id"),
        "agent_type": event.get("agent_type"),
        "usage_reading": reading(),
    }
    transcript = event.get("agent_transcript_path") if name == "SubagentStop" else event.get("transcript_path")
    if name != "SubagentStart" and transcript:
        line["transcript"] = transcript
        line["tokens"] = usage(transcript)
    folder = state_dir()
    os.makedirs(folder, mode=0o700, exist_ok=True)
    with open(os.path.join(folder, "ledger.jsonl"), "a") as f:
        f.write(json.dumps(line) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # a ledger must never stop an agent
        sys.stderr.write("qa-budget ledger: %s\n" % error)
    sys.exit(0)
