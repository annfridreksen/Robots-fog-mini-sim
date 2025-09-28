# robots-fog-mini-sim

Готовый шаблон проекта под папку **D:\PythonProjects\robots-fog-mini-sim** и VS Code.
Подойдёт тебе и ребятам (16+).

## Быстрый старт (Windows, VS Code)
1. Скопируй папку проекта в `D:\PythonProjects\` чтобы путь был `D:\PythonProjects\robots-fog-mini-sim`.
2. Открой папку в VS Code: **File → Open Folder…**
3. Создай окружение и установи инструменты (вариант А — скриптом):
   - Открой `scripts/setup_venv_windows.ps1` → **Run** (или открой терминал PowerShell и запусти `.\scripts\setup_venv_windows.ps1`).
   - Он создаст `.venv`, обновит pip и поставит инструменты разработчика.
   - Если PowerShell запрещает запуск скриптов — запусти в терминале: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
4. Выбери интерпретатор: **Ctrl+Shift+P → Python: Select Interpreter → .venv**.
5. Запусти `main.py` кнопкой ▶️ или F5.

## Терминал вручную (без скрипта)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
python main.py
```

## Структура
```
.vscode/               # настройки запуска и форматирования
modules/               # модули проекта
scripts/               # скрипты для удобного старта
main.py                # точка входа (мини-симуляция)
requirements.txt       # боевые зависимости (пока пусто)
requirements-dev.txt   # инструменты: black, ipykernel
README.md
```

## Мини‑задача (на 1–2 часа)
1) Добавь четвёртого робота — монитор (считает, сколько задач выполнено).
2) Замени тексты задач под свою тему (умный дом / склад / парк дронов).
3) Запусти и покажи наставнику понятный “лог” в консоли.

Удачи! 🚀
