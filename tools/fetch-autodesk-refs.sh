#!/usr/bin/env bash
# fetch-autodesk-refs.sh — populate vendor/autodesk-refs/ with the Autodesk
# reference assemblies the aeco Windows add-ins compile against, by scp'ing them
# from the licensed Windows hosts.
#
# WHY: lets fleet CI compile-check the Revit/Navisworks add-ins OFF-WINDOWS
# (macOS/Linux) for instant feedback. The DLLs are reference-only inputs; the
# add-ins still only *run* on Windows. See vendor/autodesk-refs/README.md.
#
# POLICY: these are Autodesk PROPRIETARY binaries. By default this repo does NOT
# commit them — vendor/autodesk-refs/**/*.dll is gitignored and fetched on
# demand (here). Do NOT push them to any public remote. (Committing them into a
# private repo is a documented, opt-in alternative — see the README policy note.)
#
# Usage:
#   tools/fetch-autodesk-refs.sh                 # fetch both, default hosts
#   REVIT_HOST=example-revit NAVIS_HOST=example-navis tools/fetch-autodesk-refs.sh
#   tools/fetch-autodesk-refs.sh --revit-only
#   tools/fetch-autodesk-refs.sh --navis-only
#   tools/fetch-autodesk-refs.sh --verify        # re-verify existing DLLs vs SHA256SUMS
#
# SSH: expects keyless SSH as user $SSH_USER (set explicitly) to the hosts.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(dirname "$here")"
vendor_dir="$repo_root/vendor/autodesk-refs"
revit_dir="$vendor_dir/revit-2027"
navis_dir="$vendor_dir/navis-2027"

SSH_USER="${SSH_USER:?set SSH_USER}"
REVIT_HOST="${REVIT_HOST:?set REVIT_HOST}"
NAVIS_HOST="${NAVIS_HOST:?set NAVIS_HOST}"
REVIT_INSTALL="${REVIT_INSTALL:-C:/Program Files/Autodesk/Revit 2027}"
NAVIS_INSTALL="${NAVIS_INSTALL:-C:/Program Files/Autodesk/Navisworks Manage 2027}"

# Reference assemblies the add-in .csproj files actually name (kept minimal).
REVIT_DLLS=(RevitAPI.dll RevitAPIUI.dll)
NAVIS_DLLS=(Autodesk.Navisworks.Api.dll)

do_revit=1
do_navis=1
verify_only=0
for arg in "$@"; do
  case "$arg" in
    --revit-only) do_navis=0 ;;
    --navis-only) do_revit=0 ;;
    --verify)     verify_only=1 ;;
    -h|--help)    grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

sha256() {
  # portable sha256 -> bare hex
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}';
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

verify_sums() {
  local sums="$vendor_dir/SHA256SUMS"
  if [[ ! -f "$sums" ]]; then
    echo "verify: no SHA256SUMS at $sums (skipping integrity check)" >&2
    return 0
  fi
  local fail=0 line hash rel
  while read -r hash rel; do
    [[ -z "$hash" ]] && continue
    if [[ ! -f "$vendor_dir/$rel" ]]; then
      echo "verify: MISSING $rel" >&2; fail=1; continue
    fi
    local got; got="$(sha256 "$vendor_dir/$rel")"
    if [[ "$got" != "$hash" ]]; then
      echo "verify: MISMATCH $rel" >&2
      echo "  expected $hash" >&2
      echo "  got      $got" >&2
      fail=1
    else
      echo "verify: OK $rel"
    fi
  done < "$sums"
  return "$fail"
}

if [[ "$verify_only" == 1 ]]; then
  verify_sums; exit $?
fi

fetch_set() {
  local host="$1" install="$2" dest="$3"; shift 3
  local -a dlls=("$@")
  mkdir -p "$dest"
  echo "==> fetching from ${SSH_USER}@${host}:${install}"
  local d
  for d in "${dlls[@]}"; do
    echo "    scp $d"
    scp -o ConnectTimeout=20 -o BatchMode=yes \
      "${SSH_USER}@${host}:${install}/${d}" "$dest/${d}"
    printf "    %-32s %s bytes  sha256=%s\n" "$d" "$(wc -c < "$dest/${d}" | tr -d ' ')" "$(sha256 "$dest/${d}")"
  done
}

[[ "$do_revit" == 1 ]] && fetch_set "$REVIT_HOST" "$REVIT_INSTALL" "$revit_dir" "${REVIT_DLLS[@]}"
[[ "$do_navis" == 1 ]] && fetch_set "$NAVIS_HOST" "$NAVIS_INSTALL" "$navis_dir" "${NAVIS_DLLS[@]}"

echo
echo "Fetched into $vendor_dir"
if [[ -f "$vendor_dir/SHA256SUMS" ]]; then
  echo "Verifying against committed SHA256SUMS ..."
  verify_sums || { echo "WARNING: fetched DLL hashes differ from SHA256SUMS — the host install may have been updated (new Revit/Navis build). Review, then refresh SHA256SUMS + vendor/autodesk-refs/MANIFEST.txt." >&2; }
else
  echo "No SHA256SUMS present yet. To record the current set:"
  echo "  ( cd \"$vendor_dir\" && (command -v sha256sum >/dev/null && sha256sum revit-2027/*.dll navis-2027/*.dll || shasum -a 256 revit-2027/*.dll navis-2027/*.dll | sed 's/  / /') > SHA256SUMS )"
fi
