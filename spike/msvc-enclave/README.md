# MSVC enclave — production `AecoLandingC.dll` (static USD monolith)

This directory builds the **production, self-contained** `AecoLandingC.dll` on
Windows/MSVC: the shippable native writer both AECO add-ins P/Invoke, exporting
**exactly the 19 `aeco_landing_*` symbols** (ABI v2, `aeco_landing_set_mesh` the
19th — aeco-meta #96) with **no external OpenUSD or CPython runtime dependency**. It is the Windows realisation of `nix/usd-embed.nix` +
aeco-core's `AECO_LANDINGC_BUILD_EMBED` stanza, and it exercises the second-TBB /
Arch-ctor risks the top-level `spike/README.md` defers to "the Windows enclave"
(the Arch-ctor path is retired here; second-TBB is characterised — one residual
`tbb.dll` — with the fix to fully retire it specified below).

It supersedes the recon's **Variant A** (`CMakeLists.txt` + `build_msvc.cmd` in
this same directory), which links the *shared* prebuilt USD (`usd_*.dll` +
`python311.dll` + `tbb.dll` on PATH) and leaks ~44 C++ `Aeco*` symbols through
the `.def` union. Variant A is validated end-to-end and fine for a dev/CI
compile-gate; this is the clean shippable form. See `RECON.md` for the recon
verdict and why Variant B (`.def` on shared USD) dead-ends at `LNK1120`.

## What it produces

- `usd_m.lib` — a **static, monolithic, python-free** OpenUSD, internal
  namespace `aecoEmbed_v1`, no imaging / usdImaging / tools / tests / plugins.
  Built from `C:\OpenUSD-src` reusing the prebuilt third-party under
  `C:\OpenUSD` (boost 1.86, TBB 2020.3) so the build stays ~1 day.
- `AecoLandingC.dll` — the C-ABI shim, `usd_m.lib` force-loaded whole-archive,
  compiled `PXR_STATIC` so `exports.def` is the complete export story.

## Recipe (example-navis)

```bat
:: 0. one-time: a private, patched copy of the pinned OpenUSD source
robocopy C:\OpenUSD-src C:\usd-embed-src /E /XD .git
powershell -ExecutionPolicy Bypass -File apply-embed-patches.ps1 -UsdSrc C:\usd-embed-src

:: 1. static monolith  ->  C:\usd-embed-build\usd_m.lib, installed to C:\usd-embed
::    (heavy: ~1700 TUs, 30-60 min; ~13 min on example-navis's 12 cores)
set USDSRC=C:\usd-embed-src
build-usd-monolith.cmd

:: 2. the DLL  (stage CMakeLists-embed.txt as CMakeLists.txt beside the aeco tree)
::    copy aeco-core's aeco\base + aeco\vendor beside CMakeLists.txt first
build-landingc-embed.cmd
```

`build-landingc-embed.cmd` ends by running `dumpbin /exports` and
`dumpbin /dependents` — the acceptance evidence.

## The three source mutations (`apply-embed-patches.ps1`)

1. **`patches/0001-work-loops-generic-parallel-for-tbb-range.patch`** —
   `pxr/base/work/loops.h`, the self-init `RangeType range = range;` fix.
2. **`pxrctor -> aecoctor` / `pxrdtor -> aecodtor`** in
   `pxr/base/arch/attributes.{h,cpp}` — gives the internally namespaced embed
   its own COFF constructor-registry section names so a stock USD loader
   callback does not run the embedded copy's ctors while its image is only
   partly loaded (the Arch static-ctor collision `spike/README.md` documents).
3. **`patches/0004-static-monolith-empty-export-msvc.patch` (MSVC-only, NEW)** —
   `cmake/macros/Private.cmake`. This is the load-bearing MSVC discovery.
   USD's monolithic build path targets the *shared* `usd_ms.dll` and therefore
   compiles every core library with `ARCH_EXPORT = __declspec(dllexport)`; it
   does **not** define `PXR_STATIC`. A **static** monolith `usd_m.lib` inherits
   those dllexport marks, and because a PE/COFF module-definition file UNIONS
   with (never subtracts) dllexport marks, whole-archiving `usd_m.lib` into the
   shim leaks the entire USD surface (~12k symbols) past `exports.def`. The
   patch makes the static monolith (`PXR_BUILD_MONOLITHIC=ON` +
   `BUILD_SHARED_LIBS=OFF`) compile with `PXR_STATIC=1` so `ARCH_EXPORT` is
   empty and nothing but the `.def` symbols is exported. On Nix this is
   unnecessary — the shim's version script / exported-symbols list SUBTRACTS at
   link, which PE/COFF cannot do — so it has no counterpart in `usd-embed.nix`.

