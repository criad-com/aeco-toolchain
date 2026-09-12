{ lib
, stdenv
, cmake
, ninja
, python3
, usdDev
}:

stdenv.mkDerivation {
  pname = "aeco-embed-host";
  version = "0.1.0";

  src = ../spike/host;

  nativeBuildInputs = [ cmake ninja python3 ];
  buildInputs = [
    usdDev
    python3
  ];

  cmakeFlags = [
    "-Dpxr_DIR=${usdDev}"
  ];

  meta = {
    description = "Shared-OpenUSD host for the AECO embed coexistence spike";
    license = lib.licenses.mit;
    platforms = lib.platforms.unix;
    mainProgram = "aeco-embed-host";
  };
}
