@echo off
rem Build runtime\build\vf2revive_b200.dll (32-bit, static CRT, no runtime DLL dependency): the Revive companion DLL
rem for the B200 executable. It holds no game address (the executable passes everything in its host table), so there
rem is no sites header to regenerate.
rem
rem   build_b200revive.bat          the shipped DLL
rem   build_b200revive.bat test     also the test harness, runtime\build\vf2revive_harness.exe (tests/test_b200_revive.py)
setlocal
set ROOT=%~dp0..
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
if "%VF2_VCVARS32%"=="" (
  echo Set VF2_VCVARS32 to the full path of Visual Studio's vcvars32.bat 1>&2
  exit /b 1
)
call "%VF2_VCVARS32%" >nul || exit /b 1
cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS "%ROOT%\native\b200revive\b200revive.cpp" /Fo"%ROOT%\build\vf2revive_b200.obj" /Fe"%ROOT%\build\vf2revive_b200.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%ROOT%\build\vf2revive_b200.dll" exit /b 1
if /I "%1"=="test" (
  cl /nologo /O2 /MT /EHsc /W4 /WX "%ROOT%\native\b200revive\revive_harness.cpp" /Fo"%ROOT%\build\vf2revive_harness.obj" /Fe"%ROOT%\build\vf2revive_harness.exe" /link kernel32.lib || exit /b 1
  if not exist "%ROOT%\build\vf2revive_harness.exe" exit /b 1
  cl /nologo /O2 /MT /W4 /WX /LD "%ROOT%\native\b200revive\skin_standin.cpp" /Fo"%ROOT%\build\vf2skin_standin.obj" /Fe"%ROOT%\build\vf2skin_standin.dll" /link kernel32.lib || exit /b 1
)
exit /b 0
