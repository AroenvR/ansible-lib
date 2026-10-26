#!/usr/bin/env python3
"""Runs loop-to-delivery's installed hook command as Claude Code runs it (sh -c,
the event as JSON on stdin), with a temporary HOME for the loop's state and
qa-budget's readings: for a prompt of a conversation without a loop, then for the
wake-up job of a loop the installed program starts in a conversation, then for
the next wake-up of that loop with a reading of the status line over the weekly
ceiling (the installed guard ends the loop). Prints the results as JSON:
loop-hook.py POLICY PROGRAM (the installed managed-settings.json and program)."""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

policy, program = sys.argv[1], sys.argv[2]
with open(policy, encoding="utf-8") as handle:
    entries = json.load(handle)["hooks"]["UserPromptSubmit"]
# qa-budget's guard hooks the same event, and comes first: the loop's is the command that names its program.
commands = [hook["command"] for entry in entries for hook in entry["hooks"] if program in hook["command"]]
session = "cccccccc-3333-4333-8333-333333333333"
results = {"commands": commands}
if len(commands) == 1:
    command = commands[0]
    results["command"] = command
    hours = int(re.search(r"--max-hours ([0-9]+) ", command).group(1))

    def ends_on():   # the date the hook names as the end of a loop started now, by this clock
        return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).date().isoformat()

    # No QA_BUDGET_* limits and no other config folder: the guard reads $HOME/.claude/qa-budget only.
    env = {name: value for name, value in os.environ.items()
           if name != "CLAUDE_CONFIG_DIR" and not name.startswith("QA_BUDGET_")}
    with tempfile.TemporaryDirectory() as home:
        env["HOME"] = home

        def run(argv, data=""):
            done = subprocess.run(argv, input=data, capture_output=True, text=True, env=env, timeout=60)
            return {"rc": done.returncode, "stdout": done.stdout, "stderr": done.stderr}

        def hook(prompt_id, prompt):
            event = {"session_id": session, "prompt_id": prompt_id, "hook_event_name": "UserPromptSubmit",
                     "prompt": prompt}
            return run(["sh", "-c", command], json.dumps(event))

        results["unknown"] = hook("p-1", "Hello")
        notes = os.path.join(home, "notes.md")
        with open(notes, "w", encoding="utf-8") as handle:
            handle.write("# Goal\nDone when the test passes.\n")
        results["start"] = run(["/usr/bin/python3", "-I", program, "start", "--session", session, "--notes", notes])
        lines = results["start"]["stdout"].strip().splitlines()
        if results["start"]["rc"] == 0 and lines and lines[-1].startswith("CronCreate {"):
            wake_up = json.loads(lines[-1][len("CronCreate "):])["prompt"]
            # No reading of the status line yet: the usage is unknown, which the guard lets through.
            before = ends_on()
            results["wake"] = hook("p-2", wake_up)
            results["ends_on"] = sorted({before, ends_on()})
            # A reading made now, 61% of the week used, over the guard's ceiling of 60%.
            now = datetime.datetime.now(datetime.timezone.utc)
            folder = os.path.join(home, ".claude", "qa-budget")
            os.makedirs(folder, mode=0o700)
            reset = int((now + datetime.timedelta(days=1)).timestamp())
            reading = {"time": now.isoformat(timespec="seconds"), "rate_limits": {
                "five_hour": {"used_percentage": 10, "resets_at": reset},
                "seven_day": {"used_percentage": 61, "resets_at": reset}}}
            with open(os.path.join(folder, "rate-limits.json"), "w", encoding="utf-8") as handle:
                json.dump(reading, handle)
            results["over"] = hook("p-3", wake_up)
print(json.dumps(results))
