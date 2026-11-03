@echo off
rem Build runtime\build\vf2tr_b200.dll (32-bit, static CRT, no runtime DLL dependency): the Translations
rem companion DLL for the B200 executable.
rem Regenerate runtime\native\b200tr\b200tr_sites.h and b200tr_limits.h with tools\gen_b200_translations_sites.py first
rem if runtime\b200_translations_sites.py changed.
rem
rem   build_b200tr.bat          the shipped DLL
rem   build_b200tr.bat test     the harness DLL (exports B200Tr_TestInstall and friends,
rem                             writes runtime\build\vf2tr_b200_test.dll)
rem
rem VF2_TR_BUILD_DIR, when set, is the folder the DLL is written to instead of runtime\build (the tests build
rem their own copy there, so a DLL another test still has open is never relinked).
setlocal
set ROOT=%~dp0..
set OUTDIR=%ROOT%\build
if not "%VF2_TR_BUILD_DIR%"=="" set OUTDIR=%VF2_TR_BUILD_DIR%
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2tr_b200
if /I "%1"=="test" (
  set DEFS=/DB200TR_TEST
  set OUT=vf2tr_b200_test
)
cl /nologo /O2 /MT /TC /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200tr\b200tr.c" /Fo"%OUTDIR%\%OUT%.obj" /Fe"%OUTDIR%\%OUT%.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%OUTDIR%\%OUT%.dll" exit /b 1
