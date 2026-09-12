#!/usr/bin/env bash
# drift-check — verify that cmake/pxr-macros/ is a byte-exact copy of the
# pinned OpenUSD source's cmake/macros/ and cmake/defaults/ directories.
#
# This covers the *.cmake macro/defaults files AND the support files the
# macros reference by sibling path (testWrapper.py, compilePython.py,
# moduleDeps.cpp.in, shebang.py, test.pre.js, ...): every regular file in
# the source directories must exist byte-identical in the replica, and the
# replica must contain no extra files. Exits non-zero and prints a diff on
# any difference.
#
# Source selection:
#   - If OPENUSD_SRC is set, it must point at an OpenUSD source tree
#     (used by the nix flake check, which passes the flake input directly).
#   - Otherwise the pinned source is materialised via `nix build
#     .#openusd-src` from the repo this script lives in.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(dirname "$here")"
replica_root="$repo_root/cmake/pxr-macros"

src="${OPENUSD_SRC:-}"
if [[ -z "$src" ]]; then
    src="$(nix build "$repo_root#openusd-src" --no-link --print-out-paths)"
fi

if [[ ! -d "$src/cmake/macros" || ! -d "$src/cmake/defaults" ]]; then
    echo "drift-check: '$src' does not look like an OpenUSD source tree" >&2
    exit 2
fi

fail=0

compare_dir() {
    local sub="$1"
    local src_dir="$src/cmake/$sub"
    local rep_dir="$replica_root/$sub"
    local f base

    # Every regular file in the source dir must exist, byte-identical,
    # in the replica.
    for f in "$src_dir"/*; do
        [[ -f "$f" ]] || continue
        base="$(basename "$f")"
        if [[ ! -f "$rep_dir/$base" ]]; then
            echo "DRIFT: missing from replica: cmake/pxr-macros/$sub/$base" >&2
            fail=1
        elif ! diff -u "$rep_dir/$base" "$f"; then
            echo "DRIFT: content differs: cmake/pxr-macros/$sub/$base" >&2
            fail=1
        fi
    done

    # No extra files in the replica.
    for f in "$rep_dir"/*; do
        [[ -f "$f" ]] || continue
        base="$(basename "$f")"
        if [[ ! -f "$src_dir/$base" ]]; then
            echo "DRIFT: extra file in replica: cmake/pxr-macros/$sub/$base" >&2
            fail=1
        fi
    done
}

compare_dir macros
compare_dir defaults

if [[ "$fail" -ne 0 ]]; then
    echo "drift-check: FAILED — cmake/pxr-macros is out of sync with $src" >&2
    exit 1
fi

echo "drift-check: OK — cmake/pxr-macros matches $src (all files, both directions)"
