# Static PIC form of OpenUSD's taskflow libWork implementation for usd-embed.
{ lib
, stdenv
, cmake
, ninja
, taskflow
, openusdSrc
, version
}:

stdenv.mkDerivation {
  pname = "workTaskflowExample-static";
  inherit version;

  src = "${openusdSrc}/extras/usd/examples/workTaskflowExample";

  postPatch = ''
    # The upstream example hard-codes SHARED instead of honoring
    # BUILD_SHARED_LIBS.  The embed closure needs the backend absorbed into
    # the shim alongside the OpenUSD archive.
    substituteInPlace CMakeLists.txt \
      --replace-fail \
        'add_library(workTaskflowExample SHARED)' \
        'add_library(workTaskflowExample STATIC)'
  '';

  nativeBuildInputs = [ cmake ninja ];
  propagatedBuildInputs = [ taskflow ];

  cmakeFlags = [
    "-DBUILD_SHARED_LIBS=OFF"
    "-DCMAKE_POSITION_INDEPENDENT_CODE=ON"
    "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"
  ];

  meta = {
    description = "Static PIC OpenUSD libWork implementation backed by Taskflow";
    license = lib.licenses.free;
  };
}
