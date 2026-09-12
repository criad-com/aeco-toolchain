# workTaskflowExample — OpenUSD's example custom libWork implementation
# (extras/usd/examples/workTaskflowExample), built standalone from the pinned
# source so usd-dev can consume it via PXR_WORK_IMPL.
{ lib
, stdenv
, cmake
, ninja
, taskflow
, openusdSrc
, version
}:

stdenv.mkDerivation {
  pname = "workTaskflowExample";
  inherit version;

  # The example is a self-contained cmake project inside the OpenUSD tree.
  src = "${openusdSrc}/extras/usd/examples/workTaskflowExample";

  nativeBuildInputs = [ cmake ninja ];
  # taskflow is required at build time and referenced (via the absolute
  # Taskflow_DIR embedded in workTaskflowExampleConfig.cmake) at consume time.
  propagatedBuildInputs = [ taskflow ];

  cmakeFlags = [
    # Never let FetchContent reach the network; Taskflow must resolve via
    # find_package against the nix-provided package.
    "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"
  ];

  meta = {
    description = "OpenUSD libWork implementation backed by Taskflow (from the pinned OpenUSD source)";
    license = lib.licenses.free; # Pixar / TOST license (see LICENSE.txt in the source)
  };
}
