#!/usr/bin/env python3
"""verbatim-proxy: an OpenAI-compatible proxy that keeps file names and paths verbatim.

When a coding agent works in a language other than English (Spanish, in our tests), the model sometimes picks a different file name from the one the
user asked for: `procesos.csv` becomes `processes.csv`, `usuarios.txt` becomes `users.txt`. The model is not translating (names unrelated to the system,
like `tortuga.txt`, are always kept); it "normalizes" words it recognizes as system concepts to the English names such files usually have.

The proxy sits between the client (e.g. opencode) and the server (e.g. vLLM). In the USER messages of /v1/chat/completions requests it wraps file names
and paths in backticks (`errores.txt`, `config/colector.yaml`, `/opt/app/bin`), so the model treats them as literals. It does not touch the system
prompt, tool results or the model's answers; everything else (including streaming) is forwarded unchanged. Standard library only (Python 3.8+).

usage:  verbatim_proxy.py --upstream http://127.0.0.1:8000 [--port 8199] [--host 127.0.0.1]
        verbatim_proxy.py --test                     # show what it marks
then point the client at http://127.0.0.1:8199/v1 instead of the server.
"""
import argparse, json, re, sys, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EXT = r"(?:txt|csv|md|sh|ya?ml|json|conf|cfg|ini|log|service|timer|socket|nft|py|sql|toml|xml|html?|js|ts|env|pem|key|crt)"
FILE = re.compile(r"(?<![`\w/.\-])((?:~?/)?(?:[\w.\-]+/)*[\w\-][\w.\-]*\." + EXT + r")(?![\w`])")
PATH = re.compile(r"(?<![`\w])(/(?:[\w.\-]+/)+[\w.\-]*)(?![\w`])")
UPSTREAM = ""


def mark(text):
    """Wrap file names and paths in backticks, leaving code spans and code blocks alone."""
    if not isinstance(text, str):
        return text
    parts = re.split(r"(```.*?```|`[^`\n]*`)", text, flags=re.S)   # odd items are already quoted: keep them
    for i in range(0, len(parts), 2):
        x = FILE.sub(r"`\1`", parts[i])
        x = PATH.sub(lambda m: m.group(0) if m.group(0).count("/") < 2 else f"`{m.group(1)}`", x)   # /a alone is not a path
        parts[i] = x
    return "".join(parts)


def transform(body):
    for m in body.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            m["content"] = mark(c)
        elif isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    p["text"] = mark(p.get("text"))
    return body


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _forward(self, body=None):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=self.command,
                                     headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "accept-encoding")})
        if body is not None:
            req.add_header("Content-Length", str(len(body)))
        try:
            r = urllib.request.urlopen(req, timeout=3600)
        except urllib.error.HTTPError as e:
            r = e
        self.send_response(r.status if hasattr(r, "status") else r.code)
        for k, v in r.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()
        while True:
            b = r.read1(65536) if hasattr(r, "read1") else r.read(65536)
            if not b:
                break
            self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        self.close_connection = True

    def do_GET(self):
        self._forward()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if self.path.rstrip("/").endswith("/chat/completions"):
            try:
                body = json.dumps(transform(json.loads(body)), ensure_ascii=False).encode()
            except Exception:
                pass   # not JSON we understand: forward it as it came
        self._forward(body)


EXAMPLES = ["Analiza app.log y escribe errores.txt con los 3 errores.",
            "Corrige mi-app.service aquí; mira /opt/miapp/bin y passwd.txt.",
            "Ya marcado: `informe.md`. Y config/colector.yaml",
            "Versión 2.5 y 3.14 no son ficheros; tampoco e.g. o 10.0.4.17"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OpenAI-compatible proxy that wraps file names and paths in backticks in user messages.")
    ap.add_argument("--upstream", help="server to forward to, e.g. http://127.0.0.1:8000")
    ap.add_argument("--port", type=int, default=8199)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--test", action="store_true", help="print what the proxy marks in a few examples and exit")
    a = ap.parse_args()
    if a.test:
        for t in EXAMPLES:
            print(f"{t}\n  -> {mark(t)}")
        sys.exit(0)
    if not a.upstream:
        ap.error("--upstream is required")
    UPSTREAM = a.upstream.rstrip("/")
    print(f"verbatim-proxy on http://{a.host}:{a.port} -> {UPSTREAM}", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
