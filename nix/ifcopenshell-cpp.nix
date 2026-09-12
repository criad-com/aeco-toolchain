# IfcOpenShell C++ parsing core for aecoExtractIfc.
#
# This intentionally builds only libIfcParse. Representation-map identity and
# mapped-item transforms are present in the parsed IFC graph, so prototype
# dedup does not require IfcGeom tessellation. Keeping IfcGeom off also keeps
# OpenCASCADE and CGAL out of this heavy-dependency leaf's closure.
{ lib
, stdenv
, cmake
, ninja
, boost
, fetchFromGitHub
, ifcOpenShellRev
, version
}:

stdenv.mkDerivation {
  pname = "ifcopenshell-cpp";
  inherit version;

  src = fetchFromGitHub {
    owner = "IfcOpenShell";
    repo = "IfcOpenShell";
    # Commit resolved from stable tag ifcopenshell-python-0.8.5. The project
    # uses that tag name for the whole monorepo release, including C++.
    rev = ifcOpenShellRev;
    hash = "sha256-z0iFc5jXN9xFuzUW9oYH42OCXDZoobR/XzRBoV1MuL0=";
  };

  nativeBuildInputs = [
    cmake
    ninja
  ];

  # IfcParse's public headers and exported CMake target expose Boost types and
  # targets. Propagate the same nixpkgs Boost pin used by the toolchain so a
  # downstream find_package(IfcOpenShell) resolves one compatible copy.
  propagatedBuildInputs = [ boost ];

  postPatch = ''
    # Boost.System became header-only and its binary component disappeared in
    # Boost 1.89. This is the same compatibility adjustment carried by the
    # pinned nixpkgs Python recipe, applied here to both build and export data.
    substituteInPlace cmake/CMakeLists.txt \
      --replace-fail '        system' \
        '        # Boost.System is header-only in Boost 1.89.'
    substituteInPlace cmake/IfcOpenShellConfig.cmake.in \
      --replace-fail 'set(Boost_USE_STATIC_LIBS ON)' 'set(Boost_USE_STATIC_LIBS OFF)' \
      --replace-fail '    system' \
        '    # Boost.System is header-only in Boost 1.89.' \
      --replace-fail 'find_dependency(Eigen3 CONFIG)' \
        '# IfcParse-only builds do not export or use Eigen targets.'
  '';

  # Upstream keeps its top-level CMake project in this subdirectory.
  preConfigure = ''
    cd cmake
  '';

  cmakeFlags = [
    "-DVERSION_OVERRIDE=ON"
    "-DEXTRA_VERSION="
    "-DCMAKE_CXX_STANDARD=17"

    # LGPL posture: aecoExtractIfc must dynamically link this shared library.
    "-DBUILD_SHARED_LIBS=ON"

    # Parsing and common production schemas only.
    "-DSCHEMA_VERSIONS=2x3;4;4x3_add2"
    "-DBUILD_IFCGEOM=OFF"
    "-DBUILD_IFCPYTHON=OFF"
    "-DBUILD_CONVERT=OFF"
    "-DBUILD_GEOMSERVER=OFF"
    "-DBUILD_IFCMAX=OFF"
    "-DBUILD_QTVIEWER=OFF"
    "-DBUILD_DOCUMENTATION=OFF"
    "-DBUILD_EXAMPLES=OFF"
    "-DBUILD_PACKAGE=OFF"

    # Geometry/conversion and unrelated storage/XML integrations. These are a
    # deliberate seam, not silently inherited defaults.
    "-DWITH_OPENCASCADE=OFF"
    "-DWITH_CGAL=OFF"
    "-DCOLLADA_SUPPORT=OFF"
    "-DGLTF_SUPPORT=OFF"
    "-DHDF5_SUPPORT=OFF"
    "-DIFCXML_SUPPORT=OFF"
    "-DUSD_SUPPORT=OFF"
    "-DWITH_PROJ=OFF"
    "-DWITH_ROCKSDB=OFF"
    "-DWITH_ZSTD=OFF"
    "-DUSE_MMAP=OFF"
    "-DUSE_CCACHE=OFF"
  ];

  postInstall = ''
    install -Dm444 "$src/COPYING" \
      "$out/share/licenses/IfcOpenShell/COPYING"
    install -Dm444 "$src/COPYING.LESSER" \
      "$out/share/licenses/IfcOpenShell/COPYING.LESSER"
  '';

  postFixup = ''
    test -d "$out/include/ifcparse"
    test -e "$out/lib/cmake/IfcOpenShell/IfcOpenShellConfig.cmake"

    shared_library=$(find "$out/lib" -maxdepth 1 -type f \
      \( -name 'libIfcParse.dylib' -o -name 'libIfcParse.so' \
         -o -name 'libIfcParse.so.*' -o -name 'libIfcParse.*.dylib' \) \
      -print -quit)
    test -n "$shared_library"

    if find "$out/lib" -maxdepth 1 -type f -name 'libIfcParse.a' \
      -print -quit | grep -q .; then
      echo "static libIfcParse must not be shipped" >&2
      exit 1
    fi
    if find "$out/lib" -maxdepth 1 -type f \
      \( -name 'libIfcGeom*' -o -name '*OpenCASCADE*' \) \
      -print -quit | grep -q .; then
      echo "IfcGeom/OCCT leaked into the IfcParse-only output" >&2
      exit 1
    fi
  '';

  meta = {
    description = "IfcOpenShell C++ IFC parsing library (shared, without IfcGeom/OCCT)";
    homepage = "https://ifcopenshell.org/";
    license = lib.licenses.lgpl3Plus;
    platforms = lib.platforms.darwin ++ lib.platforms.linux;
  };
}
