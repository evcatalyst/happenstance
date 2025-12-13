from happenstance.cli import build_parser, serve_command

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args(["serve"])
    serve_command(args)
