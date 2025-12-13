from __future__ import annotations

import argparse
import http.server
import os
from pathlib import Path
from typing import Callable

from .aggregate import aggregate


def aggregate_command(args: argparse.Namespace) -> None:
    aggregate(args.profile)


def serve_command(args: argparse.Namespace) -> None:
    docs_dir = Path(args.directory).resolve()
    os.chdir(docs_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with http.server.ThreadingHTTPServer(("", args.port), handler) as httpd:
        print(f"Serving {docs_dir} on port {args.port}")
        httpd.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="happenstance")
    sub = parser.add_subparsers(dest="command", required=True)

    agg = sub.add_parser("aggregate", help="Generate docs/*.json")
    agg.add_argument("--profile", default=None)
    agg.set_defaults(func=aggregate_command)

    srv = sub.add_parser("serve", help="Serve docs/ locally")
    srv.add_argument("--directory", default=Path(__file__).resolve().parent.parent / "docs")
    srv.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    srv.set_defaults(func=serve_command)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    func: Callable = args.func
    func(args)


if __name__ == "__main__":
    main()
