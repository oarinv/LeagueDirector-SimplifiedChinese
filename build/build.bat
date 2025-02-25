@echo off
cd %~dp0
cd "${0%/*}"
uv venv .venv
uv pip install
uv pip install pyinstaller==6.6.0
.venv/bin/pyinstaller build.spec --windowed --noconfirm --workpath=out/build --distpath=out/dist
ISCC.exe install.iss
