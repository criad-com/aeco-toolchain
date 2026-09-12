# Vendored Autodesk reference assemblies

These are the Autodesk **reference assemblies** the aeco Windows add-ins compile
against, staged here so fleet CI can **compile-check the add-ins off-Windows**
(macOS/Linux) for instant feedback. They are consumed **reference-only**
(`<Reference Private=false>`): nothing is linked, copied into output, or
redistributed. **The add-ins still only _run_ on Windows** inside Revit /
Navisworks; this is a syntax/type/API-surface gate, loop #3 of the plan.

## Contents

| Path | Assembly | Size | AssemblyVersion | FileVersion | Source host |
|------|----------|------|-----------------|-------------|-------------|
| `revit-2027/RevitAPI.dll` | RevitAPI | 34,000,216 | 27.2.0.0 | 27.2.0.39 | example-revit |
| `revit-2027/RevitAPIUI.dll` | RevitAPIUI | 3,342,680 | 27.2.0.0 | 27.2.0.39 | example-revit |
| `navis-2027/Autodesk.Navisworks.Api.dll` | Autodesk.Navisworks.Api | 4,627,288 | 24.0.0.0 | 24.0.1453.24 | example-navis |

SHA256 sums are in `SHA256SUMS`; full metadata (product version, public key
token, image runtime) is in `MANIFEST.txt`. Host source paths:

- Revit: `example-revit:C:\Program Files\Autodesk\Revit 2027\`
- Navis: `example-navis:C:\Program Files\Autodesk\Navisworks Manage 2027\`

Only the assemblies actually named by the add-in `.csproj` files are vendored
(minimal footprint). The Revit add-ins reference `RevitAPI` + `RevitAPIUI`; the
Navis add-in references `Autodesk.Navisworks.Api` only (plus `System.Windows.Forms`,
which comes from the .NET Framework reference pack, not from Autodesk).

> **Navis version note:** Navisworks 2027 (product year) ships assembly major
> version **24**. This is expected — the Navis .NET API assembly version trails
> the product year. example-navis also carries a 2026 install; this vendored set pins the
> **2027 Manage** API.

## ⚠️ POLICY — proprietary binaries (decision needed)

These are **Autodesk proprietary binaries**.

- They must **never** be pushed to any **public** remote. The org Gitea
  (configured by the local registry) is local/private, but even so, committing large
  proprietary DLLs into a repo has license and repo-bloat implications.
- **Default in this repo: NOT committed.** `vendor/autodesk-refs/**` binaries are
  `.gitignore`d and fetched on demand by
  [`tools/fetch-autodesk-refs.sh`](../../tools/fetch-autodesk-refs.sh), which
  `scp`s them from the licensed hosts. Only the text metadata
  (`README.md`, `MANIFEST.txt`, `SHA256SUMS`, `.gitignore`) is tracked.

**Open question for the maintainer (raised in the PR):** do we

1. **keep the fetch-script model** (current default) — CI/devs run
   `tools/fetch-autodesk-refs.sh` to pull the DLLs from example-revit/example-navis at build
   time; nothing proprietary is ever committed; **or**
2. **commit the DLLs into this private repo** — simplest for CI (no SSH to the
   Windows hosts needed, hermetic), at the cost of ~40 MB of proprietary binaries
   in git history on the private Gitea; **or**
3. **a local artifact store** — publish the DLLs once to an internal artifact
   store / file share and have CI fetch from there (decouples CI from the live
   Windows hosts without putting binaries in git).

The compile-check works **either way** — it only needs the DLLs present under
this directory at build time, regardless of how they got there. To switch to
option 2, delete the `*.dll` ignore lines in `vendor/autodesk-refs/.gitignore`
and `git add` the DLLs.
