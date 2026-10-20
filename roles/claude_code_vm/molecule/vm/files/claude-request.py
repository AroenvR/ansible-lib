#!/usr/bin/env python3
"""Runs COMMAND with Claude Code's API at a stand-in on 127.0.0.1 and prints the
requests Claude Code sent it within SECONDS, which hold the skills and the agents
it found, as a JSON list: claude-request.py SECONDS COMMAND [ARGS...]. The
stand-in answers every request with an error, so nothing reaches a model."""
import http.server
import json
import os
import subprocess
import sys
import threading
import time

seconds, command = float(sys.argv[1]), sys.argv[2:]
requests = []


class StandIn(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        requests.append(json.loads(body or b"null"))
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"type": "error", "error": {"type": "invalid_request_error", "message": "stand-in"}}')

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), StandIn)
threading.Thread(target=server.serve_forever, daemon=True).start()
env = dict(os.environ, ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_port}",
           ANTHROPIC_API_KEY="sk-ant-api03-stand-in")
claude = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
end = time.time() + seconds
while time.time() < end and claude.poll() is None:
    time.sleep(0.2)
claude.kill()
print(json.dumps(requests))
sys.exit(0 if requests else 1)
