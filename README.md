# robots-fog-mini-sim (simple)

Два файла визуализации:
1) viz_experiment.py — один график задержки + средняя задержка (одно число).
2) viz_phone_pipeline.py — задержка + размер буфера телефона.

Запуск (VS Code терминал):
```
python -m venv .venv
.\.venv\Scriptsctivate
python -m pip install --upgrade pip
pip install -r requirements.txt
python viz_experiment.py
python viz_phone_pipeline.py
```
