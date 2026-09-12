{
  description = "aeco-toolchain — pinned OpenUSD and heavy extractor dependencies";

  # Local cache settings and mirror addresses live in an external registry.
  # tools/nix-local.py supplies them; flake nixConfig requires literal values.

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/afb4584a80bbf779ce0f691509ff902d188c2b3d";
    flake-utils.url = "github:numtide/flake-utils/11707dc2f618dd54ca8739b309ec4fc024de578b";

    # Verbatim upstream OpenUSD dev; local mirrors use the deployment registry.
    openusd = {
      url = "github:PixarAnimationStudios/OpenUSD?rev=47154dc7b5e28df623745495a7a508b69535ba24";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, openusd }:
    flake-utils.lib.eachSystem
      # aarch64-darwin is the supported target today; x86_64-linux is kept
      # evaluating so the flake can be extended to Linux builders later.
      [ "aarch64-darwin" "x86_64-linux" ]
      (system:
        let
          pkgs = import nixpkgs { inherit system; };

          inherit (pkgs) lib stdenv;

          usdRev = "47154dc7b5e28df623745495a7a508b69535ba24";
          usdVersion = "0.26.11-dev-g${builtins.substring 0 7 usdRev}";

          # Stable IfcOpenShell release used by the C++ parsing-only package.
          ifcOpenShellRev = "16723d11cab9bc8a13b4e025a00d39445ccc462e";
          ifcOpenShellVersion = "0.8.5";

          apple-sdk =
            if stdenv.hostPlatform.isDarwin
            then pkgs.apple-sdk_15
            else null;

          # --- Dependencies -----------------------------------------------

          # Task-scheduling backend for pxr work (see workTaskflowExample).
          taskflow = stdenv.mkDerivation rec {
            pname = "taskflow";
            version = "3.10.0";
            src = pkgs.fetchFromGitHub {
              owner = "taskflow";
              repo = "taskflow";
              rev = "v${version}";
              hash = "sha256-s0A8zJoq0VfmAks9h4v63J7tPX5JnlNTzJJMilzc5yM=";
            };
            nativeBuildInputs = [ pkgs.cmake ];
            cmakeFlags = [
              "-DTF_BUILD_TESTS=OFF"
              "-DTF_BUILD_EXAMPLES=OFF"
              "-DTF_BUILD_BENCHMARKS=OFF"
            ];
            meta = {
              description = "General-purpose parallel task programming system";
              homepage = "https://taskflow.github.io/";
              license = lib.licenses.mit;
            };
          };

          # Custom libWork implementation (PXR_WORK_IMPL) built from the
          # pinned OpenUSD source tree itself.
          workTaskflowExample = pkgs.callPackage ./nix/workTaskflowExample.nix {
            inherit taskflow;
            openusdSrc = openusd;
            version = usdVersion;
          };

          workTaskflowExampleStatic =
            pkgs.callPackage ./nix/workTaskflowExample-static.nix {
              inherit taskflow;
              openusdSrc = openusd;
              version = usdVersion;
            };

          # Default: upstream Work backend (workTBB). See README "Work backend".
          usd-dev = pkgs.callPackage ./nix/usd-dev.nix {
            inherit taskflow workTaskflowExample apple-sdk;
            openusdSrc = openusd;
            version = usdVersion;
            tbb = pkgs.tbb; # oneTBB 2022.3 — same as nixpkgs' openusd on this rev
            embree = pkgs.embree; # Embree 4.4 — the pin requires Embree 4 CONFIG
            opensubdiv = pkgs.opensubdiv; # imaging's required subdivision backend
          };

          # Taskflow-backed Work variant, kept reachable for the future
          # usd-embed. See README "Work backend".
          usd-dev-taskflow = usd-dev.override { workImpl = "taskflow"; };

          # Heavy extractor dependency kept separate from both USD variants.
          # It uses the same nixpkgs Boost pin as the rest of this flake and
          # deliberately carries no IfcGeom/OpenCASCADE closure.
          ifcopenshell-cpp = pkgs.callPackage ./nix/ifcopenshell-cpp.nix {
            inherit ifcOpenShellRev;
            version = ifcOpenShellVersion;
            boost = pkgs.boost;
          };

          # OCCT's nixpkgs recipe defaults to shared libraries. Keep the exact
          # derivation so consumers can reuse binary substitutes.
          occt = pkgs.opencascade-occt;

          ifcopenshell-cpp-geom = pkgs.callPackage ./nix/ifcopenshell-cpp-geom.nix {
            inherit ifcopenshell-cpp occt;
          };

          ifcGeomSmoke = pkgs.runCommand "check-ifcgeom" {
            nativeBuildInputs = [ pkgs.cmake pkgs.ninja pkgs.stdenv.cc ]
              ++ lib.optionals stdenv.hostPlatform.isDarwin [ pkgs.darwin.cctools ];
            buildInputs = [ ifcopenshell-cpp-geom ];
          } ''
            echo "== stage: IfcGeom extruded-wall"
            cmake -S ${self}/tests/ifcgeom-smoke -B build -G Ninja
            cmake --build build
            ctest --test-dir build --output-on-failure
            mkdir -p "$out"
            build/aeco-ifcgeom-smoke ${self}/tests/ifcgeom-smoke/wall.ifc | tee "$out/report.txt"
            ${if stdenv.hostPlatform.isDarwin then ''
              otool -L ${ifcopenshell-cpp-geom}/lib/libgeometry_kernel_opencascade.dylib > "$out/linkage.txt"
            '' else ''
              ldd ${ifcopenshell-cpp-geom}/lib/libgeometry_kernel_opencascade.so > "$out/linkage.txt"
            ''}
            grep -q 'libTK' "$out/linkage.txt"
            mkdir -p "$out/bin"
            cp build/aeco-ifcgeom-smoke "$out/bin/"
          '';

          # Gate-T document/workbook dependencies come from this flake's
          # nixpkgs pin. The ordinary poppler derivation includes its C++ API
          # and poppler-cpp pkg-config module; it is not a separate package.
          poppler = pkgs.poppler;
          libzip = pkgs.libzip;

          # Stock libixion 0.20.0 fails to link its Python extension on
          # aarch64-darwin (unresolved Python C API symbols), which prevents
          # stock liborcus from building. Gate-T consumes only the C++ API, so
          # keep the nixpkgs recipes but disable both irrelevant Python
          # bindings. Explicitly retain shared-only libraries at this seam.
          cppOnlyShared = package: package.overrideAttrs (old: {
            configureFlags = (old.configureFlags or [ ]) ++ [
              "--disable-python"
              "--disable-static"
              "--enable-shared"
            ];
          });

          libixion-cpp = cppOnlyShared pkgs.libixion;
          liborcus = cppOnlyShared (pkgs.liborcus.override {
            libixion = libixion-cpp;
          });

          usd-embed = pkgs.callPackage ./nix/usd-embed.nix {
            inherit taskflow apple-sdk;
            workTaskflowExample = workTaskflowExampleStatic;
            openusdSrc = openusd;
            version = usdVersion;
            tbb = pkgs.tbb;
          };

          embed-shim = pkgs.callPackage ./nix/embed-shim.nix {
            inherit taskflow;
            workTaskflowExample = workTaskflowExampleStatic;
            usdEmbed = usd-embed;
          };

          embed-host = pkgs.callPackage ./nix/embed-host.nix {
            usdDev = usd-dev;
          };

          # The pinned OpenUSD source tree, verbatim, as a buildable package
          # so downstream tools can reference it.
          openusd-src = pkgs.runCommandLocal "openusd-src-${usdVersion}" { } ''
            ln -s ${openusd} $out
          '';

          pythonSitePackages = "lib/${pkgs.python3.libPrefix}/site-packages";

          pxrSmokeScript = pkgs.writeText "pxr-import-smoke.py" ''
            from pxr import Usd, UsdGeom, Sdf

            stage = Usd.Stage.CreateInMemory()
            UsdGeom.Xform.Define(stage, "/toolchainSmoke")
            assert stage.GetPrimAtPath("/toolchainSmoke").IsValid()
            layer = Sdf.Layer.CreateAnonymous(".usda")
            print("pxr import smoke OK — Usd version:", Usd.GetVersion())
          '';

          extractorDepsSmokeSource = pkgs.writeText
            "extractor-deps-smoke.cpp" ''
            #include <orcus/orcus_xlsx.hpp>
            #include <poppler-version.h>
            #include <zip.h>

            #include <iostream>
            #include <string>

            int main()
            {
                const std::string popplerVersion = poppler::version_string();
                const char* const libzipVersion = zip_libzip_version();

                if (popplerVersion.empty() || libzipVersion == nullptr ||
                    orcus::orcus_xlsx::detect("not an xlsx workbook")) {
                    return 1;
                }

                std::cout << "Gate-T extractor dependency smoke OK"
                          << " — poppler=" << popplerVersion
                          << " libzip=" << libzipVersion
                          << " liborcus=xlsx-reader\n";
                return 0;
            }
          '';

          # Render the same fixture under each Work backend. ImageMagick is a
          # check-only dependency used to reject a valid-but-blank PNG.
          usdrecordEmbreeCheck = name: usdPackage:
            pkgs.runCommand "check-usdrecord-embree-${name}"
              {
                nativeBuildInputs = [ pkgs.imagemagick ];
              } ''
              mkdir -p "$out"
              export PYTHONPATH=${usdPackage}/${pythonSitePackages}
              ${usdPackage}/bin/usdrecord \
                --disableGpu \
                --renderer Embree \
                --imageWidth 256 \
                ${self}/tests/usdrecord-embree/cube.usda \
                "$out/cube.png"

              colors=$(magick "$out/cube.png" -format %k info:)
              test "$colors" -gt 1
              printf 'renderer=Embree colors=%s\n' "$colors" \
                > "$out/report.txt"
            '';
        in
        {
          # --- Packages ---------------------------------------------------

          packages = {
            inherit
              taskflow
              workTaskflowExample
              usd-dev
              usd-dev-taskflow
              ifcopenshell-cpp
              occt
              ifcopenshell-cpp-geom
              poppler
              libzip
              liborcus
              usd-embed
              embed-shim
              embed-host
              openusd-src
              ;
            default = usd-dev;
          };

          # --- Checks (nix flake check) -----------------------------------

          checks = {
            ifcgeom = ifcGeomSmoke;
            occt-shared = pkgs.runCommand "check-occt-shared" { } ''
              echo "== stage: OCCT shared closure"
              mkdir -p "$out"
              closure=${pkgs.closureInfo { rootPaths = [ occt ifcGeomSmoke usd-dev ]; }}/store-paths
              while IFS= read -r store_path; do
                if find "$store_path" -name 'libTK*.a' -print -quit | grep -q .; then
                  echo "static OCCT archive in native consumer closure" >&2
                  exit 1
                fi
              done < "$closure"
              printf 'OCCT version=${occt.version}; closure paths=%s; static OCCT archives=0\n' \
                "$(wc -l < "$closure" | tr -d ' ')" | tee "$out/report.txt"
            '';
            # (a) python import smoke test against usd-dev
            pxr-import = pkgs.runCommand "check-pxr-import"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              } ''
              export PYTHONPATH=${usd-dev}/${pythonSitePackages}
              python3 ${pxrSmokeScript}
              touch $out
            '';

            # (b) blocking headless CPU render proof for both Work variants.
            usdrecord-embree = usdrecordEmbreeCheck "tbb" usd-dev;
            usdrecord-embree-taskflow =
              usdrecordEmbreeCheck "taskflow" usd-dev-taskflow;

            # (c) compile through the installed CMake package, dynamically
            # link libIfcParse, parse a tiny hermetic IFC4 fixture, and count
            # all IfcRoot-derived entities (exactly one IfcProject here).
            ifcparse = pkgs.runCommand "check-ifcparse"
              {
                nativeBuildInputs = [ pkgs.cmake pkgs.ninja pkgs.stdenv.cc ];
                buildInputs = [ ifcopenshell-cpp ];
              } ''
              cmake -S ${self}/tests/ifcparse-smoke -B build -G Ninja \
                -DIfcOpenShell_DIR=${ifcopenshell-cpp}/lib/cmake/IfcOpenShell
              cmake --build build

              mkdir -p "$out"
              build/aeco-ifcparse-smoke \
                ${self}/tests/ifcparse-smoke/minimal.ifc \
                | tee "$out/report.txt"
              grep -q 'IfcRoot-derived entities=1' "$out/report.txt"
            '';

            # (d) compile and dynamically link the public Gate-T interfaces.
            # This also forces every exposed dependency (including dev
            # outputs) to build as part of nix flake check.
            extractor-deps = pkgs.runCommand "check-extractor-deps"
              {
                nativeBuildInputs = [ pkgs.pkg-config pkgs.stdenv.cc ];
                buildInputs = [ poppler libzip liborcus ];
              } ''
              $CXX -std=c++17 \
                $(${pkgs.pkg-config}/bin/pkg-config \
                  --cflags poppler-cpp libzip liborcus-0.21) \
                ${extractorDepsSmokeSource} \
                -o extractor-deps-smoke \
                $(${pkgs.pkg-config}/bin/pkg-config \
                  --libs poppler-cpp libzip liborcus-0.21)

              mkdir -p "$out"
              ./extractor-deps-smoke | tee "$out/report.txt"
              grep -q 'Gate-T extractor dependency smoke OK' \
                "$out/report.txt"

              if find ${poppler} ${libzip} ${liborcus} \
                -type f -name '*.a' -print -quit | grep -q .; then
                echo "Gate-T dependencies must remain shared-only" >&2
                exit 1
              fi
            '';

            # (e) macro replica drift check against the pinned source
            drift = pkgs.runCommandLocal "check-macro-drift" { } ''
              OPENUSD_SRC=${openusd} ${pkgs.bash}/bin/bash \
                ${self}/tools/drift-check.sh
              touch $out
            '';

            # (f) one process operates stock shared USD and the namespaced,
            # static USD carried by the dynamically loaded C-ABI shim.
            embed-spike = pkgs.runCommand "check-embed-spike" { } ''
              mkdir -p "$out/layers"
              shim=$(find ${embed-shim}/lib -maxdepth 1 -type f \
                \( -name '*.dylib' -o -name '*.so' \) -print -quit)
              if [ -z "$shim" ]; then
                echo "embed shim library not found" >&2
                exit 1
              fi
              ${embed-host}/bin/aeco-embed-host "$shim" "$out/layers" \
                | tee "$out/report.txt"
              test -s "$out/layers/host.usda"
              test -s "$out/layers/embed.usda"
              grep -q 'embed coexistence spike OK' "$out/report.txt"
            '';

            # (g) conventions linter: run it over THIS repo, and run its own
            # stdlib-only unittest suite (the fixtures + guard derivation).
            # Both are hermetic (no USD, no third-party python) so they belong
            # in the fast flake check. Consumer repos wire the same linter from
            # this repo as a flake input — see README "aecoLintConventions".
            lintConventions = pkgs.runCommandLocal "check-lint-conventions"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              } ''
              cd ${self}
              echo "== aecoLintConventions unittest suite =="
              python3 -m unittest discover -s tools/tests -v
              echo "== aecoLintConventions over the toolchain repo =="
              python3 tools/aecoLintConventions.py ${self}
              touch $out
            '';
          };

          # --- Dev shell --------------------------------------------------

          devShells.default = pkgs.mkShell {
            name = "aeco-toolchain";

            packages = [
              pkgs.cmake
              pkgs.ninja
              pkgs.pkg-config
              pkgs.python3
              usd-dev
              ifcopenshell-cpp
              poppler
              libzip
              liborcus
            ];

            shellHook = ''
              export PYTHONPATH=${usd-dev}/${pythonSitePackages}''${PYTHONPATH:+:$PYTHONPATH}
              export PATH=${usd-dev}/bin''${PATH:+:$PATH}
              export pxr_DIR=${usd-dev}
              export IfcOpenShell_DIR=${ifcopenshell-cpp}/lib/cmake/IfcOpenShell
              echo "aeco-toolchain dev shell"
              echo "  usd-dev: ${usd-dev}"
              echo "  IfcParse: ${ifcopenshell-cpp}"
              echo "  Poppler C++: ${poppler}"
              echo "  libzip: ${libzip}"
              echo "  liborcus: ${liborcus}"
              echo "  python:  python3 -c 'from pxr import Usd' should work"
            '';
          };

          devShells.native = pkgs.mkShell {
            name = "aeco-native";
            packages = [ pkgs.cmake pkgs.ninja pkgs.stdenv.cc
              pkgs.pkg-config pkgs.python3 usd-dev occt
              pkgs.opensubdiv.dev pkgs.opensubdiv.static ];
            shellHook = ''
              export PYTHONPATH=${usd-dev}/${pythonSitePackages}
              export pxr_DIR=${usd-dev}
            '';
          };
        });
}
