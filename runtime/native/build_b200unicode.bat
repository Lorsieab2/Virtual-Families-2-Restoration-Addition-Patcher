@echo off
rem Build runtime\build\vf2unicode_b200.dll (32-bit, static CRT, no runtime DLL dependency): the Unicode text
rem companion DLL ("Render Unicode with In-Game Fonts" / "Use Unicode Font (overrides in-game fonts)") for the B200
rem executable. Regenerate runtime\native\b200unicode\b200unicode_sites.h with tools\gen_b200_unicode_sites.py and
rem b200unicode_tables.h with tools\gen_b200_unicode_tables.py first if their sources changed.
rem
rem   build_b200unicode.bat          the shipped DLL
rem   build_b200unicode.bat test     the harness DLL (exports the planning test entry points,
rem                                  writes runtime\build\vf2unicode_b200_test.dll)
setlocal
set ROOT=%~dp0..
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2unicode_b200
if /I "%1"=="test" (
  set DEFS=/DB200UNICODE_TEST
  set OUT=vf2unicode_b200_test
)
cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200unicode\b200unicode.cpp" /Fo"%ROOT%\build\%OUT%.obj" /Fe"%ROOT%\build\%OUT%.dll" /link kernel32.lib gdi32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%ROOT%\build\%OUT%.dll" exit /b 1
