@echo off
rem Build runtime\build\vf2unicode_b200.dll (32-bit, static CRT, no runtime DLL dependency): the Unicode text
rem companion DLL ("Render Unicode with In-Game Fonts" / "Use Unicode Font (overrides in-game fonts)") for the B200
rem executable. Regenerate runtime\native\b200unicode\b200unicode_sites.h with tools\gen_b200_unicode_sites.py and
rem b200unicode_tables.h with tools\gen_b200_unicode_tables.py first if their sources changed.
rem
rem   build_b200unicode.bat           the shipped DLL
rem   build_b200unicode.bat test      the harness DLL (exports the planning test entry points,
rem                                   writes runtime\build\vf2unicode_b200_test.dll)
rem   build_b200unicode.bat clip      "Copy and Paste in Text Boxes": the same source built as vf2clip_b200.dll
rem                                   (B200UNICODE_CLIP: only the clipboard keys, b200clip.inc)
rem   build_b200unicode.bat cliptest  its harness DLL (vf2clip_b200_test.dll)
rem
rem VF2_UNICODE_BUILD_DIR, when set, is the folder the DLL is written to instead of runtime\build (the tests build
rem their own copy there, so a DLL another test still has open is never relinked).
setlocal
set ROOT=%~dp0..
set OUTDIR=%ROOT%\build
if not "%VF2_UNICODE_BUILD_DIR%"=="" set OUTDIR=%VF2_UNICODE_BUILD_DIR%
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2unicode_b200
set LIBS=kernel32.lib gdi32.lib
if /I "%1"=="test" (
  set DEFS=/DB200UNICODE_TEST
  set OUT=vf2unicode_b200_test
)
if /I "%1"=="clip" (
  set DEFS=/DB200UNICODE_CLIP /wd4505
  set OUT=vf2clip_b200
  set LIBS=kernel32.lib gdi32.lib user32.lib
)
if /I "%1"=="cliptest" (
  set DEFS=/DB200UNICODE_CLIP /DB200UNICODE_TEST /wd4505
  set OUT=vf2clip_b200_test
  set LIBS=kernel32.lib gdi32.lib user32.lib
)
cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200unicode\b200unicode.cpp" /Fo"%OUTDIR%\%OUT%.obj" /Fe"%OUTDIR%\%OUT%.dll" /link %LIBS% /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%OUTDIR%\%OUT%.dll" exit /b 1

