@echo off
rem Build runtime\build\vf2titlebox_b200.dll (32-bit, static CRT, no runtime DLL dependency):
rem the Title Screen Player Name Box companion DLL for the B200 executable.
rem Regenerate runtime\native\b200titlebox\b200titlebox_sites.h with tools\gen_b200_titlebox_sites.py first
rem if runtime\b200_titlebox_sites.py changed.
rem
rem   build_b200titlebox.bat          the shipped DLL
rem   build_b200titlebox.bat test     the harness DLL (exports the planning test entry points,
rem                                   writes runtime\build\vf2titlebox_b200_test.dll)
rem
rem VF2_TITLEBOX_BUILD_DIR, when set, is the folder the DLL is written to instead of runtime\build (the tests build
rem their own copy there, so a DLL another test still has open is never relinked).
setlocal
set ROOT=%~dp0..
set OUTDIR=%ROOT%\build
if not "%VF2_TITLEBOX_BUILD_DIR%"=="" set OUTDIR=%VF2_TITLEBOX_BUILD_DIR%
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2titlebox_b200
if /I "%1"=="test" (
  set DEFS=/DB200TITLEBOX_TEST
  set OUT=vf2titlebox_b200_test
)
cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200titlebox\b200titlebox.cpp" /Fo"%OUTDIR%\%OUT%.obj" /Fe"%OUTDIR%\%OUT%.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%OUTDIR%\%OUT%.dll" exit /b 1
