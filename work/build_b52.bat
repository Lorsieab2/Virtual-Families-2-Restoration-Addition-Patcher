@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 1
cl @work\compile_helpers_b22.rsp
if errorlevel 1 exit /b 1
link @work\vf2_link_b27_arcade_behavior_restore.rsp /OUT:"C:\Users\Owner\Documents\Codex\2026-06-13\files-mentioned-by-the-user-virtual\outputs\VF2-Mobile-Furniture-With-Island-Events-B52-Body-Frame-Export-and-Hammock-Revert\Virtual Families 2 - Additive Mobile Furniture Pack.exe"
