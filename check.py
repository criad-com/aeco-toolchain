#!/usr/bin/env python3
"""Run hub source gates and optional Nix checks; print N checks, M failed."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nix", action="store_true", help="also build all flake checks through the local registry")
    args = parser.parse_args()
    results = []
    commands = [
        ("conventions", [sys.executable, "tools/aecoLintConventions.py", "."]),
        ("pytest", [sys.executable, "-m", "pytest", "-q", "tools/tests"]),
        ("term-sweep", [sys.executable, "tools/term-sweep.py"]),
    ]
    if args.nix:
        commands.append(("nix-flake-check", [sys.executable, "tools/nix-local.py", "flake", "check", "-L"]))
    for name, command in commands:
        print(f"== stage: {name}", flush=True)
        result = subprocess.run(command, cwd=ROOT)
        results.append(result.returncode == 0)
        print(f"{'PASS' if results[-1] else 'FAIL'}  {name}", flush=True)
    print(f"\n{len(results)} checks, {results.count(False)} failed")
    return int(not all(results))


if __name__ == "__main__":
    raise SystemExit(main())
