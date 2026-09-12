@echo off
setlocal enableextensions
rem Variant B: compile the aeco/USD-consuming TUs with PXR_STATIC so all pxr
rem ARCH_EXPORT-based macros (incl. AECOLANDING_API/AECOBASE_API) go empty and
rem the .def becomes the COMPLETE export story => expect EXACTLY 18 exports.
rem This mirrors the production static-embed compile posture. We still link the
rem shared USD import libs here (recon), which is the one impurity vs production.
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "BUILD=%SRC%\build-pxrstatic"

call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >NUL 2>&1

if exist "%BUILD%" rmdir /s /q "%BUILD%"
cmake -S "%SRC%" -B "%BUILD%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DAECO_PXR_STATIC=ON
if errorlevel 1 ( echo CONFIGURE_FAILED & exit /b 2 )
cmake --build "%BUILD%" --config Release
if errorlevel 1 ( echo BUILD_FAILED & exit /b 3 )

set "DLL=%BUILD%\AecoLandingC.dll"
if not exist "%DLL%" ( echo DLL_NOT_FOUND & exit /b 4 )
echo === EXPORT COUNT + list ===
dumpbin /exports "%DLL%"
echo === DONE_OK ===
endlocal
