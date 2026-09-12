# MSVC-enclave feasibility recon — `aecoLandingC.dll` on example-navis

Packet: P4 `p4-msvc-enclave-recon`. Date: 2026-08-12. Host: **example-navis**
(Windows 10.0.26200), VS 2022 BuildTools 17.14.28 / MSVC 14.44.35207,
cmake 4.3.1, Python 3.11, 12 cores. Keyless SSH as `AECO`.

## Verdict (order of magnitude)

- **A loadable `AecoLandingC.dll` exporting the full 18-symbol `aeco_landing_*`
  ABI can be built on example-navis in ~1 HOUR**, because a complete prebuilt OpenUSD
  already exists at `C:\OpenUSD`. This was DONE during recon (see "Build
  progress"). It is a *dev-flavor* DLL: it links the shared USD DLLs and its
  export table also carries the ~44 leaked C++ `Aeco*` symbols (the documented
  MSVC `.def`-union effect). Functionally complete for P/Invoke — the managed
  side binds the 18 by name — but not the clean two-symbol image.
- **The PRODUCTION-shape DLL (exactly 18 exports, self-contained, no external
  USD/CPython in its closure) is a ~1-DAY effort**, gated entirely on building
  the static `usd-embed` monolith (`usd_m`, `PXR_STATIC`, internal namespace
  `aecoEmbed_v1`, python-free) under MSVC. That build has never been done on
  Windows and carries the specific risks the spike README already flags
  (second-TBB, Arch COFF ctor sections). It is NOT multi-day *if* the existing
  `C:\OpenUSD` third-party dependency tree (boost/TBB/etc., already compiled by
  `build_usd.py`) is reused; from a cold machine it would be multi-day.

## OpenUSD dependency scope (what aecoLandingC actually needs)

`aecoLandingC` is a SMALL subset of pxr, not all of it. The DLL source closure
(`aecoLandingC.cpp` + `aecoLanding/{landingBuilder,debugCodes}.cpp` +
`aecoBase/{identity,contentHash,profile,semantics,version,debugCodes}.cpp` +
vendored `sha1.c`/`sha256.c`) includes only:

    pxr/base/{arch, tf, gf, vt, js}   pxr/usd/sdf

**No `pxr/usd/usd` stage, no imaging, no usdGeom, no hydra.** Confirmed by
grepping every include in the closure. Link set (import libs on the shared
prebuilt): `usd_{tf,gf,vt,js,sdf,arch,plug,ar,trace,work,ts,pegtl,kind,pcp}` +
`tbb`. (The boost.python glue — `usd_python` — is pulled ONLY because the
prebuilt is python-on; see below. The production python-free build drops it.)

## Is a prebuilt OpenUSD available? YES — `C:\OpenUSD` on example-navis

A full `build_usd.py` install (dated 2026-07-04), with `include/pxr`, `lib`,
`cmake`, `pxrConfig.cmake`, a working `usdview`/`usdrecord`, and every
third-party dep (boost 1.86, oneTBB, MaterialX, OpenImageIO, OpenEXR, embree,
draco, OpenSubdiv, …). Env setup: `C:\OpenUSD\openusd-env.cmd`.

- **Version: OpenUSD 0.26.5** (`PXR_VERSION 2605`, namespace
  `pxrInternal_v0_26_5`). NOTE: aeco-toolchain pins rev `47154dc` =
  **0.26.11-dev** (`pxrInternal_v0_26_11`). **Minor-version skew** — fine for
  this recon (the Sdf/Tf/Vt/Gf API the closure uses is stable across it; it
  compiled clean), but the production build should rebuild at the pinned rev
  for byte-identity parity with the Linux/Mac `usd-dev`.
- **Linkage: SHARED / dynamic** (73 `usd_*.dll` + import `.lib`s), **python-on**
  (`PXR_PYTHON_SUPPORT_ENABLED`, `PXR_USE_INTERNAL_BOOST_PYTHON` baked into
  `pxr/pxr.h`), **not monolithic** (no `usd_m.lib`), stock namespace. i.e. it
  is the analogue of the flake's `usd-dev`, NOT `usd-embed`.

So the prebuilt is perfect for the dev-flavor DLL and for CI compile-checks,
but it is NOT the `usd-embed` static monolith the production shim wants.

## Build progress (what was actually done)

Standalone CMake scaffold in this directory (`CMakeLists.txt` + the two
`build_msvc*.cmd`) compiles the aeco source closure directly and links
`C:\OpenUSD`. Reproduce on example-navis by copying the aeco `aeco/base` + `aeco/vendor`
trees beside this `CMakeLists.txt` (repo root on the include path) and running
the batch file.

- **Variant A — shared USD, no `PXR_STATIC` (`build_msvc.cmd`): SUCCESS.**
  All 11 TUs compile under MSVC 14.44 (a handful of benign C4273
  "inconsistent dll linkage" warnings — the API-macro/dllexport interplay).
  Links to **`AecoLandingC.dll` (250,880 bytes)** + import lib. `dumpbin
  /exports` shows **all 18 `aeco_landing_*` symbols present** (verified count
  == 18). Total export count is 62: the extra 44 are `Aeco{ContentHash,
  LandingBuilder,Uuid,Profile,Semantics,BaseVersion,Identity}` C++ methods that
  union in from their `ARCH_EXPORT` marks — the exact MSVC `.def`-cannot-
  subtract caveat documented in `aecoLandingC.h`. `dumpbin /dependents`:
  `usd_{tf,gf,vt,js,sdf,arch,python}.dll, tbb.dll, python311.dll,
  MSVCP140/VCRUNTIME140*`, KERNEL32 — a sane closure.
  - One fix over the naive attempt: the python-on `pxr.h` makes Tf/Vt inline
    templates emit `pxr_boost::python` glue, so the build needs Python's
    `include/` (for `pyconfig.h`) and `usd_python.lib` on the link line. Both
    present on example-navis. A python-FREE USD would not need either.

- **Variant B — `PXR_STATIC` to force exactly-18 (`build_msvc_pxrstatic.cmd`):
  FAILS TO LINK, as expected and instructively.** With `PXR_STATIC` defined,
  every pxr ARCH macro (incl. `AECOLANDING_API`/`AECOBASE_API`) goes empty, so
  the `.def` WOULD be the whole export story — but `PXR_STATIC` also makes USD's
  own headers stop marking their symbols `dllimport`, so `TfSingleton::_instance`,
  `Sdf_Pool::_regionStarts`, `SdfValueTypeNames` static data resolve *locally*
  instead of from the DLLs → `LNK1120: 6 unresolved externals`. **`PXR_STATIC`
  is only correct against a STATIC USD.** This is precisely why exactly-18
  requires the `usd-embed` monolith, not a `.def` bolted onto shared USD.

## Recommended path

1. **Immediate / low-cost (CI + unblock managed integration): ship Variant A.**
   Wire the standalone CMake here as an aeco-core `-DAECO_LANDINGC_MSVC_DEV`
   consumer (or a small toolchain package) against `C:\OpenUSD`. It gives the
   add-ins a real `AecoLandingC.dll` to P/Invoke TODAY and a Windows compile-gate
   for the C-ABI TUs. Accept the 44 cosmetic extra exports (harmless to
   consumers). Best rev-parity by rebuilding `C:\OpenUSD` at the pinned
   `47154dc`/0.26.11, but 0.26.5 already compiles.

2. **Production (exactly-18, self-contained): build `usd-embed` for MSVC.**
   Port `nix/usd-embed.nix`'s flags to a `build_scripts/build_usd.py`-driven
   MSVC build (or a direct CMake) at the pinned rev:
   `BUILD_SHARED_LIBS=OFF, PXR_BUILD_MONOLITHIC=ON,
   PXR_SET_INTERNAL_NAMESPACE=aecoEmbed_v1, PXR_ENABLE_PYTHON_SUPPORT=OFF`,
   all imaging/plugins/tests OFF, `CMAKE_CXX_STANDARD=17`, and the two toolchain
   patches (generic parallel-for TBB range; custom-work global for monolithic)
   + the `attributes.{h,cpp}` `pxrctor→aecoctor` section rename. Then this same
   `aecoLandingC/CMakeLists.txt` embed stanza (`AECO_LANDINGC_BUILD_EMBED=ON`,
   `PXR_STATIC`, `WHOLE_ARCHIVE,usd_m`) yields the clean 18-export DLL; verify
   with `dumpbin /exports`. Reuse `C:\OpenUSD\build\*` third-party deps to keep
   this ~1 day, not multi-day. This is the step that also retires the
   second-TBB / Arch-ctor risks the spike README defers to the Windows enclave.

Do NOT attempt exactly-18 by adding `/DEF` tricks on shared USD — Variant B
proves that dead-ends.
