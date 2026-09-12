# OpenUSD embed coexistence spike

This spike proves that one process can operate two copies of the pinned
OpenUSD build:

- `host/` links `usd-dev` (shared libraries, stock internal namespace),
  authors `host.usda`, and loads the shim with `dlopen`.
- `shim/` exposes only `aeco_embed_probe` and `aeco_embed_namespace` as a C
  ABI. It force-loads the static `usd-embed` monolith, authors `embed.usda`,
  and reports its compiled internal namespace.
- The host reopens both files through its own shared Sdf and verifies the
  expected prim and `customLayerData` in each.

Run it with:

```console
nix build .#usd-embed
nix build .#embed-shim
nix build .#checks.aarch64-darwin.embed-spike
cat result/report.txt
```

The check prints:

```text
host internal namespace: pxrInternal_v0_26_11__pxrReserved__
shim internal namespace: aecoEmbed_v1__pxrReserved__
embed coexistence spike OK
```

## Measured closure report

Measured on aarch64-darwin against OpenUSD
`47154dc7b5e28df623745495a7a508b69535ba24` and nixpkgs oneTBB 2022.3.0.
The installed shim dylib is 46,376,912 bytes (44.23 MiB). The shim package's
NAR size is 48,166,408 bytes (45.94 MiB), including the `lib/usd` resource
tree, and its complete three-path runtime closure is 49,407,856 bytes
(47.12 MiB).

`otool -L libaeco_embed_probe.dylib` reports:

```text
libaeco_embed_probe.dylib
Foundation.framework/Versions/C/Foundation
/usr/lib/libSystem.B.dylib
/nix/store/...-onetbb-2022.3.0/lib/libtbb.12.dylib
/usr/lib/libc++.1.dylib
/usr/lib/libobjc.A.dylib
```

There are no OpenUSD or `workTaskflowExample` dylib dependencies: the OpenUSD
monolith and taskflow work implementation are static PIC archives, and
Taskflow itself is header-only. `nm -gU` reports exactly the two intended
exports:

```text
_aeco_embed_namespace
_aeco_embed_probe
```

TBB is still dynamic. The nixpkgs oneTBB outputs contain dylibs and no static
`libtbb.a`; OpenUSD also uses TBB concurrent containers outside the `Work`
scheduler, even with `PXR_WORK_IMPL=workTaskflowExample`. The shim therefore
has a direct `libtbb.12.dylib` dependency, and the closure also contains
oneTBB's `hwloc` dependency. This is a real second-TBB risk for an in-process
Revit host and must be exercised by the Windows enclave spike; the successful
macOS test does not retire that risk.

## Visibility and lifetime caveats

The C++ internal namespace prevents collisions between the two USD copies,
and the Darwin export list (or ELF version script) keeps the public dylib
surface to the C ABI. Static-library symbols still exist locally in the image;
export filtering is defense in depth, not a substitute for the namespace.

OpenUSD's Arch constructor registry uses process-global loader callbacks and,
upstream, shared section names. A stock USD callback initially attempted to
run the embedded copy's constructors while the Mach-O image was only partly
loaded, causing an Objective-C selector failure in `Arch_InitTmpDir`. The
embed derivation isolates those sections as `aecoctor`/`aecodtor`, so each USD
copy initializes only its own registry. This is required in addition to
`PXR_SET_INTERNAL_NAMESPACE`.

On Darwin, Arch registers dyld callbacks for the process lifetime and exposes
no unregister operation. Consumers should load the shim once and keep it
loaded until process exit; the host deliberately does not call `dlclose`.
