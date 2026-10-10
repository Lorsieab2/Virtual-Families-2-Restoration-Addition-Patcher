@echo off
rem Build runtime\build\vf2fun.dll (32-bit, static CRT, no runtime DLL dependency).
rem Regenerate runtime\native\vf2fun\vf2fun_sites.h with tools\gen_sites.py first
rem if runtime\vf2_runtime_sites.py changed.
setlocal
set ROOT=%~dp0..
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS "%ROOT%\native\vf2fun\vf2fun.cpp" /Fo"%ROOT%\build\\" /Fe"%ROOT%\build\vf2fun.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1
if not exist "%ROOT%\build\vf2fun.dll" exit /b 1
