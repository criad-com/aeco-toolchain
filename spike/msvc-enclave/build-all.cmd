@echo off
setlocal enableextensions
rem =====================================================================
rem  build-all.cmd — one-shot production build of the self-contained
rem  AecoLandingC.dll on example-navis (MSVC enclave). Orchestrates:
rem     0. private patched copy of the OpenUSD source
rem     1. static monolithic OpenUSD  (usd_m.lib)   [heavy]
rem     2. AecoLandingC.dll against it + dumpbin acceptance
rem
rem  Prereqs:
rem     - VS 2022 BuildTools (vcvars64 + bundled ninja)
rem     - OpenUSD source at %OPENUSD_SRC%  (default C:\OpenUSD-src)
rem     - prebuilt third-party at %OPENUSD_ROOT% (default C:\OpenUSD): boost 1.86
rem       under src\boost_1_86_0, TBB under include/ + lib\tbb.lib
rem     - aeco-core's aeco\base + aeco\vendor trees copied into %AECO_SRC%
rem       (default: this script's dir) so CMakeLists-embed.txt resolves the
rem       in-tree includes. (In the recon workspace they live at
rem       C:\p4-aecoLandingC\aeco; point AECO_SRC there or copy them beside this.)
rem
rem  Env overrides: OPENUSD_SRC, OPENUSD_ROOT, USDSRC (patched copy),
rem                 USD_MONOLITH_ROOT, AECO_SRC, VCVARS
rem =====================================================================
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

if not defined OPENUSD_SRC       set "OPENUSD_SRC=C:\OpenUSD-src"
if not defined OPENUSD_ROOT      set "OPENUSD_ROOT=C:\OpenUSD"
if not defined USDSRC            set "USDSRC=C:\usd-embed-src"
if not defined USD_MONOLITH_ROOT set "USD_MONOLITH_ROOT=C:\usd-embed"
if not defined AECO_SRC          set "AECO_SRC=%HERE%"
if not defined VCVARS            set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

echo ============================================================
echo  STEP 0 : patched OpenUSD source copy at %USDSRC%
echo ============================================================
if not exist "%USDSRC%\CMakeLists.txt" (
    echo robocopy %OPENUSD_SRC% -^> %USDSRC% (excluding .git) ...
    robocopy "%OPENUSD_SRC%" "%USDSRC%" /E /NFL /NDL /NJH /NJS /NC /NS /XD ".git" >NUL
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%\apply-embed-patches.ps1" -UsdSrc "%USDSRC%"
if errorlevel 1 ( echo PATCH_FAILED & exit /b 10 )

echo ============================================================
echo  STEP 1 : static monolith usd_m.lib  (heavy, 30-60 min)
echo ============================================================
call "%HERE%\build-usd-monolith.cmd"
if errorlevel 1 ( echo MONOLITH_FAILED & exit /b 20 )

echo ============================================================
echo  STEP 2 : AecoLandingC.dll + dumpbin acceptance
echo ============================================================
rem CMake reads CMakeLists.txt by name; stage the embed one beside the aeco tree.
copy /Y "%HERE%\CMakeLists-embed.txt" "%AECO_SRC%\CMakeLists.txt" >NUL
set "SRCSAVE=%SRC%"
pushd "%AECO_SRC%"
call "%HERE%\build-landingc-embed.cmd"
set "RC=%errorlevel%"
popd
if not "%RC%"=="0" ( echo DLL_FAILED & exit /b 30 )

echo === ALL_DONE_OK ===
endlocal
