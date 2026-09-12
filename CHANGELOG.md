# Changelog

## 0.4.0 — 2026-09-12

- public names → github.com/criad-com.
- Add the MIT packaging licence with the family copyright attribution;
  retain all third-party notices and document the dependency licences.
- Point the unchanged OpenUSD revision at PixarAnimationStudios/OpenUSD:
  the deployment mirror has the identical commit and tree, with zero diff.
- Move deployment addresses to an external registry selected by
  AECO_NIX_REGISTRY. The committed template uses public sources; the term
  sweep checks it and permits only the exact public org slug and licence
  attribution.
- Verify 3 source checks, 0 failures; 55 pytest tests pass with 1 optional
  skip. The single Nix attempt evaluated 10 checks but was stopped when
  source-fetch builders accessed the network despite offline mode; full
  Nix validation is NOT PROVEN. See docs/public-packaging.md.

### Previously unreleased

- Complete the aarch64-darwin Nix gate: all 10 named checks pass in one
  1,295.70 s run, including both CPU renders and USD coexistence. Verify
  zero static OCCT archives across 74 consumer closure paths and retain
  all 15 package output paths. Remove the resolved native-build blocker.
- Build and publish IfcOpenShell 0.8.5 geometry: 235.12 s compilation,
  453,734,056-byte closure and 67 dynamic OCCT dependencies. Correct the
  smoke consumer's settings call for the pinned API; its wall tessellates
  into 8 vertices and 12 faces through the installed CMake targets.
- Verify OCCT 7.9.3 from cache.nixos.org: 8.62 s substitution, 185,296,464-byte
  closure, shared libTKernel and zero static OCCT archives. Select the current
  local Attic cache through the deployment registry for online native builds.
- Add OCCT 7.9.3, optional IfcOpenShell geometry and the native development shell.
- Add extruded-wall tessellation/dynamic-link and static-OCCT closure checks.
- Move cache/mirror deployment details to the allowlisted registry and local
  launcher; pin the existing nixpkgs and flake-utils revisions in source.
- Sanitize legacy examples, fixture notices and workflow configuration.

- Reframed convention B16 around authorship: processing repositories may not
  contain `schema.usda` or register schema types in `plugInfo.json`, while
  consuming generated schema resources from flake inputs is explicitly valid.
  Red fixtures now plant schema-type registration and retain `schema.usda`;
  clean fixtures cover generated resources and non-schema plugin types.
- Declared the studio Harmonia binary cache in the flake's `nixConfig` and
  documented opt-in flake trust plus permanent `nix.conf` configuration for
  managed fleet and runner machines.

## P5-T1 — Gate-T PDF and XLSX extractor dependencies

- Added `packages.poppler` (nixpkgs `poppler` 26.06.0, including its C++ API),
  `packages.libzip` (nixpkgs `libzip` 1.11.4), and `packages.liborcus`
  (nixpkgs `liborcus` 0.21.0) as separate consumable toolchain outputs.
- Chose liborcus for XLSX because it provides a read-capable C++ import filter
  and spreadsheet model. `xlnt` and `OpenXLSX` are absent from the pin, and
  `libxlsxwriter` is write-only.
- Worked around aarch64-darwin's stock `libixion` Python-extension link
  failure (unresolved Python C API symbols) by disabling the unused Python
  bindings in nixpkgs `libixion` and `liborcus`. The C++ libraries remain
  shared-only and otherwise retain the pinned nixpkgs recipes.
- Added a blocking C++ smoke check through `poppler-cpp`, `libzip`, and
  `liborcus-0.21`; it calls each linked library and rejects static archives.
- Kept the dependencies separate from both USD closures. libzip is
  BSD-3-Clause and liborcus/libixion are MPL-2.0. Poppler is
  GPL-2.0-or-later, so dynamic linking alone does not avoid GPL distribution
  obligations; consumers must adopt a compatible posture or an approved
  process-boundary design.

## P4-T1 — IfcOpenShell C++ parsing dependency

- Added `packages.ifcopenshell-cpp`, pinned to stable IfcOpenShell tag
  `ifcopenshell-python-0.8.5` at
  `16723d11cab9bc8a13b4e025a00d39445ccc462e`. The pinned nixpkgs only offers
  a Python package, marked broken on Darwin and coupled to the full geometry
  stack, so the C++ library is built directly from source.
