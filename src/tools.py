import subprocess
import sys


def format_code() -> None:
    sys.exit(subprocess.run(["ruff", "format", "."], check=False).returncode)


def lint_code() -> None:
    sys.exit(subprocess.run(["ruff", "check", "."], check=False).returncode)