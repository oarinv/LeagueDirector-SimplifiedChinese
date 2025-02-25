@echo off
uv venv .venv
uv sync
uv run -m leaguedirector.app
