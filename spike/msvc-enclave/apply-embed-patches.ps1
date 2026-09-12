# apply-embed-patches.ps1 -- prepare an OpenUSD source tree for the MSVC
# static-monolith (usd-embed) build.
#
# This is the Windows/MSVC port of the source mutations that
# toolchain/nix/usd-embed.nix applies on Nix (its `patches` + `postPatch`):
#
#   1. patches/0001-work-loops-generic-parallel-for-tbb-range.patch
#        pxr/base/work/loops.h -- replace the self-initialising
#        `RangeType range = range;` (shadow / UB) inside WorkParallelForTBBRange
#        with a correctly-seeded `localRange` moved into the range task. Required
#        by the generic TBB-range path.
#   2. the `pxrctor -> aecoctor` / `pxrdtor -> aecodtor` section rename in
#        pxr/base/arch/attributes.{h,cpp}. Arch's constructor registry keys off
#        process-global COFF/Mach-O section names; giving the internally
#        namespaced embed its OWN section names stops a stock USD dyld/loader
#        callback from discovering and running the embedded copy's constructors
#        while its image is only partly loaded (the Arch static-ctor collision
#        the spike README documents).
#
# NOTE on patch 0002 (work-custom-impl-global-for-monolithic): that patch only
# matters when PXR_WORK_IMPL names a *custom* work backend (the
# workTaskflowExample find_package branch). The MSVC recipe builds with the
# default built-in workTBB backend (PXR_WORK_IMPL empty), for which the custom
# `else` branch -- and therefore patch 0002 -- is never taken. It is intentionally
# not applied here. See README.md ("Work backend").
#
#   3. patches/0004-static-monolith-empty-export-msvc.patch (MSVC-ONLY)
#        cmake/macros/Private.cmake -- make the STATIC monolith
#        (PXR_BUILD_MONOLITHIC=ON + BUILD_SHARED_LIBS=OFF) compile every core
#        library with PXR_STATIC=1 so ARCH_EXPORT expands EMPTY and no
#        __declspec(dllexport) bakes into usd_m.lib. Without this, USD's
#        monolithic path (which targets the *shared* usd_ms.dll) marks every
#        symbol dllexport; whole-archiving usd_m.lib into the shim then leaks
#        the entire USD surface through the exports.def UNION (~12k symbols),
#        because a PE/COFF .def cannot SUBTRACT. This is the MSVC analogue of
#        the Nix shim's version script and has no Nix counterpart (ELF/Mach-O
#        filter at link instead). REQUIRED for the exactly-19 (ABI v2) contract.
#
# Idempotent: re-running on an already-patched tree is a no-op.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File apply-embed-patches.ps1 -UsdSrc C:\usd-embed-src

param(
    [Parameter(Mandatory = $true)]
    [string]$UsdSrc
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $UsdSrc "pxr\base\arch\attributes.h"))) {
    throw "-UsdSrc '$UsdSrc' does not look like an OpenUSD source tree (no pxr/base/arch/attributes.h)."
}

# --- (1) work/loops.h: RangeType range = range; -> localRange (+ std::move) ---
$loops = Join-Path $UsdSrc "pxr\base\work\loops.h"
$lines = Get-Content -LiteralPath $loops
$applied = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*RangeType range = range;\s*$') {
        $indent = ($lines[$i] -replace 'RangeType range = range;.*', '')
        $lines[$i] = $indent + 'RangeType localRange = range;'
        for ($j = $i + 1; $j -lt [Math]::Min($i + 4, $lines.Count); $j++) {
            if ($lines[$j] -match 'dispatcher,\s*range,') {
                $lines[$j] = $lines[$j] -replace 'dispatcher,\s*range,', 'dispatcher, std::move(localRange),'
            }
        }
        $applied = $true
        break
    }
}
if ($applied) {
    Set-Content -LiteralPath $loops -Value $lines
    Write-Output "patch 0001 (work/loops.h): APPLIED"
} elseif ((Get-Content -LiteralPath $loops -Raw).Contains("RangeType localRange = range;")) {
    Write-Output "patch 0001 (work/loops.h): already applied"
} else {
    Write-Output "patch 0001 (work/loops.h): target line not found (loops.h shape differs at this rev) -- review manually"
}

# --- (2) pxrctor/pxrdtor -> aecoctor/aecodtor in arch/attributes.{h,cpp} ---
foreach ($rel in @("pxr\base\arch\attributes.h", "pxr\base\arch\attributes.cpp")) {
    $f = Join-Path $UsdSrc $rel
    $c = Get-Content -LiteralPath $f -Raw
    $before = ([regex]::Matches($c, 'pxrctor')).Count + ([regex]::Matches($c, 'pxrdtor')).Count
    if ($before -gt 0) {
        $c = $c.Replace('pxrctor', 'aecoctor').Replace('pxrdtor', 'aecodtor')
        Set-Content -LiteralPath $f -Value $c -NoNewline
        Write-Output ("ctor-section rename {0}: replaced {1} occurrence(s)" -f $rel, $before)
    } else {
        Write-Output ("ctor-section rename {0}: already renamed (0 pxrctor/pxrdtor)" -f $rel)
    }
}

# --- (3) MSVC-only: static monolith compiles core libs with empty ARCH_EXPORT ---
# Insert an `elseif(_building_monolithic AND NOT BUILD_SHARED_LIBS)` branch that
# sets apiPublic=PXR_STATIC=1, right before the endif() of the existing
# individual-static-library apiPublic block in _pxr_library.
$priv = Join-Path $UsdSrc "cmake\macros\Private.cmake"
$plines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $priv)
if ($plines | Select-String -SimpleMatch '_building_monolithic AND NOT BUILD_SHARED_LIBS') {
    Write-Output "patch 0004 (Private.cmake static-monolith export): already applied"
} else {
    $anchorIdx = -1
    for ($i = 0; $i -lt $plines.Count; $i++) {
        if ($plines[$i] -match 'NOT _building_monolithic AND args_TYPE STREQUAL "STATIC"' -and
            $plines[$i + 1] -match 'set\(apiPublic PXR_STATIC=1\)' -and
            $plines[$i + 2] -match '^\s*endif\(\)\s*$') {
            $anchorIdx = $i + 2   # the endif() line
            break
        }
    }
    if ($anchorIdx -lt 0) {
        Write-Output "patch 0004 (Private.cmake static-monolith export): ANCHOR NOT FOUND -- apply patches/0004 manually"
    } else {
        $indent = ($plines[$anchorIdx] -replace 'endif\(\).*', '')
        $insert = @(
            ($indent + 'elseif(_building_monolithic AND NOT BUILD_SHARED_LIBS)')
            ($indent + '    # AECO embed: static monolith. Compile every core library with empty')
            ($indent + '    # ARCH_EXPORT (PXR_STATIC) so NO __declspec(dllexport) bakes into')
            ($indent + '    # usd_m.lib. On PE/COFF the shim exports.def cannot SUBTRACT')
            ($indent + '    # dllexport-marked symbols, so they must never be marked. (ELF/Mach-O')
            ($indent + '    # get this from the shim version script; MSVC needs it at compile time.)')
            ($indent + '    set(apiPublic PXR_STATIC=1)')
        )
        $plines.InsertRange($anchorIdx, [string[]]$insert)
        Set-Content -LiteralPath $priv -Value $plines
        Write-Output "patch 0004 (Private.cmake static-monolith export): APPLIED"
    }
}

Write-Output "apply-embed-patches: DONE"
