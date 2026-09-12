# Native dependency verification

Measured on 2026-09-11, aarch64-darwin, Nix 2.33.3. Commands use
`--max-jobs 4 --cores 6`. OpenUSD remains 0.26.11-dev-g47154dc; IfcOpenShell
remains 0.8.5, commit `16723d11cab9bc8a13b4e025a00d39445ccc462e`.
OCCT is the unchanged nixpkgs `opencascade-occt` 7.9.3 recipe.

| Check | Measured result |
|---|---|
| Source check.py | 3 checks, 0 failed |
| pytest | 49 passed, 1 skipped; optional aeco-core sibling is absent |
| Term sweep | 0 findings; the registry was address-allowlisted in this historical run |
| Package drift | 15/15 output paths unchanged, including all 13 legacy outputs and both native dependencies |
| OCCT build | PASS: substituted from cache.nixos.org in 8.62 s; 3 paths fetched, 44.6 MiB download, 168.5 MiB unpacked |
| OCCT size | Output NAR 166,111,344 bytes; closure 185,296,464 bytes across 11 store paths |
| OCCT linkage | PASS: libTKernel.dylib identifies libTKernel.7.9.dylib, compatibility 7.9.0, current version 7.9.3; dynamically uses system libc++ and libSystem |
| OCCT archive scan | PASS: 0 libTK*.a; 6 unrelated dependency archives, listed below |
| OCCT cache push | PASS in 4.44 s: 5 paths uploaded, 6 already cached; all 11 closure paths covered |
| IfcGeom build | PASS: compiled locally in 235.12 s; 328 targets; 16 prerequisite paths substituted from cache.nixos.org (20.0 MiB download, 90.0 MiB unpacked) |
| IfcGeom size | Output NAR 47,227,680 bytes; closure 453,734,056 bytes across 18 store paths |
| IfcGeom C++ smoke check | PASS in 16.56 s: 1 product, 8 vertices, 12 faces; CTest 1/1 passed; bounds 4 × 0.2 × 3 m |
| IfcGeom linkage | PASS: 67 direct OCCT dylib dependencies, all from the pinned 7.9.3 output; shared IfcGeom and IfcParse 0.8.5 |
| IfcGeom archives | 0 archives in its own output; transitive closure has the 6 OCCT dependency archives plus 2 Boost support archives; 0 static OCCT archives |
| IfcGeom cache push | PASS in 4.56 s: 4 paths uploaded, 14 already cached; all 18 closure paths verified by a recursive query to the local cache |
| OCCT consumer closure check | PASS: 74 transitive paths across OCCT, the C++ IfcGeom executable and usd-dev; 0 static OCCT archives |
| Full nix flake check | PASS: all 10 named aarch64-darwin checks, 0 failures; 1,295.70 s; one invocation at commit 615dc8a |
| Full-gate cache hits | 109 paths substituted from cache.nixos.org; the existing Taskflow USD and embedded USD variants built locally |
| CPU renders / coexistence | Both Work backends rendered 49-colour images; the shared/embedded USD coexistence probe passed |

## OCCT evidence

Output store basename: `2gbffh2ql78n3nbhzdari5mhnlh0ll49-opencascade-occt-7.9.3`.
Its NAR hash is `sha256-puSPzEk1meu9vzUSmm/XN4WBKbz98UR8/y6btO+DMFI=`;
the fetched output carries a cache.nixos.org signature.

`otool -L result-occt/lib/libTKernel.dylib` reports the OCCT output's
`lib/libTKernel.7.9.dylib` (compatibility 7.9.0, current version 7.9.3),
plus the system `libSystem.B.dylib` and `libc++.1.dylib`.

The complete `find $(nix path-info -r ./result-occt) -name '*.a'` scan finds:

| Dependency | Archive relative to its output |
|---|---|
| tcl-8.6.16 | lib/tdbc1.1.10/libtdbcstub1.1.10.a |
| tcl-8.6.16 | lib/libtclstub8.6.a |
| tcl-8.6.16 | lib/itcl4.3.2/libitclstub4.3.2.a |
| tk-8.6.16 | lib/libtkstub8.6.a |
| zlib-1.3.2-static | lib/libz.a |
| freetype-2.14.3 | lib/libfreetype.a |

These are dependency archives, not OCCT archives. The unchanged upstream
recipe retains them in its closure; no `libTK*.a` is present. The separate
consumer check also scans OCCT, IfcGeom's executable and usd-dev transitively.

## IfcGeom evidence