- Chose IfcParse-only for representation-signature prototype dedup:
  `IfcRepresentationMap`/`IfcMappedItem` preserve reusable definition identity
  and occurrence transforms in the IFC graph, without tessellation. A future
  geometry-equivalence or mesh/BRep need is an explicit separate IfcGeom/OCCT
  output seam; OCCT is absent from this closure.
- Built IFC2X3, IFC4, and IFC4X3_ADD2 parsing into shared `libIfcParse` only,
  with headers and `IfcOpenShell::IfcParse` CMake export. Reused nixpkgs Boost
  1.89 dynamically; IfcParse does not require oneTBB. Python, conversion tools,
  IFCXML, HDF5, CGAL, OCCT, RocksDB, and static libraries remain off.
- Added a blocking downstream-style CMake smoke check. It links the exported
  target, parses a 554-byte hermetic IFC4 fixture, and counts one
  IfcRoot-derived entity. The same binary also parsed the read-only 6.9 MB
  `demo-datacentre-01.ifc` and counted 25,641 roots in 0.44s.
- Recorded LGPL-3.0-or-later notice handling under
  `THIRDPARTY_LICENSES/IfcOpenShell-LICENSE`; the output installs upstream's
  GPL/LGPL texts. Dynamic-only linkage preserves replacement/relink rights and
  avoids statically absorbing LGPL code into the proprietary consumer.
- On aarch64-darwin the standalone closure is 255,910,448 bytes (244.06 MiB).
  Its incremental closure beside either existing USD variant is 208,751,168
  bytes (199.08 MiB): `usd-dev` 1,732,470,104 → 1,941,221,272 bytes and
  `usd-dev-taskflow` 1,742,883,760 → 1,951,634,928 bytes. A cached-input
  compile/install took 2m13s.

## P3-T1 — headless CPU report imagery

- `packages.usd-dev` and `packages.usd-dev-taskflow` now build OpenUSD imaging,
  USD imaging, `usdAppUtils`/`usdrecord`, and the HdEmbree render delegate.
- Added nixpkgs Embree 4.4.1 (the pinned OpenUSD CMake requires Embree 4) and
  OpenSubdiv 3.7.0 (required by the imaging build); OpenSubdiv is propagated so
  downstream `find_package(pxr)` can resolve its generated dependency.
- Kept MaterialX, OpenImageIO, OpenColorIO, OpenVDB, PRMan, and `usdview` off.
  No Python package was added: `usdrecord` uses only OpenUSD modules and the
  standard library, while Jinja2 remains deliberately absent.
- Added blocking `usdrecord --disableGpu --renderer Embree` flake checks for
  both Work backends; each renders a cube and rejects a blank PNG.
- Patched HdEmbree's legacy-TBB scheduler workaround to skip its private
  workTBB header under custom Work implementations, keeping Taskflow buildable.
- Restored hermetic flake checks by removing a fixed host-path probe from the
  optional consumer lint test; ordinary sibling-checkout coverage remains.
- On aarch64-darwin, the default closure changed from 1,614,643,432 to
  1,732,470,208 bytes: +117,826,776 bytes (+112.37 MiB / +0.110 GiB).
  The Taskflow closure changed from 1,622,661,480 to 1,742,883,864 bytes:
  +120,222,384 bytes (+114.65 MiB / +0.112 GiB).

## P0-9 — aecoLintConventions (canon by CI)

- `tools/aecoLintConventions.py`: stdlib-only linter that holds the OpenUSD
  library canon (plan §3, design §4.8). Six rules, each documented in-file:
  `LIB-CANON` (exemplar file set + shape), `NAMING` (path-derived pxr include
  guards + `Aeco*` public-class prefix), `SCOPE` (`PXR_NAMESPACE_OPEN/CLOSE`
  pairing + `pxr/pxr.h` first-ish), `B16` (no `schema.usda`/
  `generatedSchema.usda`), `DIAG` (no bare `printf`/`fprintf(stderr)`/
  `std::cerr` on error paths, `// aeco-lint: allow-raw-output` honored),
  `PLUGINFO` (JSON well-formedness + `Types`/`Validators`/`Exec` structure).
  Guard derivation matches the reviewed skeleton (`aecoBase`→`AECOBASE`
  package token, filename camelCase split: `debugCodes`→`DEBUG_CODES`).
- `tools/tests/`: a clean canonical fixture (`fixtures/clean`) plus a
  planted-violation table (35 red fixtures, one violation each,
  message-substring asserted) driving a python `unittest` suite that asserts
  every rule reds with its id (and only its id), the clean tree passes, and
  the aeco-core skeleton passes as-is.
