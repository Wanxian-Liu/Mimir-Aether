#!/usr/bin/env python3
"""
Mimir Daemon — lightweight status server for port 18791.
Reports Mimir's current health, state (idle/active), and last activity.
"""

import http.server
import json
import os
import signal
import socket
import socketserver
import sys
import time
from datetime import datetime

HOST = "127.0.0.1"
PORT = 18791

START_TIME = time.time()
STATE_FILE = os.path.expanduser("~/.mimiraether/data/star-office-state.json")


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"state": "idle", "area": "breakroom", "detail": "daemon init"}


class MimirHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        state = load_state()
        uptime_sec = int(time.time() - START_TIME)
        body = json.dumps({
            "agent": "MimirAether",
            "status": "alive",
            "uptime_sec": uptime_sec,
            "uptime_human": f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s",
            "state": state.get("state", "idle"),
            "area": state.get("area", "breakroom"),
            "detail": state.get("detail", ""),
            "pid": os.getpid(),
            "started_at": datetime.fromtimestamp(START_TIME).isoformat(),
            "endpoints": {
                "/health": "this status report",
                "/state": "current Mimir state",
            }
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write(f"[MimirDaemon] {args}\n")


class ReuseAddrServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    server = ReuseAddrServer((HOST, PORT), MimirHandler)
    print(f"[MimirDaemon] Listening on http://{HOST}:{PORT}", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[MimirDaemon] Shutdown", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()
