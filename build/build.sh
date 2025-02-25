#!/bin/bash
cd "${0%/*}"
uv run pyinstaller build.spec 
