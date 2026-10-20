#!/usr/bin/env python3
"""Runs loop-to-delivery's installed hook command as Claude Code runs it (sh -c,
the event as JSON on stdin), with a temporary HOME for the loop's state: for a
prompt of a conversation without a loop, then for the wake-up job of a loop the
installed program starts in a conversation. Prints the results as JSON:
loop-hook.py POLICY PROGRAM (the installed managed-settings.json and program)."""
import json
import os
import subprocess
import sys
import tempfile

policy, program = sys.argv[1], sys.argv[2]
with open(policy, encoding="utf-8") as handle:
    command = json.load(handle)["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
session = "cccccccc-3333-4333-8333-333333333333"
results = {"command": command}
with tempfile.TemporaryDirectory() as home:
    env = dict(os.environ, HOME=home)

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
        results["wake"] = hook("p-2", json.loads(lines[-1][len("CronCreate "):])["prompt"])
print(json.dumps(results))