- `checks.lintConventions`: runs the linter over this repo and its unittest
  suite in `nix flake check` (hermetic, python-only). README documents how
  consumer repos wire the same linter from this repo as a flake input.
- Validated against the reviewed consumer (aeco-core packet/2): clean, zero
  findings — no defects surfaced, no over-strictness to tune.
- Scope decision (post-P0-4 rebase): per-library rules govern `pxr_library`
  dirs under `aeco/` only; standalone harness code (`spike/`, like `testenv/`)
  is exempt by design — its stdout/stderr is its interface. Documented in the
  DIAG docstring, pinned by a regression test; linter verified clean over the
  post-rebase tree including `spike/`.
- Review hardening (cross-pool review on PR #3 — six constructed evasions,
  each now a permanent fixture): C++-phase-ordered lexer (backslash-newline
  splice before comment/string removal; raw-string literals; the allow marker
  honored only from genuine comments; digit separators); DIAG matches across
  physical lines on the lexed buffer; discovery matches `pxr_library`
  case-insensitively (CMake command names are), reports library-shaped dirs
  with no parseable call as LIB-CANON findings instead of silence, and no
  longer prunes `cmake`/`result*` under `aeco/`; NAMING verifies the guard as
  the file's structural outer frame (first directive `#ifndef`, then its
  `#define` — a dead `#if 0` pair no longer satisfies); SCOPE requires
  `pxr/pxr.h` to exist in public class headers and evaluates pairing on the
  stripped buffer; LIB-CANON enforces both directions of the
  module.cpp/`__init__.py` iff and flags omitted/unlisted `DOXYGEN_FILES`
  (fused api.h fixture split four ways). Rev-2 follow-up: the guard must
  actually ENCLOSE the file — conditional nesting is tracked and the outer
  #endif must be the last directive with nothing substantive after it, so a
  degenerate `#ifndef/#define/#endif`-up-front guard reds (inner conditional
  ladders like api.h's `PXR_STATIC` still pass). Suite now 48 tests, incl. 6
  clean-side evasion counter-cases.

## P0-4 — usd-embed and coexistence spike

- `packages.usd-embed`: static, monolithic, python-free OpenUSD under
  `aecoEmbed_v1`, with imaging/tools/tests/examples disabled and Sdf plugin
  resources installed.
- Static PIC form of `workTaskflowExample` for the embed closure, plus the
  required custom-work monolithic target-scope fix.
- Isolated Arch constructor/destructor sections for the embedded copy so a
  stock USD dyld callback cannot initialize it during a partial image load.
- `packages.embed-shim` and `packages.embed-host`, with a two-layer,
  two-namespace coexistence harness wired as `checks.embed-spike`.
- Measured macOS linkage, size, export-surface, and second-TBB risk report in
  `spike/README.md`.

## P0-1 — initial toolchain flake

- Flake input `openusd` pinned to `aeco/openusd` @ `47154dc7b5e2` (dev, 0.26.11).
- `packages.usd-dev`: OpenUSD core build (shared, python3, no imaging, C++17)
  on the upstream TBB Work backend; `packages.usd-dev-taskflow` variant on
  taskflow 3.10.0 (`PXR_WORK_IMPL=workTaskflowExample`) for the future
  usd-embed (decision record: README "Work backend"). oneTBB propagated so
  downstream `find_package(pxr)` resolves `find_dependency(TBB)`.
- `patches/0001`: fixes the upstream generic (non-TBB) `WorkParallelForTBBRange`
  fallback in `pxr/base/work/loops.h` (self-initialised range + lvalue passed
  to an rvalue-ref ctor), which only compiles under a custom `PXR_WORK_IMPL`.
- `packages.openusd-src`: verbatim pinned source tree.
- `cmake/pxr-macros/`: byte-exact replica of the pinned source's
  `cmake/macros/` + `cmake/defaults/` (including the macro support files
  `testWrapper.py`, `compilePython.py`, `moduleDeps.cpp.in`, `shebang.py`,
  `test.pre.js`); `tools/drift-check.sh` compares every file, both
  directions (also wired as a flake check, next to the pxr import smoke test).
- `devShells.default`: cmake, ninja, pkg-config, python3, usd-dev with
  PYTHONPATH/PATH wired for `from pxr import Usd`.
