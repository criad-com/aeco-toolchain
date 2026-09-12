# aeco-toolchain

Toolchain hub for the AECO org (Nix-first). Pins the org-wide OpenUSD source
and provides the canonical OpenUSD build every downstream repo consumes.

Version: **0.4.0**. Public repository: [criad-com/aeco-toolchain](https://github.com/criad-com/aeco-toolchain).

Pinned OpenUSD: `PixarAnimationStudios/OpenUSD` @ `47154dc7b5e28df623745495a7a508b69535ba24`
(dev, post-26.08). Target platform: aarch64-darwin (structured for
x86_64-linux later). The deployment mirror is identical to upstream at this
revision; see the [source comparison](docs/public-packaging.md).

## Build and check

From a checkout, with Python and pytest already available:

```sh
export PYTHON=python3
env -u PYTHONPATH "$PYTHON" check.py
nix flake check --no-write-lock-file
```

The source gate runs the hub conventions linter, pytest and the term sweep,
then prints `N checks, M failed`. Tests import directly from the source tree;
no package installation or setuptools is needed. The generic processing hub
uses its own conventions linter; the family schema skeleton and structure lint
belong to the separate `usdaeco-toolchain` kit. Current release validation is
recorded in [public packaging verification](docs/public-packaging.md).

## Binary cache

The [local launcher](tools/nix-local.py) reads the public
[registry template](nix/registry.json) by default. To use a Gitea source mirror
and a local binary cache, copy the template outside the checkout, replace its
`to.url` and `nixConfig` values, and set `AECO_NIX_REGISTRY` to that copy.
Keep deployment addresses and cache keys in the external file. Use the
launcher when the daemon trusts this user or the configured substituter.
Cache trust remains a machine configuration decision.

Public inputs are pinned by revision. The local registry supplies an explicit
override without placing deployment addresses in source code or documentation:

```sh
export PYTHON=python3
export AECO_NIX_REGISTRY="$HOME/.config/aeco/registry.json"
export OPENUSD_OVERRIDE="$(env -u PYTHONPATH "$PYTHON" -c 'import json, os; d=json.load(open(os.environ["AECO_NIX_REGISTRY"])); print("git+"+d["flakes"][0]["to"]["url"])')"
nix flake check --accept-flake-config --no-write-lock-file \
  --override-input openusd "$OPENUSD_OVERRIDE?ref=dev&rev=47154dc7b5e28df623745495a7a508b69535ba24"
```

Local lockfiles stay uncommitted. The OpenUSD and nixpkgs revisions are preserved
when applying the mirror override.

The same command with the cache and mirror selected automatically is:

```sh
env -u PYTHONPATH "$PYTHON" tools/nix-local.py flake check -L
```

## Flake outputs

- `packages.usd-dev` — shared OpenUSD with python3 bindings, imaging,
  USD imaging, HdEmbree, and `usdrecord`; no usdview/tests/examples/docs,
  C++17, upstream TBB Work backend. Carries pin-local build fixes
  (see `patches/`).
- `packages.usd-dev-taskflow` — same build with the taskflow Work backend
  (see "Work backend" below).
- `packages.ifcopenshell-cpp` — IfcOpenShell 0.8.5's shared C++ `libIfcParse`
  with IFC2X3, IFC4, and IFC4X3_ADD2 schemas; no Python, IfcGeom, OCCT, or
  CGAL closure. Exports the `IfcOpenShell::IfcParse` CMake target.
- `packages.occt` — nixpkgs OCCT **7.9.3**, shared libraries; see the native geometry section.
- `packages.ifcopenshell-cpp-geom` — optional shared IfcGeom and OCCT kernel,
  using the same IfcOpenShell 0.8.5 source and IFC schemas as the parsing leaf.
- `devShells.native` — CMake, Ninja, compiler, usd-dev and OCCT for native plugins.
- `packages.poppler` — nixpkgs Poppler, including the shared C++ PDF API and
  its `poppler-cpp` pkg-config module.
- `packages.libzip` — nixpkgs's shared ZIP container library, with the
  `libzip::zip` CMake target and `libzip` pkg-config module.
- `packages.liborcus` — nixpkgs's shared C++ spreadsheet import library with
  XLSX support; Python bindings are disabled for the Gate-T C++ consumer.
- `packages.usd-embed` — static monolithic, python-free OpenUSD under the
  `aecoEmbed_v1` internal namespace, without imaging, tools, tests, or
  examples. It includes the Sdf `plugInfo.json` resource tree.
- `packages.embed-shim` — the coexistence spike's C-ABI dylib, with
  `usd-embed` and the taskflow work backend absorbed statically.
- `packages.embed-host` — a stock shared-`usd-dev` host that dynamically loads
  the shim and verifies both USD copies can author and parse layers in one
  process.
- `packages.openusd-src` — the pinned OpenUSD source tree, verbatim.
- `packages.taskflow`, `packages.workTaskflowExample` — supporting deps.
- `devShells.default` — cmake/ninja/pkg-config/python3 + usd-dev, wired so
  `python3 -c "from pxr import Usd"` works out of the box.
- `checks` — pxr python import smoke test, headless HdEmbree render tests for
  both Work backends, C++ IfcParse and Gate-T dependency link tests,
  IfcGeom tessellation and shared-OCCT closure checks, macro-replica drift,
  conventions linter, and the two-USD
  `embed-spike` coexistence test. See [`spike/README.md`](spike/README.md) for
  the embed closure report and platform caveats.

## IfcOpenShell C++ (P4-T1)

`packages.ifcopenshell-cpp` is a heavy extractor dependency kept separate
from `usd-dev` and `usd-dev-taskflow`. The pinned nixpkgs has no top-level
`ifcopenshell` package: its only recipe is
`python3Packages.ifcopenshell` 0.8.0, which is marked broken on Darwin and
builds the Python wrapper around the full OCCT/CGAL geometry stack. This flake
therefore builds stable IfcOpenShell 0.8.5 directly from commit
`16723d11cab9bc8a13b4e025a00d39445ccc462e` (release tag
`ifcopenshell-python-0.8.5`; the tag covers the monorepo's C++ sources too).

The scope is deliberately **IfcParse-only**. Prototype identity can be
derived without tessellation: `IfcMappedItem.MappingSource` names a reusable
`IfcRepresentationMap`/mapped representation, while `MappingTarget` carries
the occurrence transform. Direct shape representations can use a canonical
hash of their `IfcShapeRepresentation.Items` reference graph. That signature
detects reused IFC definitions—the instancing question—without asking whether
two independently modelled solids become geometrically equivalent after
boolean evaluation. Tolerance-based equivalence and mesh/BRep conversion use the separate
`ifcopenshell-cpp-geom` output. Geometry never enters this parsing leaf's closure.

The output contains headers under `include/ifcparse`, shared
`lib/libIfcParse`, and upstream's CMake package. Downstream Nix CMake builds
use it as follows (the propagated Boost 1.89 pin is placed on
`CMAKE_PREFIX_PATH` automatically):

```cmake
find_package(IfcOpenShell CONFIG REQUIRED)
target_link_libraries(aecoExtractIfc PRIVATE IfcOpenShell::IfcParse)
```

Non-Nix builds may set
`IfcOpenShell_DIR=<prefix>/lib/cmake/IfcOpenShell`. IfcParse does not use TBB,
so no second oneTBB enters this closure; its Boost libraries are the same
nixpkgs 1.89 pin and are dynamically linked.

IfcOpenShell is LGPL-3.0-or-later. `libIfcParse` is shared-only—there is no
static archive—so the proprietary consumer remains a dynamically linked
application and an interface-compatible replacement library can be used. A
redistribution must retain
`THIRDPARTY_LICENSES/IfcOpenShell-LICENSE`, the upstream GPL/LGPL notices
installed under `share/licenses/IfcOpenShell`, the source offer/access, and
the LGPL's reverse-engineering/replacement rights.

The blocking check compiles through `IfcOpenShell::IfcParse`, parses the tiny
554-byte hermetic `tests/ifcparse-smoke/minimal.ifc`, and reports exactly one
IfcRoot-derived entity. A supplemental read-only studio run parsed the 6.9 MB
`demo-datacentre-01.ifc` and counted 25,641 IfcRoot-derived entities in 0.44s.

On aarch64-darwin, `nix path-info -S` reports a standalone closure of
255,910,448 bytes (244.06 MiB). Adding it beside either existing USD variant
adds 208,751,168 bytes (199.08 MiB) after shared runtime paths: `usd-dev`
1,732,470,104 → 1,941,221,272 bytes; `usd-dev-taskflow` 1,742,883,760 →
1,951,634,928 bytes. A source/dependency-cached compile and install took
2m13s on the studio aarch64-darwin builder.

## Native geometry

OCCT is nixpkgs `opencascade-occt` **7.9.3**, with its recipe unchanged. It is
LGPL-2.1 with the upstream exception; **dynamic linking only**. Preserve the
upstream licence notices and replacement rights when redistributing it.
The geometry output builds shared IfcParse, IfcGeom, schema mappings and
`geometry_kernel_opencascade`; CGAL, converters and Python wrappers are disabled.
IfcOpenShell remains LGPL-3.0-or-later. Its notices are installed with both
parsing and geometry outputs.

```sh
env -u PYTHONPATH "$PYTHON" tools/nix-local.py build .#occt -L --max-jobs 4 --cores 6
env -u PYTHONPATH "$PYTHON" tools/nix-local.py build .#ifcopenshell-cpp-geom -L --max-jobs 4 --cores 6
env -u PYTHONPATH "$PYTHON" tools/nix-local.py develop .#native
```

Consume the geometry target through its installed CMake package:

```cmake
find_package(IfcOpenShell CONFIG REQUIRED)
target_link_libraries(myGeometryTool PRIVATE
    IfcOpenShell::IfcGeom IfcOpenShell::geometry_kernel_opencascade)
target_compile_definitions(myGeometryTool PRIVATE IFOPSH_WITH_OPENCASCADE IFC_SHARED_BUILD)
```

`checks.ifcgeom` compiles an actual iterator consumer against the exported
package and tessellates [a tiny extruded wall](tests/ifcgeom-smoke/wall.ifc). It
checks one product, 8 welded vertices, 12 triangles, finite coordinates, valid
indices and 4 × 0.2 × 3 metre bounds. The result prints the counts. Darwin's
`otool -L` must show dynamically linked libTK libraries; Linux uses ldd.
`checks.occt-shared` scans the transitive closure of OCCT, the test executable
and usd-dev and rejects static OCCT archives. The family toolchain also scans
its native template closure.

The hub remains a processing repo with its existing conventions linter; it
does not carry a family schema. Source checks run without installing a package:

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q tools/tests
```

Measured on aarch64-darwin; both dependency closures are published in the
local Attic cache:

| Output / check | Result |
|---|---|
| OCCT 7.9.3 | Substituted from cache.nixos.org in 8.62 s; 185,296,464-byte closure; shared libraries; 0 static OCCT archives |
| IfcOpenShell 0.8.5 geometry | Built in 235.12 s; 453,734,056-byte closure; 67 dynamic OCCT dependencies |
| C++ IfcGeom wall | PASS: 1 product, 8 vertices, 12 faces; 4 × 0.2 × 3 m bounds |
| Cache publication | OCCT: 11/11 closure paths available; geometry: 18/18 |
| Full Nix gate | PASS: 10/10 named checks in 1,295.70 s; both CPU renders contain 49 colours |
| Source gate | 3 checks, 0 failed; pytest 49 passed, 1 optional sibling skip; term sweep 0 findings |

`check.py --nix` also builds all flake checks through the local launcher. Source
checks alone establish neither native compilation nor tessellation. See
[verification](docs/native-verification.md) for measured results and deviations.

## Gate-T document and workbook dependencies (P5-T1)

The PDF and XLSX extractor libraries are separate package outputs, just like
`packages.ifcopenshell-cpp`; none enters either USD package's closure:

- `packages.poppler` maps to nixpkgs `poppler` 26.06.0. This derivation already
  enables the C++ frontend and provides shared `libpoppler-cpp` plus the
  `poppler-cpp` pkg-config module, so no second C++ package is necessary.
- `packages.libzip` maps to nixpkgs `libzip` 1.11.4. It provides shared
  `libzip`, headers, pkg-config metadata, and the `libzip::zip` CMake target.
- `packages.liborcus` is nixpkgs `liborcus` 0.21.0, with its nixpkgs
  `libixion` dependency, configured C++-only and shared-only. liborcus was
  chosen because it has an actual C++ XLSX import filter and spreadsheet
  model. The pinned nixpkgs has neither `xlnt` nor `OpenXLSX`, while
  `libxlsxwriter` writes workbooks but does not read them.

The C++-only override is required on aarch64-darwin: stock nixpkgs
`libixion` 0.20.0 tries to link its optional Python extension without the
Python C API and fails with unresolved `_Py*` symbols; stock `liborcus` then
fails through that dependency. `--disable-python` removes only bindings the
C++ extractor does not consume. Both corrected packages build shared
libraries and retain the nixpkgs source/version/dependency pins.

A downstream Nix build consumes the packages through the one toolchain input:

```nix
buildInputs = [
  aeco-toolchain.packages.${system}.poppler
  aeco-toolchain.packages.${system}.libzip
  aeco-toolchain.packages.${system}.liborcus
];
```

Poppler and liborcus expose pkg-config modules `poppler-cpp` and
`liborcus-0.21`; libzip additionally exports `libzip::zip` for CMake. The
`extractor-deps` check compiles against all three public interfaces, calls
symbols from each shared library, and rejects static archives in the exposed
outputs.

The packages stay at arm's length as dynamically linked libraries. libzip is
BSD-3-Clause; liborcus and libixion are MPL-2.0. Poppler is
GPL-2.0-or-later, not LGPL: dynamic linking does not remove its GPL
obligations. A distributed `aecoExtractDoc` that links `libpoppler-cpp` must
therefore use a GPL-compatible distribution posture; if that is unacceptable,
the product architecture needs an approved process boundary rather than
assuming the IfcOpenShell LGPL analysis applies unchanged.

## Headless CPU rendering

Both `usd-dev` variants carry the minimal stack required by this OpenUSD pin
for report imagery:

- `PXR_BUILD_IMAGING=ON`, `PXR_BUILD_USD_IMAGING=ON`,
  `PXR_BUILD_EMBREE_PLUGIN=ON`, `PXR_ENABLE_GL_SUPPORT=ON`, and
  `PXR_BUILD_USD_TOOLS=ON` provide Hydra, `usdImagingGL`, HdEmbree,
  `usdAppUtils`, and `usdrecord`.
- nixpkgs Embree 4.4.1 is used because the pin explicitly calls
  `find_package(Embree 4 REQUIRED CONFIG)`; Embree 3 is incompatible with that
  requirement.
- OpenSubdiv 3.7.0 is required by every imaging build and is propagated for
  the installed `pxrConfig.cmake` dependency.
- OpenGL remains enabled because this revision gates `hdSt`/`hdx`—and thus
  `usdImagingGL`/`usdrecord`—on it even for CPU rendering. `--disableGpu`
  prevents creation or use of a GPU context at runtime.
- A narrow source patch guards HdEmbree's legacy-TBB scheduler workaround on
  the presence of its workTBB-private header. The pin otherwise includes that
  uninstalled header under custom Work implementations, breaking Taskflow.
- MaterialX, OpenImageIO, OpenColorIO, OpenVDB, PRMan, Metal, and `usdview`
  remain disabled. Jinja2 also remains absent: `usdrecord` needs no Python
  packages beyond the OpenUSD bindings and Python standard library.

The blocking smoke tests author a small cube in
`tests/usdrecord-embree/cube.usda` and run both Work variants. To reproduce
the default variant directly:

```sh
nix develop
usdrecord --disableGpu --renderer Embree \
  tests/usdrecord-embree/cube.usda cube.png
```

Measured on aarch64-darwin, the default `usd-dev` closure grows by 112.37 MiB
(1,614,643,432 → 1,732,470,208 bytes), while `usd-dev-taskflow` grows by
114.65 MiB (1,622,661,480 → 1,742,883,864 bytes). Both are well below the
2 GiB escalation threshold. The first uncached default build took 10m53s on a
12-job host; a fully uncached check building both variants concurrently took
20m15s.

## Work backend (rule E23 — decision record)

`libWork` scheduling is parameterised (`workImpl` in `nix/usd-dev.nix`):

- **`usd-dev` (default): upstream TBB (`workTBB`, `PXR_WORK_IMPL` unset).**
  Reason: the upstream default and the configuration Pixar builds and tests;
  downstream org repos should consume the least-surprising binary.
- **`usd-dev-taskflow`: taskflow 3.10.0 via `PXR_WORK_IMPL=workTaskflowExample`.**
  Reason: kept building and reachable alongside `usd-embed`, which uses the
  same backend for its static monolith.

Measured nuance: choosing taskflow does NOT drop TBB from the closure —
tf/vt/trace/plug use TBB concurrent containers directly, so oneTBB is a hard
dependency of both variants; the Work backend only changes the scheduler.
HdEmbree's legacy-TBB scheduler workaround is disabled for Taskflow by the
pin-local compatibility patch described above.

## cmake/pxr-macros

Byte-exact replica of the pinned source's `cmake/macros/` and
`cmake/defaults/` directories: the `*.cmake` files plus the support files the
macros reference by sibling path (`testWrapper.py`, `compilePython.py`,
`moduleDeps.cpp.in`, `shebang.py`, `test.pre.js`). `tools/drift-check.sh`
verifies the replica against `packages.openusd-src` — every file, both
directions (non-zero exit + diff on any drift). Never edit the replica by
hand; re-copy from the pinned source.

## aecoLintConventions

`tools/aecoLintConventions.py` holds the OpenUSD library canon mechanically
(plan §3, design §4.8) — stdlib-only python, no third-party imports:

```sh
python3 tools/aecoLintConventions.py <repo-root> [--lib <path>]*
```

Exit 0 clean, 1 on findings (`file:line: RULE-ID: message`). Rules:
`LIB-CANON` (exemplar file set: `api.h` export macros, `overview.dox`,
`module.cpp`/`__init__.py` when a python surface is declared, `testenv/`);
`NAMING` (path-derived pxr include guards + `Aeco*` class prefix in public
headers); `SCOPE` (`PXR_NAMESPACE_OPEN/CLOSE_SCOPE` paired, `pxr/pxr.h` first
among project includes); `B16` (no authored `schema.usda` or schema-type
registration in `plugInfo.json`; generated schema resources may be consumed
from flake inputs);
`DIAG` (no bare `printf`/`fprintf(stderr)`/`std::cerr` on error paths — the
`// aeco-lint: allow-raw-output` comment is an escape hatch); `PLUGINFO`
(every `plugInfo.json` parses and carries the keys its `Types`/`Validators`/
`Exec` registries need). Grep-class C++ rules run on a buffer lexed in the
compiler's phase order (splice, then comments/strings/raw-strings), so legal
formatting can neither evade nor false-positive them; include guards are
verified as the file's structural outer frame; discovery is case-insensitive
and loud (a library-shaped dir with no parseable `pxr_library` is a finding).
Tests: `python3 tools/tests/test_lint_conventions.py` (35 single-violation
red fixtures incl. the PR #3 review's six constructed evasions, + clean-side
counter-cases). Wired as the `lintConventions` flake check (linter over this
repo + the unittest suite).

Scope: the per-library rules govern `pxr_library` dirs under `aeco/` — the
canon's own scope. Harness code (`testenv/` drivers, standalone spike/probe
executables like `spike/`) is exempt by design: its stdout/stderr is its
interface (decision recorded in the DIAG rule's docstring, pinned by test).

**Wiring it in a consumer repo.** Consumers add this repo as a flake input
(they already do, for `usd-dev`) and call the linter from its tree in a flake
check — the toolchain stays the single source of the linter:

```nix
# flake.nix, in checks.<system>:
lintConventions = pkgs.runCommandLocal "check-lint-conventions"
  { nativeBuildInputs = [ pkgs.python3 ]; } ''
    python3 ${aeco-toolchain}/tools/aecoLintConventions.py ${self}
    touch $out
  '';
```

`${aeco-toolchain}` is the input's source tree; `${self}` is the consumer repo
being linted. This runs as an H0 check on every PR (plan §2). aeco-core
(the reviewed walking skeleton) passes as-is.

## Consuming from another repo

```nix
inputs.aeco-toolchain.url = "github:criad-com/aeco-toolchain?ref=v0.4.0";
# then: aeco-toolchain.packages.${system}.usd-dev
#       aeco-toolchain.packages.${system}.ifcopenshell-cpp
#       aeco-toolchain.packages.${system}.poppler
#       aeco-toolchain.packages.${system}.libzip
#       aeco-toolchain.packages.${system}.liborcus
#       aeco-toolchain.packages.${system}.openusd-src
```

usd-dev propagates oneTBB: the installed `pxrConfig.cmake` runs
`find_dependency(TBB ... CONFIG)`, so TBB must be findable wherever
`find_package(pxr)` runs. Putting `usd-dev` in `buildInputs` (or using the
devShell) is enough — nix places the propagated TBB on `CMAKE_PREFIX_PATH`.
Non-nix consumers must set `TBB_DIR` themselves.

Fetching the private mirrors requires a `~/.netrc` entry for the configured Git service.

## Off-Windows compile-check for the Windows add-ins (P4)

`tools/compile-check/autodesk-addins/` compiles the `addins-codex` Revit and
Navisworks add-ins **reference-only** against **vendored Autodesk reference
assemblies**, on macOS/Linux — no Windows host — giving the fleet an instant
compile gate. The add-ins still only **run** on Windows; this is compile-only.

- `tools/fetch-autodesk-refs.sh` — scp's `RevitAPI.dll`/`RevitAPIUI.dll` (Revit
  2027, example-revit) and `Autodesk.Navisworks.Api.dll` (Navisworks 2027, example-navis) into
  `vendor/autodesk-refs/`.
- `tools/compile-check/autodesk-addins/run-compile-check.sh` — builds both add-ins
  (`net10.0-windows` Revit via `EnableWindowsTargeting`; `net48` Navis via the
  Framework reference pack). `--install-sdk` fetches a no-sudo .NET 10 SDK into
  `$HOME/.dotnet`; `--fetch` pulls the DLLs first.

**Policy — proprietary binaries:** the Autodesk DLLs are **not committed** by
default (`vendor/autodesk-refs/**/*.dll` is gitignored; fetched on demand). See
[`vendor/autodesk-refs/README.md`](vendor/autodesk-refs/README.md) for the
open decision (fetch-script vs. commit-into-private-repo vs. artifact store).

## Licence

The hub's original code and packaging are MIT licensed; see [LICENSE](LICENSE).
Third-party sources, patches and dependencies retain their own notices and
licences. The packaging licence does not replace those terms.

| Component | Licence and retained notices |
|---|---|
| OpenUSD and copied CMake helpers | Upstream OpenUSD licence; copyright and licence headers in `cmake/pxr-macros/` remain intact |
| OCCT | LGPL-2.1 with the upstream exception; dynamic linking only; preserve the upstream notices shipped by the unchanged nixpkgs recipe |
| IfcOpenShell | LGPL-3.0-or-later; imported dependency, with shared C++ linkage here; [retained notice](THIRDPARTY_LICENSES/IfcOpenShell-LICENSE) and upstream COPYING/COPYING.LESSER installed by both packages |
| Poppler | GPL-2.0-or-later; see the extractor dependency distribution notes above |
| libzip | BSD-3-Clause |
| liborcus / libixion | MPL-2.0 |

Autodesk reference assemblies remain uncommitted and separately licensed;
see [vendor metadata](vendor/autodesk-refs/README.md).
