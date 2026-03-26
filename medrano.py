from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from js import JSParseError, JSRuntime, JSError, default_globals


def _to_output_text(value: Any) -> str:
	if value is None:
		return "null"
	if isinstance(value, bool):
		return "true" if value else "false"
	return str(value)


def _read_source(file_arg: str | None) -> str:
	if file_arg and file_arg != "-":
		return Path(file_arg).read_text(encoding="utf-8")

	if not sys.stdin.isatty():
		return sys.stdin.read()

	if file_arg == "-":
		raise ValueError("No JavaScript received from stdin")

	raise ValueError("No JavaScript source provided (pass a file or pipe code to stdin)")


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		prog="medrano",
		description="Run JavaScript with the Medrano engine",
	)
	parser.add_argument("file", nargs="?", help="JavaScript file to run, or '-' for stdin")
	args = parser.parse_args(argv)

	try:
		source = _read_source(args.file)
		runtime = JSRuntime(default_globals(console_logger=print))
		result = runtime.execute(source)
		if result is not None:
			print(_to_output_text(result))
		return 0
	except FileNotFoundError as exc:
		print(f"medrano: file not found: {exc.filename}", file=sys.stderr)
		return 1
	except (JSParseError, JSError, ValueError) as exc:
		print(f"medrano: {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())