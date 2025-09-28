#!/usr/bin/env bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
echo "✅ Venv ready. Select it in VS Code: Python: Select Interpreter → .venv"
