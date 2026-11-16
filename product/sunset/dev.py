"""Local preview: python -m sunset.dev  -> builds the site and serves it with the API on :8000.

Mail goes to ./outbox as .eml files unless SMTP_HOST is set. Not for production.
"""
import functools
import os
import pathlib
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import build, server


def main(port=8000):
    out = pathlib.Path(tempfile.mkdtemp()) / "dist"
    os.environ.setdefault("SITE_URL", f"http://localhost:{port}")
    build.build(out)
    class Dev(server.Handler, SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/api/") and not self.path.startswith("/api/v1/"):
                return server.Handler.do_GET(self)
            SimpleHTTPRequestHandler.do_GET(self)

    handler = functools.partial(Dev, directory=str(out))
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
