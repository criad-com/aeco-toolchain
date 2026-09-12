#!/usr/bin/env python3
"""Apply an external deployment registry (or the public template) to Nix."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
registry_path = Path(os.environ.get("AECO_NIX_REGISTRY", root / "nix/registry.json"))
registry = json.loads(registry_path.read_text())
if len(sys.argv) < 2:
    raise SystemExit("usage: nix-local.py build|develop|flake check [Nix arguments]")
options = []
for key, value in registry["nixConfig"].items():
    options += ["--option", key, " ".join(value)]
mirror = registry["flakes"][0]["to"]["url"]
revision = "47154dc7b5e28df623745495a7a508b69535ba24"
command = ["nix", *options, *sys.argv[1:], "--no-write-lock-file",
           "--override-input", "openusd", f"git+{mirror}?ref=dev&rev={revision}"]
os.chdir(root)
os.execvp("nix", command)