`patches/0002-work-custom-impl-global-for-monolithic.patch` is **not** applied:
it only matters for a *custom* `PXR_WORK_IMPL` (the `workTaskflowExample`
`find_package` branch); this recipe uses the built-in `workTBB` backend.

## Work backend

`usd-embed.nix` selects `PXR_WORK_IMPL=workTaskflowExample` specifically to keep
oneTBB's dylibs out of the Nix closure. On Windows the reused TBB 2020.3 is
linked for USD's concurrent containers regardless (they live outside `libWork`),
so the taskflow detour buys nothing here — this recipe uses the **default
built-in workTBB** backend, matching how `C:\OpenUSD` itself was built.

## TBB — the one honest caveat

`dumpbin /dependents` on the finished DLL is clean of USD and CPython but **does
carry `tbb.dll`**. USD uses oneTBB/TBB concurrent containers and its Work
scheduler pervasively, and the third-party TBB reused from `C:\OpenUSD` (classic
TBB **2020.3**, interface 11103) ships **dynamic-only** — the `tbb.lib` beside it
is a pure import lib; there is no static `tbb.lib` variant and the 2020.3 win
package carries no build tree to make one. So the static monolith resolves TBB at
runtime through `tbb.dll`.

This is exactly the **second-TBB** item the top-level `spike/README.md` left
"to be exercised by the Windows enclave spike": the macOS coexistence spike also
kept TBB dynamic (`libtbb.12.dylib`). It is now exercised — the DLL is otherwise
fully self-contained, and `tbb.dll` is a single, well-behaved ~200 KB system-ish
dependency (not the `usd_*`/`python311` cloud Variant A drags in).

To retire `tbb.dll` entirely, rebuild the monolith against a **static** TBB:
`build_scripts/build_usd.py` at this rev already knows oneTBB v2021.12.0
(`InstallOneTBB`, CMake), which builds static with `-DBUILD_SHARED_LIBS=OFF
-DTBB_TEST=OFF`; point the monolith configure at that static `tbb.lib` (and its
`oneapi/tbb.h` include) and drop `tbb.dll` from `/dependents`. That is a second
full monolith rebuild against a newer TBB ABI (interface 12xxx vs 11103), so it
is called out as the follow-up rather than folded in here.

## Acceptance evidence

