# usd-embed — OpenUSD for an in-process C-ABI shim.
#
# Shape (per packet P0-4):
#   static, monolithic, python-free, internally namespaced,
#   no imaging/tools/tests/examples/tutorials/docs.
#
# The monolith still contains the OpenUSD core library tree.  Keeping it
# monolithic is intentional: the final shim can force-load one PIC archive so
# registry initializers (including Sdf file formats) are not discarded.
{ lib
, stdenv
, cmake
, ninja
, pkg-config
, tbb
, taskflow
, workTaskflowExample
, apple-sdk ? null
, openusdSrc
, version
}:

stdenv.mkDerivation {
  pname = "usd-embed";
  inherit version;

  src = openusdSrc;

  patches = [
    # Required by the generic WorkParallelForTBBRange path selected by the
    # taskflow-backed PXR_WORK_IMPL.
    ../patches/0001-work-loops-generic-parallel-for-tbb-range.patch

    # The imported custom-work target otherwise has directory scope and is
    # invisible when the monolithic archive is finalized at the project root.
    ../patches/0002-work-custom-impl-global-for-monolithic.patch
  ];

  postPatch = ''
    # Arch's constructor registry uses process-global Mach-O/COFF section
    # names.  A stock USD dyld callback would otherwise discover and run the
    # embedded copy's constructors while its image is only partly loaded.
    # Give the internally namespaced embed its own registry sections too.
    substituteInPlace \
      pxr/base/arch/attributes.h \
      pxr/base/arch/attributes.cpp \
      --replace-warn 'pxrctor' 'aecoctor' \
      --replace-warn 'pxrdtor' 'aecodtor'
  '';

  nativeBuildInputs = [
    cmake
    ninja
    pkg-config
  ];

  # OpenUSD still uses oneTBB concurrent containers outside libWork.  The
  # taskflow package and implementation are header/interface dependencies.
  buildInputs = [
    taskflow
    workTaskflowExample
  ] ++ lib.optionals stdenv.hostPlatform.isDarwin [
    apple-sdk
  ];

  # The installed pxrConfig.cmake calls find_dependency(TBB), so consumers
  # need the oneTBB package config on CMAKE_PREFIX_PATH.
  propagatedBuildInputs = [ tbb ];

  cmakeFlags = [
    # Embeddable library shape.
    "-DBUILD_SHARED_LIBS=OFF"
    "-DPXR_BUILD_MONOLITHIC=ON"
    "-DPXR_SET_INTERNAL_NAMESPACE=aecoEmbed_v1"
    "-DCMAKE_CXX_STANDARD=17"

    # Deliberately absent runtime surfaces.
    "-DPXR_ENABLE_PYTHON_SUPPORT=OFF"
    "-DPXR_BUILD_IMAGING=OFF"
    "-DPXR_BUILD_USD_IMAGING=OFF"
    "-DPXR_BUILD_USDVIEW=OFF"
    "-DPXR_BUILD_USD_TOOLS=OFF"
    "-DPXR_BUILD_TESTS=OFF"
    "-DPXR_BUILD_EXAMPLES=OFF"
    "-DPXR_BUILD_TUTORIALS=OFF"
    "-DPXR_BUILD_DOCUMENTATION=OFF"

    # Keep optional heavy/plugin dependencies out of the closure.
    "-DPXR_ENABLE_MATERIALX_SUPPORT=OFF"
    "-DPXR_BUILD_ALEMBIC_PLUGIN=OFF"
    "-DPXR_BUILD_DRACO_PLUGIN=OFF"
    "-DPXR_BUILD_EMBREE_PLUGIN=OFF"
    "-DPXR_BUILD_OPENIMAGEIO_PLUGIN=OFF"
    "-DPXR_BUILD_OPENCOLORIO_PLUGIN=OFF"
    "-DPXR_BUILD_PRMAN_PLUGIN=OFF"
    "-DPXR_BUILD_OPENVDB_PLUGIN=OFF"

    # Custom libWork implementation (taskflow-backed).
    "-DPXR_WORK_IMPL=workTaskflowExample"
    "-DworkTaskflowExample_DIR=${workTaskflowExample}/lib/cmake/workTaskflowExample"
  ];

  meta = {
    description = "Static internally-namespaced OpenUSD monolith for AECO embedding";
    homepage = "https://openusd.org";
    license = lib.licenses.free; # Pixar / TOST license (see source LICENSE.txt)
  };
}
