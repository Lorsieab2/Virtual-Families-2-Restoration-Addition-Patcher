@echo off

rem Build runtime\build\vf2skin_b200.dll (32-bit, static CRT, no runtime DLL dependency): the Skin Tones companion

rem DLL for the B200 executable (loaded by the Family History DLL, vf2history_b200.dll).

rem Regenerate runtime\native\b200skin\b200skin_sites.h with tools\gen_b200_skin_sites.py, skin_masks.h (and the

rem masks) with tools\gen_b200_skin_masks.py and skin_tables.h with tools\gen_b200_skin_tables.py first if they

rem changed.

rem

rem   build_b200skin.bat          the shipped DLL

rem   build_b200skin.bat test     the harness DLL (exports B200Skin_TestScanAddress, writes vf2skin_b200_test.dll)

rem

rem Set VF2_SKIN_BUILD_DIR to build somewhere other than runtime\build (the tests give each run its own folder).

setlocal

set ROOT=%~dp0..

set "BUILD=%ROOT%\build"

if not "%VF2_SKIN_BUILD_DIR%"=="" set "BUILD=%VF2_SKIN_BUILD_DIR%"

if not exist "%BUILD%" mkdir "%BUILD%"

if "%VF2_VCVARS32%"=="" (

  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2

  exit /b 1

)

call "%VF2_VCVARS32%" >nul || exit /b 1

set DEFS=

set OUT=vf2skin_b200

if /I "%1"=="test" (

  set DEFS=/DB200SKIN_TEST

  set OUT=vf2skin_b200_test

)

cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200skin\b200skin.cpp" /Fo"%BUILD%\%OUT%.obj" /Fe"%BUILD%\%OUT%.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1

if not exist "%BUILD%\%OUT%.dll" exit /b 1

