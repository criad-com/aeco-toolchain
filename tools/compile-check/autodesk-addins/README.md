# Off-Windows compile-check for the aeco Windows add-ins

Gives CI an **instant compile-check** of the Revit and Navisworks add-ins
**without a Windows host**, by compiling their sources (reference-only) against
the vendored Autodesk reference assemblies in
[`../../../vendor/autodesk-refs/`](../../../vendor/autodesk-refs/).

**This is compile-only.** The add-ins still only **run** on Windows
inside Revit / Navisworks. This gate catches syntax, type, and Autodesk-API-surface
regressions early; it does not (and cannot) exercise runtime behaviour.

## What it checks

| Project | Sources under `AddinsRepo` | TFM | Autodesk refs |
|---------|-------------|-----|---------------|
| `UsdAecoRevit.compilecheck.csproj` | `UsdAecoRevit` (+ `AecoLandingC.Interop`, `Aeco.Addins.Core`) | `net10.0-windows` | RevitAPI, RevitAPIUI |
| `UsdAecoNavis.compilecheck.csproj` | `UsdAecoNavis` (+ `AecoLandingC.Interop`, `Aeco.Addins.Core`) | `net48` | Autodesk.Navisworks.Api |

Each compile-check project compiles the add-in's `*.cs` **and** the
`AecoLandingC.Interop` `*.cs` in place (rather than via a cross-repo
`ProjectReference`), so the check is self-contained and isolates the single
question: *do the add-in sources still type-check against the Autodesk API?*

Select a checkout of the Revit and Navisworks add-in sources with
`--addins-repo`, the MSBuild property `AddinsRepo`, or the environment variable
`ADDINS_REPO`. The default is a sibling directory named `autodesk-addins`.

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
# Both add-ins; autodesk-addins assumed to be a sibling checkout of this repo.
tools/compile-check/autodesk-addins/run-compile-check.sh

# Install a local SDK first (no sudo) and fetch the DLLs from the hosts, then check:
tools/compile-check/autodesk-addins/run-compile-check.sh --install-sdk --fetch

# Select a checkout of the Revit and Navisworks add-in sources, Navis only:
tools/compile-check/autodesk-addins/run-compile-check.sh \
  --addins-repo ../autodesk-addins --navis-only
```

Or invoke a single project directly:

```bash
export ADDINS_REPO="$(cd ../autodesk-addins && pwd)"
dotnet build tools/compile-check/autodesk-addins/UsdAecoRevit.compilecheck.csproj \
  -c Release -p:AddinsRepo="$ADDINS_REPO"
```

### Knobs (MSBuild properties)

- `AddinsRepo` — a checkout of the Revit and Navisworks add-in sources (default:
  `ADDINS_REPO` if set, otherwise the sibling directory `autodesk-addins`).
- `VendorDir` — vendored-refs root (default: `vendor/autodesk-refs`).
- `RevitRefDir` / `NavisRefDir` — override a single product's ref dir.

## Verified result (2026-08-12)

Both projects compiled **0 warnings / 0 errors** on macOS arm64 with .NET SDK
10.0.400 against the vendored Revit 2027 (27.2.0.39) and Navisworks 2027
(24.0.1453.24) reference assemblies. No portability errors surfaced — the add-in
sources are clean for compile off-Windows.

## Wiring into CI

CI runs on the deployment service; it is not part of this repository.
