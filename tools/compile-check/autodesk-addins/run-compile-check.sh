#!/usr/bin/env bash
# run-compile-check.sh — off-Windows compile-check for the aeco Windows add-ins.
#
# Compiles a checkout of the Revit and Navisworks add-in sources against the
# vendored Autodesk DLLs, on macOS/Linux, with no Windows host. Prints PASS/FAIL
# per add-in. This is a syntax/type/API-surface gate; the add-ins still only RUN
# on Windows.
#
# Prereqs:
#   * .NET SDK 10.x on PATH (or at $DOTNET_ROOT). If absent, this script can
#     install a self-contained SDK into $HOME/.dotnet with the official script
#     (no sudo) when run with --install-sdk.
#   * Vendored DLLs present under ../../../vendor/autodesk-refs/. If missing,
#     run tools/fetch-autodesk-refs.sh first (or pass --fetch to do it here).
#
# Usage:
#   run-compile-check.sh [--install-sdk] [--fetch] [--addins-repo PATH] [--revit-only|--navis-only]
#
# --addins-repo / ADDINS_REPO select the source checkout (reference-only).
# The default is a sibling directory named autodesk-addins.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../../.." && pwd)"

# Default: autodesk-addins is a sibling of this repo's checkout.
ADDINS_REPO="${ADDINS_REPO:-$(cd "$repo_root/.." && pwd)/autodesk-addins}"
install_sdk=0
do_fetch=0
targets=(revit navis)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-sdk) install_sdk=1 ;;
    --fetch)       do_fetch=1 ;;
    --addins-repo) ADDINS_REPO="$2"; shift ;;
    --revit-only)  targets=(revit) ;;
    --navis-only)  targets=(navis) ;;
    -h|--help)     grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

echo "addins repo: $ADDINS_REPO"
if [[ ! -d "$ADDINS_REPO" ]]; then
  echo "ERROR: a checkout of the Revit and Navisworks add-in sources was not found at $ADDINS_REPO (pass --addins-repo PATH or set ADDINS_REPO)." >&2
  exit 4
fi
ADDINS_REPO="$(cd "$ADDINS_REPO" && pwd)"

# --- locate or install dotnet ---
if command -v dotnet >/dev/null 2>&1; then
  DOTNET="$(command -v dotnet)"
elif [[ -x "${DOTNET_ROOT:-$HOME/.dotnet}/dotnet" ]]; then
  DOTNET="${DOTNET_ROOT:-$HOME/.dotnet}/dotnet"
elif [[ "$install_sdk" == 1 ]]; then
  echo "==> installing .NET SDK 10.x into \$HOME/.dotnet (no sudo)"
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
  bash /tmp/dotnet-install.sh --channel 10.0 --install-dir "$HOME/.dotnet" --no-path
  DOTNET="$HOME/.dotnet/dotnet"
else
  echo "ERROR: dotnet SDK not found. Re-run with --install-sdk to fetch a" >&2
  echo "       self-contained SDK into \$HOME/.dotnet, or install .NET 10 SDK." >&2
  exit 3
fi
export DOTNET_ROOT="$(dirname "$DOTNET")"
export PATH="$DOTNET_ROOT:$PATH"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
echo "dotnet: $("$DOTNET" --version) at $DOTNET"

# --- ensure vendored DLLs ---
if [[ "$do_fetch" == 1 ]]; then
  "$repo_root/tools/fetch-autodesk-refs.sh"
fi

proj_for() {
  case "$1" in
    revit) echo "$here/UsdAecoRevit.compilecheck.csproj" ;;
    navis) echo "$here/UsdAecoNavis.compilecheck.csproj" ;;
    *) echo "unknown target: $1" >&2; return 1 ;;
  esac
}

rc=0
for t in "${targets[@]}"; do
  csproj="$(proj_for "$t")"
  echo
  echo "=================================================================="
  echo "  compile-check: $t  (${csproj##*/})"
  echo "=================================================================="
  if "$DOTNET" build "$csproj" -c Release -v m -nologo -p:AddinsRepo="$ADDINS_REPO"; then
    echo "RESULT: $t PASS"
  else
    echo "RESULT: $t FAIL"
    rc=1
  fi
done

echo
if [[ "$rc" == 0 ]]; then echo "ALL COMPILE-CHECKS PASSED"; else echo "COMPILE-CHECK FAILURES (see above)"; fi
exit "$rc"
