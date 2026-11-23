"""A minimal SMTP server for tests: accepts messages, or refuses recipients on request."""

import socket
import socketserver
import threading
from email import message_from_bytes, policy
from email.message import EmailMessage


class _Handler(socketserver.StreamRequestHandler):
    def _reply(self, line: str) -> None:
        self.wfile.write(f"{line}\r\n".encode())

    def handle(self) -> None:
        server: FakeSmtpServer = self.server.owner  # type: ignore[attr-defined]
        self._reply("220 fake-smtp ready")
        while line := self.rfile.readline():
            command = line.decode().strip()
            verb = command.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self._reply("250 fake-smtp")
            elif verb == "MAIL":
                self._reply("250 OK")
            elif verb == "RCPT":
                self._reply(server.rcpt_reply)
            elif verb == "DATA":
                self._reply("354 End data with <CR><LF>.<CR><LF>")
                data = b""
                while (chunk := self.rfile.readline()) not in (b".\r\n", b""):
                    data += chunk[1:] if chunk.startswith(b"..") else chunk
                server.received.append(message_from_bytes(data, policy=policy.default))
                self._reply("250 OK queued")
            elif verb == "RSET" or verb == "NOOP":
                self._reply("250 OK")
            elif verb == "QUIT":
                self._reply("221 Bye")
                return
            else:
                self._reply("502 Command not implemented")


class FakeSmtpServer:
    def __init__(self) -> None:
        self.received: list[EmailMessage] = []
        self.rcpt_reply = "250 OK"
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self._server.owner = self  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]

    def __enter__(self) -> "FakeSmtpServer":
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def unused_port() -> int:
    """A local port with nothing listening on it."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
