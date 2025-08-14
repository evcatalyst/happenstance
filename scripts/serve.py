#!/usr/bin/env python3
"""Simple development server for the static front-end.
Usage:
  python scripts/serve.py            # defaults to PORT=8000
  PORT=9000 python scripts/serve.py  # custom port

Serves the ./static directory so fetch() works (file:// won't due to browser CORS restrictions).
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import sys


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    if not os.path.isdir(root):
        print(f"Static directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    os.chdir(root)
    port = int(os.environ.get('PORT', '8000'))
    handler = SimpleHTTPRequestHandler
    with ThreadingHTTPServer(('', port), handler) as httpd:
        print(f"Serving {root} at http://localhost:{port} (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")

if __name__ == '__main__':
    main()
