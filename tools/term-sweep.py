#!/usr/bin/env python3
"""Check tracked and new repository text without printing sensitive matches."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [r"\b(?:10|100|127)(?:\.\d{1,3}){3}\b",
            r"\b192\.168(?:\.\d{1,3}){2}\b", r"\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b",
            r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", r"/(?:Users|Volumes|home)/[^\s\"']+",
            r"\b[A-Z]:[/\\]Users[/\\]", r"\b[\w.-]+\.(?:local|lan|internal|ts\.net)\b",
            r"\b(?:mini|studio|npg)[-](?:one|two|three|\d+)\b",
            r"cr[i]ad", r"fel[i]x", r"neu[f]eld", r"sj[w]s", r"gr[q]6a",
            r"for[u]m-\d+", r"be[e]-\d+", r"\bcd[c]1\b"]


def has_private_term(name, line):
    # Only the exact public slug and root licence attribution are exempt.
    if name == "LICENSE" and re.fullmatch(r"Copyright \(c\) 2026 [C]riad", line):
        return False
    public_text = re.sub(r"(?<![\w.-])criad-com(?![\w-]|\.[\w-])", "", line)
    return bool(re.search("|".join(PATTERNS), public_text, re.I))


def sweep(root=ROOT):
    files = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                    cwd=root).decode().split("\0")
    failures = []
    for name in sorted(set(files)):
        if not name:
            continue
        path = root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text().splitlines()
        except UnicodeError:
            continue
        failures.extend(f"{name}:{number}" for number, line in enumerate(lines, 1)
                        if has_private_term(name, line))
    for failure in failures:
        print(failure)
    print(f"term sweep: {len(failures)} findings")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(sweep())
