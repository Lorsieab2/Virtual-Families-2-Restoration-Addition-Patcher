@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b %errorlevel%

cl @work\compile_helpers_b22.rsp
if errorlevel 1 exit /b %errorlevel%

if "%VF2_BUILD_OUT%"=="" set "VF2_BUILD_OUT=outputs\VF2-Mobile-Furniture-With-Island-Events-B119-Evict-Text-IslandOverlay"
if "%VF2_OUTPUT_EXE%"=="" set "VF2_OUTPUT_EXE=Virtual Families 2 - Additive Mobile Furniture Pack.exe"
if not exist "%VF2_BUILD_OUT%" mkdir "%VF2_BUILD_OUT%"

set "LINK_RSP=%TEMP%\vf2_link_b119_no_out.rsp"
findstr /B /V /C:"/OUT:" work\vf2_link_b27_arcade_behavior_restore.rsp > "%LINK_RSP%"
if errorlevel 1 exit /b %errorlevel%

link @"%LINK_RSP%" "work\patched_mobile_furniture_pack_objs\vf2_debug_features.obj" "work\patched_mobile_furniture_pack_objs\vf2_mobile_renovations.obj" /OUT:"%VF2_BUILD_OUT%\%VF2_OUTPUT_EXE%"
exit /b %errorlevel%
