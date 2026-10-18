@echo off
rem Build runtime\build\vf2time_b200.dll (32-bit, static CRT, no runtime DLL dependency):
rem the Time Controls companion DLL for the B200 executable.
rem Regenerate runtime\native\b200time\b200time_sites.h with tools\gen_b200_time_sites.py first
rem if runtime\b200_time_sites.py changed.
rem
rem   build_b200time.bat          the shipped DLL
rem   build_b200time.bat test     the harness DLL (exports the planning and state-machine
rem                               test entry points, writes runtime\build\vf2time_b200_test.dll)
setlocal
set ROOT=%~dp0..
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
set DEFS=
set OUT=vf2time_b200
if /I "%1"=="test" (
  set DEFS=/DB200TIME_TEST
  set OUT=vf2time_b200_test
)
cl /nologo /O2 /MT /EHsc /W4 /WX %DEFS% /LD /GS "%ROOT%\native\b200time\b200time.cpp" /Fo"%ROOT%\build\%OUT%.obj" /Fe"%ROOT%\build\%OUT%.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO /MANIFEST:EMBED || exit /b 1
if not exist "%ROOT%\build\%OUT%.dll" exit /b 1
