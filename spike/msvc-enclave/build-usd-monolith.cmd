@echo off
setlocal enableextensions
rem =====================================================================
rem  build-usd-monolith.cmd
rem
rem  Build a STATIC MONOLITHIC OpenUSD (the `usd_m` target -> usd_m.lib) for
rem  the AECO in-process C-ABI shim, under MSVC. This is the Windows/MSVC port
rem  of toolchain/nix/usd-embed.nix: same shape (static, monolithic, python-
rem  free, internally namespaced aecoEmbed_v1, no imaging/tools/tests/plugins),
rem  reusing example-navis's prebuilt third-party (boost 1.86 + TBB 2020.3) so the build
rem  stays ~1 day rather than multi-day.
rem
rem  Prereqs on the host:
rem    - VS 2022 BuildTools (vcvars64 + bundled ninja + cl on PATH after vcvars)
rem    - A patched OpenUSD source tree at %USDSRC% (run apply-embed-patches.ps1)
rem    - The prebuilt third-party under %OPENUSD_ROOT% (boost headers + TBB)
rem
rem  Env overrides (all optional):
rem    USDSRC       OpenUSD source tree           (default C:\usd-embed-src)
rem    BUILD        CMake binary dir              (default C:\usd-embed-build)
rem    PREFIX       install prefix               (default C:\usd-embed)
rem    OPENUSD_ROOT prebuilt USD install w/ deps  (default C:\OpenUSD)
rem    VCVARS       path to vcvars64.bat
rem =====================================================================

if not defined USDSRC       set "USDSRC=C:\usd-embed-src"
if not defined BUILD        set "BUILD=C:\usd-embed-build"
if not defined PREFIX       set "PREFIX=C:\usd-embed"
if not defined OPENUSD_ROOT set "OPENUSD_ROOT=C:\OpenUSD"
if not defined VCVARS       set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

rem Prebuilt third-party reused from the existing build_usd.py install.
set "BOOST_INC=%OPENUSD_ROOT%\src\boost_1_86_0"
set "TBB_INC=%OPENUSD_ROOT%\include"
set "TBB_LIB=%OPENUSD_ROOT%\lib\tbb.lib"

call "%VCVARS%" >NUL 2>&1
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
where cl    >NUL 2>&1 || ( echo NO_CL & exit /b 1 )
where ninja >NUL 2>&1 || ( echo NO_NINJA & exit /b 1 )

echo === CONFIGURE (static monolith, aecoEmbed_v1, python-free) ===
cmake -S "%USDSRC%" -B "%BUILD%" -G Ninja ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_INSTALL_PREFIX="%PREFIX%" ^
  -DBUILD_SHARED_LIBS=OFF ^
  -DPXR_BUILD_MONOLITHIC=ON ^
  -DPXR_SET_INTERNAL_NAMESPACE=aecoEmbed_v1 ^
  -DCMAKE_CXX_STANDARD=17 ^
  -DPXR_ENABLE_PYTHON_SUPPORT=OFF ^
  -DPXR_BUILD_IMAGING=OFF ^
  -DPXR_BUILD_USD_IMAGING=OFF ^
  -DPXR_BUILD_USDVIEW=OFF ^
  -DPXR_BUILD_USD_TOOLS=OFF ^
  -DPXR_BUILD_TESTS=OFF ^
  -DPXR_BUILD_EXAMPLES=OFF ^
  -DPXR_BUILD_TUTORIALS=OFF ^
  -DPXR_BUILD_DOCUMENTATION=OFF ^
  -DPXR_ENABLE_MATERIALX_SUPPORT=OFF ^
  -DPXR_BUILD_ALEMBIC_PLUGIN=OFF ^
  -DPXR_BUILD_DRACO_PLUGIN=OFF ^
  -DPXR_BUILD_EMBREE_PLUGIN=OFF ^
  -DPXR_BUILD_OPENIMAGEIO_PLUGIN=OFF ^
  -DPXR_BUILD_OPENCOLORIO_PLUGIN=OFF ^
  -DPXR_BUILD_PRMAN_PLUGIN=OFF ^
  -DPXR_BUILD_OPENVDB_PLUGIN=OFF ^
  -DPXR_ENABLE_PTEX_SUPPORT=OFF ^
  -DPXR_ENABLE_OPENVDB_SUPPORT=OFF ^
  -DBoost_NO_BOOST_CMAKE=ON ^
  -DBoost_INCLUDE_DIR="%BOOST_INC%" ^
  -DBOOST_ROOT="%BOOST_INC%" ^
  -DTBB_INCLUDE_DIRS="%TBB_INC%" ^
  -DTBB_LIBRARY="%TBB_LIB%" ^
  -DTBB_tbb_LIBRARY_RELEASE="%TBB_LIB%"
if errorlevel 1 ( echo CONFIGURE_FAILED & exit /b 2 )

echo === BUILD usd_m (static monolithic archive) ===
rem Heavy: ~1700 TUs compiled then aggregated into usd_m.lib. 30-60+ min cold.
cmake --build "%BUILD%" --target usd_m
if errorlevel 1 ( echo BUILD_FAILED & exit /b 3 )

if not exist "%BUILD%\usd_m.lib" ( echo USD_M_NOT_FOUND & exit /b 4 )
echo === usd_m.lib built ===
for %%F in ("%BUILD%\usd_m.lib") do echo   size=%%~zF bytes  path=%%F

rem Install so pxrConfig.cmake + headers + the Sdf plugInfo resource tree land
rem under %PREFIX% (the resource tree is needed at runtime for Sdf file formats).
echo === INSTALL to %PREFIX% ===
cmake --install "%BUILD%"
if errorlevel 1 ( echo INSTALL_FAILED & exit /b 5 )

echo === DONE_OK ===
endlocal
