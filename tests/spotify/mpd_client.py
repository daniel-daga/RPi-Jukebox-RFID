"""Minimal MPD protocol client (stdlib only).

Speaks the same protocol that mpc and the Phoniebox shell scripts use
against Mopidy-MPD, e.g. in playout_controls.sh:
    echo -e "status\\nclose" | nc -w 1 localhost 6600
"""

import socket


class MPDError(Exception):
    pass


def quote(arg):
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class MPDClient:

    def __init__(self, host="127.0.0.1", port=6600, timeout=10):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.file = self.sock.makefile("rb")
        banner = self.file.readline().decode("utf-8")
        if not banner.startswith("OK MPD"):
            raise MPDError(f"Unexpected banner: {banner!r}")

    def close(self):
        try:
            self.sock.sendall(b"close\n")
        except OSError:
            pass
        self.file.close()
        self.sock.close()

    def command(self, cmd):
        """Send a command, return the response lines (without final OK)."""
        self.sock.sendall((cmd + "\n").encode("utf-8"))
        lines = []
        while True:
            raw = self.file.readline()
            if not raw:
                raise MPDError("Connection closed by server")
            line = raw.decode("utf-8").rstrip("\n")
            if line == "OK":
                return lines
            if line.startswith("ACK"):
                raise MPDError(line)
            lines.append(line)

    def command_dict(self, cmd):
        """Send a command, parse 'key: value' response lines into a dict."""
        result = {}
        for line in self.command(cmd):
            key, _, value = line.partition(": ")
            result[key.lower()] = value
        return result

    def status(self):
        return self.command_dict("status")
