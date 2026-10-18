#!/usr/bin/env python3
"""Starts a command in a terminal of its own and prints the text its screen shows
after SECONDS, without the terminal's control codes. For Claude Code's start:
claude-screen.py SECONDS COMMAND [ARGS...]"""
import os
import pty
import re
import select
import signal
import sys
import time

seconds, command = float(sys.argv[1]), sys.argv[2:]
pid, fd = pty.fork()
if pid == 0:
    os.environ.update(TERM="xterm-256color", COLUMNS="120", LINES="40")
    os.execvp(command[0], command)
out = b""
end = time.time() + seconds
while time.time() < end:
    ready, _, _ = select.select([fd], [], [], 0.2)
    if ready:
        try:
            out += os.read(fd, 65536)
        except OSError:
            break
os.kill(pid, signal.SIGKILL)
text = re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]|\x1b[=>]", b" ", out)
print(re.sub(r"[ \t]+", " ", text.decode("utf-8", "replace")))
