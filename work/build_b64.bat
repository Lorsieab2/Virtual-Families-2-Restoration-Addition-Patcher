@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b %errorlevel%

cl @work\compile_helpers_b22.rsp
if errorlevel 1 exit /b %errorlevel%

if not exist "C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\outputs\VF2-Mobile-Furniture-With-Island-Events-B64-VF3-TV-Animation-Scale" mkdir "C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\outputs\VF2-Mobile-Furniture-With-Island-Events-B64-VF3-TV-Animation-Scale"

link @work\vf2_link_b27_arcade_behavior_restore.rsp "C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\work\patched_mobile_furniture_pack_objs\vf2_debug_features.obj" /OUT:"C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\outputs\VF2-Mobile-Furniture-With-Island-Events-B64-VF3-TV-Animation-Scale\Virtual Families 2 - Additive Mobile Furniture Pack.exe"
exit /b %errorlevel%
