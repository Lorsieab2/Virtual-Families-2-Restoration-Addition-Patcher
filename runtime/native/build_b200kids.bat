@echo off
rem Build runtime\build\vf2kids_b200.dll (32-bit, static CRT, no runtime DLL dependency):
rem the Up to 28 Children companion DLL for the B200 executable.
rem Regenerate runtime\native\b200kids\b200kids_sites.h with tools\gen_b200_kids_sites.py first
rem if runtime\b200_kids_sites.py changed.
rem
rem   build_b200kids.bat          the shipped DLL
rem   build_b200kids.bat test     the harness DLL (exports the planning and state test entry points,
rem                               writes runtime\build\vf2kids_b200_test.dll)
setlocal
set ROOT=%~dp0..
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2kids_b200
if /I "%1"=="test" (
  set DEFS=/DB200KIDS_TEST
  set OUT=vf2kids_b200_test
)
cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200kids\b200kids.cpp" /Fo"%ROOT%\build\%OUT%.obj" /Fe"%ROOT%\build\%OUT%.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%ROOT%\build\%OUT%.dll" exit /b 1
