@echo off
setlocal enableextensions
rem =====================================================================
rem  build-landingc-embed.cmd
rem
rem  Build the PRODUCTION self-contained AecoLandingC.dll against the static
rem  monolithic OpenUSD (usd_m.lib) produced by build-usd-monolith.cmd, then
rem  prove the acceptance criteria with dumpbin:
rem    - /exports    -> EXACTLY the 19 aeco_landing_* symbols (ABI v2, incl
rem                     aeco_landing_set_mesh), nothing else
rem    - /dependents -> only system + MSVC runtime (no usd_*.dll / python311 /
rem                     ideally no tbb.dll)
rem
rem  Drives CMakeLists-embed.txt. Expects aeco-core's aeco/base + aeco/vendor
rem  trees beside that file (repo root on the include path). Because CMake reads
rem  `CMakeLists.txt` by name, this script points -S at a staging dir where
rem  CMakeLists-embed.txt has been copied to CMakeLists.txt (build-all.cmd does
rem  this); if you run it directly, copy CMakeLists-embed.txt -> CMakeLists.txt
rem  in %SRC% first.
rem
rem  Env overrides:
rem    SRC                dir holding CMakeLists.txt (the embed one) + aeco/ tree
rem    BUILD              CMake binary dir      (default %SRC%\build-embed)
rem    USD_MONOLITH_ROOT  usd_m install         (default C:\usd-embed)
rem    OPENUSD_ROOT       TBB provider          (default C:\OpenUSD)
rem    VCVARS             vcvars64.bat
rem =====================================================================
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
if not defined BUILD             set "BUILD=%SRC%\build-embed"
if not defined USD_MONOLITH_ROOT set "USD_MONOLITH_ROOT=C:\usd-embed"
if not defined OPENUSD_ROOT      set "OPENUSD_ROOT=C:\OpenUSD"
if not defined VCVARS            set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

call "%VCVARS%" >NUL 2>&1
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
where cl      >NUL 2>&1 || ( echo NO_CL & exit /b 1 )
where ninja   >NUL 2>&1 || ( echo NO_NINJA & exit /b 1 )
where dumpbin >NUL 2>&1 || ( echo NO_DUMPBIN & exit /b 1 )

echo === CONFIGURE (embed / static monolith) ===
if exist "%BUILD%" rmdir /s /q "%BUILD%"
cmake -S "%SRC%" -B "%BUILD%" -G Ninja ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DUSD_MONOLITH_ROOT="%USD_MONOLITH_ROOT%" ^
  -DOPENUSD_ROOT="%OPENUSD_ROOT%"
if errorlevel 1 ( echo CONFIGURE_FAILED & exit /b 2 )

echo === BUILD AecoLandingC.dll ===
cmake --build "%BUILD%" --config Release --verbose
if errorlevel 1 ( echo BUILD_FAILED & exit /b 3 )

rem The DLL lands at the top of the build dir. Do NOT `for /r` — ninja creates a
rem CMakeFiles\ShowIncludes\ scratch dir whose NAME collides with the target and
rem would be matched first, sending dumpbin at a non-existent path.
set "DLL=%BUILD%\AecoLandingC.dll"
if not exist "%DLL%" (
    rem Fallback: first real match that is NOT under a CMakeFiles scratch dir.
    set "DLL="
    for /r "%BUILD%" %%F in (AecoLandingC.dll) do @echo %%~dpF| find /I "CMakeFiles" >NUL || set "DLL=%%F"
)
if not exist "%DLL%" ( echo DLL_NOT_FOUND & exit /b 4 )
echo DLL=%DLL%
for %%F in ("%DLL%") do echo SIZE=%%~zF bytes

echo === dumpbin /exports (expect EXACTLY 19 aeco_landing_*, ABI v2 incl set_mesh) ===
dumpbin /exports "%DLL%"

echo === dumpbin /dependents (expect only system + MSVC runtime) ===
dumpbin /dependents "%DLL%"

echo === DONE_OK ===
endlocal
