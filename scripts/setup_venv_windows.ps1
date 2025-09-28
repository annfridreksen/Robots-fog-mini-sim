# Creates venv and installs dev tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
Write-Host "✅ Venv ready. Select it in VS Code: Python: Select Interpreter → .venv"
