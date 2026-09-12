# Off-Windows compile-check for the aeco Windows add-ins

Gives fleet CI an **instant compile-check** of the Revit and Navisworks add-ins
**without a Windows host**, by compiling their sources (reference-only) against
the vendored Autodesk reference assemblies in
[`../../../vendor/autodesk-refs/`](../../../vendor/autodesk-refs/).

**This is loop #3: compile-only.** The add-ins still only **run** on Windows
inside Revit / Navisworks. This gate catches syntax, type, and Autodesk-API-surface
regressions early; it does not (and cannot) exercise runtime behaviour.

## What it checks

| Project | Source repo | TFM | Autodesk refs |
|---------|-------------|-----|---------------|
| `UsdAecoRevit.compilecheck.csproj` | `addins-codex/UsdAecoRevit` (+ `AecoLandingC.Interop`) | `net10.0-windows` | RevitAPI, RevitAPIUI |
| `UsdAecoNavis.compilecheck.csproj` | `addins-codex/UsdAecoNavis` (+ `AecoLandingC.Interop`) | `net48` | Autodesk.Navisworks.Api |

Each compile-check project compiles the add-in's `*.cs` **and** the
`AecoLandingC.Interop` `*.cs` in place (rather than via a cross-repo
`ProjectReference`), so the check is self-contained and isolates the single
question: *do the add-in sources still type-check against the Autodesk API?*

A third project, `usdaeco-codex/integrations/revit/UsdAecoRevit` (a separate
repo, `net10.0-windows` + WPF, no Interop dependency), was also verified to
compile cleanly against the same vendored Revit DLLs. It is not wired here
because it lives in a different repo; point a copy of the Revit compile-check at
it with `-p:AddinsRepo=`/`-p:RevitSrc=` if/when desired.

## Prerequisites

- **.NET SDK 10.x.** If absent, `run-compile-check.sh --install-sdk` fetches a
  self-contained SDK into `$HOME/.dotnet` using the official `dotnet-install.sh`
  (**no sudo**, nothing installed system-wide).
- **Vendored DLLs** under `vendor/autodesk-refs/`. If missing, run
  `tools/fetch-autodesk-refs.sh` (or pass `--fetch` below).

Cross-platform targeting works because:
- `net10.0-windows` (incl. WPF) restores the `Microsoft.WindowsDesktop.App.Ref`
  reference pack on macOS/Linux via `<EnableWindowsTargeting>true</EnableWindowsTargeting>`.
- `net48` compiles reference-only via the `Microsoft.NETFramework.ReferenceAssemblies.net48`
  package.

## Run it

```bash
# Both add-ins; addins-codex assumed to be a sibling checkout of this repo.
tools/compile-check/autodesk-addins/run-compile-check.sh

# Install a local SDK first (no sudo) and fetch the DLLs from the hosts, then check:
tools/compile-check/autodesk-addins/run-compile-check.sh --install-sdk --fetch

# Point at an addins-codex checkout elsewhere, Navis only:
tools/compile-check/autodesk-addins/run-compile-check.sh \
  --addins-repo /path/to/addins-codex --navis-only
```

Or invoke a single project directly:

```bash
dotnet build tools/compile-check/autodesk-addins/UsdAecoRevit.compilecheck.csproj \
  -c Release -p:AddinsRepo=/path/to/addins-codex
```

### Knobs (MSBuild properties)

- `AddinsRepo` — path to the `addins-codex` checkout (default: sibling of this repo).
- `VendorDir` — vendored-refs root (default: `vendor/autodesk-refs`).
- `RevitRefDir` / `NavisRefDir` — override a single product's ref dir.

## Verified result (2026-08-12)

Both projects compiled **0 warnings / 0 errors** on macOS arm64 with .NET SDK
10.0.400 against the vendored Revit 2027 (27.2.0.39) and Navisworks 2027
(24.0.1453.24) reference assemblies. No portability errors surfaced — the add-in
sources are clean for compile off-Windows.

## Wiring into CI

See [`.gitea/workflows/addins-compile-check.yml`](../../../.gitea/workflows/addins-compile-check.yml)
for a Linux runner job. Because the default policy does **not** commit the
proprietary DLLs, that job must either (a) `scp` them from the hosts via
`tools/fetch-autodesk-refs.sh` (runner needs keyless SSH), or (b) restore them
from an artifact store — see the policy note in
[`../../../vendor/autodesk-refs/README.md`](../../../vendor/autodesk-refs/README.md).
