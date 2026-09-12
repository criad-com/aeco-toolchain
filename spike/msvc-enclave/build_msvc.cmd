@echo off
setlocal enableextensions
rem P4 MSVC-enclave recon: configure + build aecoLandingC.dll, then dumpbin /exports.
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "BUILD=%SRC%\build-msvc"

echo === vcvars64 ===
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
echo cl on path:
where cl
echo dumpbin on path:
where dumpbin

echo === configure ===
rem Prefer Ninja if present, else the VS generator (single-config).
where ninja >NUL 2>&1
if %errorlevel%==0 (
  cmake -S "%SRC%" -B "%BUILD%" -G Ninja -DCMAKE_BUILD_TYPE=Release
) else (
  cmake -S "%SRC%" -B "%BUILD%" -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release
)
if errorlevel 1 ( echo CONFIGURE_FAILED & exit /b 2 )

echo === build ===
cmake --build "%BUILD%" --config Release --verbose
if errorlevel 1 ( echo BUILD_FAILED & exit /b 3 )

echo === locate DLL ===
set "DLL="
for /r "%BUILD%" %%F in (AecoLandingC.dll) do set "DLL=%%F"
if "%DLL%"=="" ( echo DLL_NOT_FOUND & exit /b 4 )
echo DLL=%DLL%

echo === dumpbin /exports ===
dumpbin /exports "%DLL%"

echo === DONE_OK ===
endlocal