> **ABI note (v2 / aeco-meta #96).** aeco-core `main` is now **ABI v2**: a 19th
> cdecl symbol `aeco_landing_set_mesh` and `AECO_LANDING_C_ABI_VERSION = 2`. The
> managed interop enforces v2 at load, so v1 DLLs are refused. **Variant A has
> been rebuilt to v2 and validated** — `dumpbin /exports` shows **19**
> `aeco_landing_*` (incl `aeco_landing_set_mesh`), `aeco_landing_abi_version()`
> returns **2**, and the real `AecoLandingC.Interop` loader guard accepts it
> (`smoke-selfcontained.c` here is the v2 harness: 19 symbols, ABI v2). The
> **monolith** evidence recorded below is from the earlier **v1** build (18
> symbols, `abi_version()==1`); rebuilding the monolith against v2 source is the
> pending follow-up (the recipe is source-driven — no script change needed, only
> a re-run — because `set_mesh` lands in the already-compiled `landingBuilder.cpp`
> / `aecoLandingC.cpp` + one new `exports.def` line, adding no new TUs).

Built on example-navis (VS 2022 BuildTools 17.14 / MSVC 14.44, 12 cores). Monolith
`usd_m.lib` ≈ 1.02 GB (a whole-of-USD static archive; the DLL pulls only the
referenced subset + registry ctors via `/WHOLEARCHIVE`). `AecoLandingC.dll` =
**13,613,056 bytes (~13 MB)**.

**`dumpbin /exports`** — 21 names total:

- **All 18 `aeco_landing_*` symbols** (the complete ABI): `abi_version`,
  `add_relationship_by_id`, `apply_api`, `create`, `def_prim`, `def_prim_kv`,
  `destroy`, `export`, `is_valid`, `last_error`, `minted_id`, `over_prim`,
  `set_extent`, `set_quarantined_prop`, `set_semantic_attr_int`,
  `set_semantic_attr_string`, `set_semantic_attr_token`, `version`.
- **3 inert residual leaks** (vs **44** in Variant A):
  `__pxr_pegtl_workaround__` (a literal `ARCH_EXPORT int` global — a pegtl/MSVC
  compiler workaround), `Arch_GetExtraLogInfoReportDebugUnsafe`,
  `Tf_GetScopeDescriptionStackReportDebugUnsafe`. These three carry a **literal
  `ARCH_EXPORT` in USD source** (`build-workaround.cpp`, `stackTrace.cpp`,
  `scopeDescription.cpp`), not via the API-macro layer that `PXR_STATIC` empties,
  so they are unreachable by the static-monolith export patch, and a PE/COFF
  `.def` cannot subtract them. They are inert debug/workaround globals — **zero
  `Aeco*` writer-class methods leak** (that whole class of ~40 Variant-A leaks is
  gone). Suppressing the last three would need source edits at those 3 sites;
  left documented instead.

**`dumpbin /dependents`** — `tbb.dll`, `SHLWAPI.dll`, `dbghelp.dll`, `WS2_32.dll`,
`KERNEL32.dll`, `ADVAPI32.dll`, `MSVCP140.dll`, `VCRUNTIME140[_1].dll`,
`api-ms-win-crt-*`. **No `usd_*.dll`, no `python311.dll`.** Only non-system
dependency is `tbb.dll` (see above). Section table shows `.aecocto` — the renamed
`aecoctor` constructor-registry section, confirming the ctor-isolation patch.

**Standalone self-containment smoke** — from an isolated dir containing only
`AecoLandingC.dll` + `tbb.dll`, with `PATH` scrubbed to `C:\Windows\system32`
(no `C:\OpenUSD` anywhere): `LoadLibrary` succeeds, **18/18** `aeco_landing_*`
symbols resolve, `aeco_landing_abi_version()` returns **1** (ABI v1 guard),
`aeco_landing_version()` returns `0.1.0-dev`. This is the proof that Revit
full-export on example-revit (which lacks `C:\OpenUSD`) is unblocked.

### vs Variant A (shared-USD, dev-flavor)

| | Variant A (shared) | This (static monolith) |
|---|---|---|
| Size | 250,880 B (~250 KB) | 13,613,056 B (~13 MB) |
| Exports | 62 (18 aeco + **44** `Aeco*` leaks) | 21 (18 aeco + **3** inert) |
| USD dep | `usd_{tf,gf,vt,js,sdf,arch,python}.dll` | none |
| Python dep | `python311.dll` | none |
| TBB dep | `tbb.dll` | `tbb.dll` |
| Runtime needs `C:\OpenUSD` on PATH | yes | **no** |

## Rev note

`C:\OpenUSD-src` on example-navis is OpenUSD **0.26.5** (`PXR_VERSION 2605`, rev
`c42a0b49`). aeco-toolchain pins rev `47154dc` (**0.26.11-dev**). This recipe
builds the monolith from the on-disk 0.26.5 — the same source that produced the
validated shared `C:\OpenUSD`, so it compiles clean — which is the minor-version
skew `RECON.md` already flags as acceptable for the enclave. For byte-identity
parity with the Linux/Mac `usd-dev`, rebuild the monolith from the pinned
`47154dc` source (drop it at `C:\OpenUSD-src` and re-run the recipe unchanged).

## Lifetime caveat (carried from `spike/README.md`)

Arch registers process-lifetime loader callbacks with no unregister. Consumers
must load the shim once and keep it loaded until process exit (Revit/Navis
add-ins already do; they never `FreeLibrary` it).