Output store basename: `ckyffr33njb9la0kkm2m720dwa3n0556-ifcopenshell-cpp-geom-0.8.5`.
Its NAR hash is `sha256-BzMTDEBiGKZcqGBNNDDiN4xjyehwmRB4lVa7/kIh1CM=`.
The library built from source; its source and most build inputs were already
local, and 16 remaining prerequisites were fetched from cache.nixos.org.

The installed CMake targets compile and link the fixture consumer. Its report is:

```text
IfcGeom extruded-wall products=1 vertices=8 faces=12
```

`otool -L result-ifcopenshell-cpp-geom/lib/libgeometry_kernel_opencascade.dylib`
lists shared `libIfcGeom.0.8.dylib` and `libIfcParse.0.8.dylib` (current version
0.8.5), shared Boost dependencies, and 67 OCCT libraries. These include
`libTKBool.7.9.dylib`, `libTKBO.7.9.dylib`, `libTKMesh.7.9.dylib`,
`libTKBRep.7.9.dylib` and `libTKernel.7.9.dylib`; every OCCT entry has
compatibility version 7.9.0 and current version 7.9.3.

The geometry output itself contains no static archive. Its closure adds
Boost's `lib/libboost_test_exec_monitor.a` and `lib/libboost_exception.a`
to the six archives listed above; none is an OCCT archive.

## Complete gate

The single full invocation ended with `all checks passed!` and exit status 0.
All eight existing checks passed: `pxr-import`, `usdrecord-embree`,
`usdrecord-embree-taskflow`, `ifcparse`, `extractor-deps`, `drift`,
`embed-spike` and `lintConventions`. Both added checks, `ifcgeom` and
`occt-shared`, also passed. All ten distinct check output paths were verified
present after completion. Nix's progress banner counted 20 scheduled check
requests; the flake declares ten distinct checks for this system.

The IfcParse probe counted one IfcRoot-derived entity; the extractor probe
reported Poppler 26.06.0, libzip 1.11.4 and a working liborcus XLSX reader.
Both CPU render reports read `renderer=Embree colors=49`. The coexistence
probe reported `embed coexistence spike OK` with separate USD namespaces.
Documentation-only evidence updates followed the full gate; no package recipe
or implementation changed after it.

## Reproduction

Set `PYTHON` to the supplied test environment's interpreter. No package
installation is needed. The launcher reads the cache and source mirror from
the external deployment registry selected by AECO_NIX_REGISTRY (see the README)
and preserves exact OpenUSD, nixpkgs and flake-utils
revisions. Builds run online against the configured local cache and
cache.nixos.org.

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" tools/nix-local.py build .#occt \
  -L --max-jobs 4 --cores 6 --out-link result-occt
env -u PYTHONPATH "$PYTHON" tools/nix-local.py build .#ifcopenshell-cpp-geom \
  -L --max-jobs 4 --cores 6 --out-link result-ifcopenshell-cpp-geom
env -u PYTHONPATH "$PYTHON" tools/nix-local.py build .#checks.aarch64-darwin.ifcgeom \
  -L --max-jobs 4 --cores 6 --out-link result-ifcgeom-check
env -u PYTHONPATH "$PYTHON" tools/nix-local.py flake check \
  -L --max-jobs 4 --cores 6
```

The configured Attic client published both complete closures. Upstream-cache
filtering was disabled so cache.nixos.org signatures did not cause uploads to
be skipped. A recursive query to the local cache verified all 11 OCCT paths
and all 18 geometry paths. To publish the same outputs again:

```sh
export NATIVE_CACHE="$(env -u PYTHONPATH "$PYTHON" -c 'import json, os; r=json.load(open(os.environ["AECO_NIX_REGISTRY"])); print(r["nixConfig"]["substituters"][-1].rsplit("/", 1)[-1])')"
attic push "$NATIVE_CACHE" --ignore-upstream-cache-filter -j 4 ./result-occt
attic push "$NATIVE_CACHE" --ignore-upstream-cache-filter -j 4 ./result-ifcopenshell-cpp-geom
```

## Deviations

The first focused C++ check exposed an incorrect fixture settings call:
the pinned API requires `get<WeldVertices>().value = true`, not
`set<WeldVertices>(true)`. That one-line correction passed the focused check;
the package recipes needed no changes.

Nix omitted the incompatible x86_64-linux system; native execution is proven
on aarch64-darwin only.

This processing hub retains its existing conventions linter. It does not adopt
the family schema skeleton; the family toolchain supplies that separate lint.
The optional sibling consumer test is skipped because that checkout is absent.
The local launcher replaces the obsolete cache setting with the authorized
local cache and cache.nixos.org. That run used a committed deployment registry;
version 0.4.0 moves deployment addresses outside the checkout and leaves a
public registry template. Input revisions and the OCCT recipe are unchanged.
