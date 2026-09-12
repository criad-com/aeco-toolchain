{ lib
, stdenv
, cmake
, ninja
, taskflow
, workTaskflowExample
, usdEmbed
}:

stdenv.mkDerivation {
  pname = "aeco-embed-shim";
  version = "0.1.0";

  src = ../spike/shim;

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [
    usdEmbed
    taskflow
    workTaskflowExample
  ];

  cmakeFlags = [
    "-Dpxr_DIR=${usdEmbed}"
  ];

  postInstall = ''
    # Plug's bootstrap metadata locates the Sdf resources relative to the
    # image containing the embedded USD implementation.
    cp -R ${usdEmbed}/lib/usd "$out/lib/usd"
  '';

  meta = {
    description = "C-ABI Sdf authoring probe with static namespaced OpenUSD";
    license = lib.licenses.mit;
    platforms = lib.platforms.unix;
  };
}
