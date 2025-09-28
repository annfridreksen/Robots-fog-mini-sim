# Публикация в GitHub или GitLab (простая версия)

## 0) Важно
- Делай **команды по одной строке**, нажимая Enter после каждой.
- Создавай **пустой** репозиторий в браузере (без README, .gitignore, LICENSE), чтобы не было конфликтов.

## 1) Подготовка локально
Открой терминал VS Code (**Terminal → New Terminal**) и выполни:
```bash
git init
git add .
git commit -m "Initial commit: robots-fog-mini-sim"
git branch -M main
```

## 2) Создай репозиторий в браузере
- GitHub: Profile → Repositories → New → Name: `robots-fog-mini-sim` → **Create repository** (ничего лишнего не добавляй).
- GitLab: Menu → Projects → Create new project → Blank → Name: `robots-fog-mini-sim` → **Create project** (без README).

Скопируй URL репозитория (он выглядит как `https://.../robots-fog-mini-sim.git`).

## 3) Привяжи и отправь
В терминале:
```bash
git remote add origin <ВСТАВЬ_СЮДА_URL>
git push -u origin main
```

VS Code может предложить войти в GitHub/GitLab через браузер — соглашайся.
Если попросит “username/password”: используй логин и **Personal Access Token** как пароль.

## 4) Если по ошибке создала репозиторий с README
Самый простой способ для новичка — удалить репозиторий в браузере и создать **новый пустой**.

(Альтернатива для уверенных пользователей)
```bash
git pull origin main --allow-unrelated-histories
git push -u origin main
```
