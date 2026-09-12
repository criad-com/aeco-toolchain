# usd-dev — OpenUSD core build from the org-pinned source.
#
# Shape (P0-1 plus P3-T1):
#   shared libs, python + imaging + USD imaging + HdEmbree + usdrecord ON,
#   usdview/tests/examples/tutorials/docs OFF, monolithic OFF, C++17.
#
# Work backend (`workImpl`, decision approved by the maintainer — see README "Work
# backend"):
#   "tbb"      — upstream default (workTBB, PXR_WORK_IMPL unset). Default.
#   "taskflow" — taskflow-backed workTaskflowExample via PXR_WORK_IMPL,
#                kept reachable for the future usd-embed.
#
# TBB is required in BOTH modes: tf/trace/vt/plug use TBB concurrent
# containers directly, so oneTBB stays in the closure regardless of the
# Work backend. It is propagated because the installed pxrConfig.cmake
# does `find_dependency(TBB ... CONFIG)` with no recorded TBB_DIR —
# downstream find_package(pxr) needs TBB visible on CMAKE_PREFIX_PATH.
{ lib
, stdenv
, cmake
, ninja
, pkg-config
, python3
, tbb
, embree
, opensubdiv
, taskflow
, workTaskflowExample
, apple-sdk ? null
, openusdSrc
, version
, workImpl ? "tbb"
}:

assert lib.assertOneOf "workImpl" workImpl [ "tbb" "taskflow" ];

stdenv.mkDerivation {
  pname = "usd-dev" + lib.optionalString (workImpl != "tbb") "-${workImpl}";
  inherit version;

  src = openusdSrc;

  patches = [
    # Upstream bug in the generic (non-TBB) WorkParallelForTBBRange fallback:
    # `RangeType range = range;` self-initialises, and the lvalue is then
    # passed to _RangeTask's `RangeType &&` parameter. The branch is only
    # compiled when PXR_WORK_IMPL is a custom impl (workTBB defines
    # WORK_IMPL_HAS_PARALLEL_FOR_TBB_RANGE, which preprocesses it away), so
    # the patch is inert on the "tbb" default and required for "taskflow".
    # Applied unconditionally to keep one patched source for both variants.
    ../patches/0001-work-loops-generic-parallel-for-tbb-range.patch

    # HdEmbree's old-TBB scheduler workaround unconditionally includes a
    # workTBB-private header that is deliberately not installed when a custom
    # Work backend is selected. Guard the workaround on that header's presence,
    # matching its own stated scope and allowing the taskflow variant to build.
    ../patches/0003-hdembree-custom-work.patch
  ];

  nativeBuildInputs = [
    cmake
    ninja
    pkg-config
    python3

    # OpenSubdiv's CMake export describes shared and static targets and checks
    # that both exist while configuring, even though usd-dev links shared.
    opensubdiv.dev
    opensubdiv.static
  ];

  buildInputs = [
    python3
    # The pinned source calls find_package(Embree 4 CONFIG); nixpkgs embree is
    # 4.4.1, whereas Embree 3 would not satisfy this OpenUSD revision.
    embree
  ] ++ lib.optionals (workImpl == "taskflow") [
    taskflow
    workTaskflowExample
  ] ++ lib.optionals stdenv.hostPlatform.isDarwin [
    apple-sdk
  ];

  # See header comment: pxrConfig.cmake find_dependency(TBB/OpenSubdiv) must
  # resolve for downstream consumers (devShell and downstream cmake builds).
  propagatedBuildInputs = [
    tbb
    # Required unconditionally by PXR_BUILD_IMAGING. Propagate it because the
    # installed pxrConfig.cmake calls find_dependency(OpenSubdiv ... CONFIG).
    opensubdiv
  ];

  cmakeFlags = [
    # Library shape
    "-DBUILD_SHARED_LIBS=ON"
    "-DPXR_BUILD_MONOLITHIC=OFF"
    "-DCMAKE_CXX_STANDARD=17"

    # Python
    "-DPXR_ENABLE_PYTHON_SUPPORT=ON"

    # Imaging, USD imaging, and the CPU render delegate used by usdrecord.
    "-DPXR_BUILD_IMAGING=ON"
    "-DPXR_BUILD_USD_IMAGING=ON"
    "-DPXR_BUILD_EMBREE_PLUGIN=ON"

    # This pin gates HdEmbree, usdAppUtils, and usdrecord on
    # PXR_BUILD_GPU_SUPPORT even for --disableGpu rendering. Its usdImagingGL
    # path also requires hdSt/hdx, which are still conditional on OpenGL.
    "-DPXR_ENABLE_GL_SUPPORT=ON"
    "-DPXR_ENABLE_METAL_SUPPORT=OFF"

    # Keep the GUI out. usdrecord itself needs no non-stdlib Python packages.
    "-DPXR_BUILD_USDVIEW=OFF"

    # No tests / examples / tutorials / docs
    "-DPXR_BUILD_TESTS=OFF"
    "-DPXR_BUILD_EXAMPLES=OFF"
    "-DPXR_BUILD_TUTORIALS=OFF"
    "-DPXR_BUILD_DOCUMENTATION=OFF"

    # Keep the command-line tools, including usdAppUtils/usdrecord now that
    # USD imaging and the build-time GPU-support gate are enabled.
    "-DPXR_BUILD_USD_TOOLS=ON"

    # Minimal imaging closure: no MaterialX or unrelated imaging plugins.
    "-DPXR_ENABLE_MATERIALX_SUPPORT=OFF"
    "-DPXR_BUILD_OPENIMAGEIO_PLUGIN=OFF"
    "-DPXR_BUILD_OPENCOLORIO_PLUGIN=OFF"
    "-DPXR_BUILD_PRMAN_PLUGIN=OFF"
    "-DPXR_ENABLE_OPENVDB_SUPPORT=OFF"
  ] ++ lib.optionals (workImpl == "taskflow") [
    # Custom libWork implementation (taskflow-backed)
    "-DPXR_WORK_IMPL=workTaskflowExample"
    "-DworkTaskflowExample_DIR=${workTaskflowExample}/lib/cmake/workTaskflowExample"
  ];

  meta = {
    description = "OpenUSD (python, imaging, HdEmbree, usdrecord, work=${workImpl}) built from the org-pinned source";
    homepage = "https://openusd.org";
    license = lib.licenses.free; # Pixar / TOST license (see LICENSE.txt in the source)
    mainProgram = "usdcat";
  };
}
