@echo off
cd %~dp0
uv run pyinstaller build.spec 
ISCC.exe install.iss
