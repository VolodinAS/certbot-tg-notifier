# certbot-tg-notifier
Каждый день отправляет в созданный Вами Телеграм-бот оповещение об окончании срока действия SSL-сертификата

# Установка:

## 🔧 Шаг 1: Создай папку в `/opt`

```bash
sudo mkdir -p /opt/certbot-tg-notifier
```

---

## 📥 Шаг 2: Клонируй репозиторий

```bash
sudo git clone https://github.com/VolodinAS/certbot-tg-notifier.git /opt/certbot-tg-notifier
```

---

## 🛠 Шаг 3: Создай файл конфигурации `.config`

> ⚠️ В твоём репозитории пока нет файла `.config`, поэтому создадим его.

```bash
sudo nano /opt/certbot-tg-notifier/.config
```

Вставь содержимое:

```ini
# API ключ Telegram-бота
bot_api_key=Ключ_бота

# ID администраторов через запятую
admins=123456789,987654321
```

> 💡 Замени `123456789,987654321` на свои реальные Telegram ID (можно узнать у бота @userinfobot)

Сохрани: `Ctrl+O` → Enter → `Ctrl+X`

---

## 🔐 Шаг 4: Установи правильные права

```bash
# Сам скрипт — исполняемый
sudo chmod +x /opt/certbot-tg-notifier/main.py

# Конфиг — только для владельца
sudo chmod 600 /opt/certbot-tg-notifier/.config
```

---

## 🔄 Шаг 5: Создай скрипт `certbotrestart` (обновление + настройка)

Создадим **shell-скрипт**, который будет обновлять проект и настраивать окружение.

```bash
sudo nano /opt/certbot-tg-notifier/update-and-setup.sh
```

Вставь:

```bash
#!/bin/bash

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.config"
CRON_JOB="0 12 * * * /usr/bin/python3 $SCRIPT_DIR/main.py >> /var/log/certbot-tg-notifier.log 2>&1"
CRON_MARKER="# certbot-tg-notifier"

echo "→ Обновляю проект из GitHub..."

# Убедимся, что это git-репозиторий
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo "❌ Ошибка: папка не является git-репозиторием"
    exit 1
fi

# Обновляем
git -C "$SCRIPT_DIR" fetch origin
git -C "$SCRIPT_DIR" reset --hard origin/master

echo "✅ Проект обновлён"

# Проверяем config
if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️ Файл config не найден. Создаю шаблон..."
    cat > "$CONFIG_FILE" << 'EOF'
# API ключ Telegram-бота
bot_api_key=YOUR_BOT_TOKEN_HERE

# ID администраторов через запятую
admins=123456789,987654321

# Успех тоже отправить в Телеграм
notify_success=true/false
EOF
    chmod 600 "$CONFIG_FILE"
    echo "✅ Шаблон config создан. Заполни его!"
    exit 1
else
    echo "✅ Файл config найден"
fi

# Проверяем, добавлен ли cron
if crontab -l | grep -Fq "$CRON_MARKER"; then
    echo "✅ Cron-задача уже добавлена"
else
    echo "→ Добавляю cron-задачу..."
    (crontab -l 2>/dev/null; echo "$CRON_MARKER"; echo "$CRON_JOB") | crontab -
    echo "✅ Cron-задача добавлена"
fi

# Создаём лог-файл, если его нет
sudo touch /var/log/certbot-tg-notifier.log
sudo chmod 644 /var/log/certbot-tg-notifier.log

echo "✅ Настройка завершена"
```

Сохрани и сделай исполняемым:

```bash
sudo chmod +x /opt/certbot-tg-notifier/update-and-setup.sh
```

---

## 🎯 Шаг 6: Добавь алиас `certbotrestart`

Добавим алиас, чтобы можно было просто писать `certbotrestart`.

### Для root (если ты входишь как root):

```bash
echo "alias certbotrestart='/opt/certbot-tg-notifier/update-and-setup.sh'" >> ~/.bashrc
source ~/.bashrc
```

### Для другого пользователя (например, `deploy`):

```bash
sudo -u deploy bash -c 'echo "alias certbotrestart=\"/opt/certbot-tg-notifier/update-and-setup.sh\"" >> ~deploy/.bashrc'
```

---

## ✅ Шаг 7: Первый запуск

```bash
certbotrestart
```

Он:
- Скачает последнюю версию
- Проверит `config`
- Добавит `cron`, если нужно

---

## 🧪 Шаг 8: Протестируй работу

Запусти вручную:

```bash
python3 /opt/certbot-tg-notifier/notify.py
```

Если всё настроено — должно прийти сообщение в Telegram (или ничего, если все сертификаты живы).

---

## 📝 Логи

Смотри, если что-то пошло не так:

```bash
tail -f /var/log/certbot-tg-notifier.log
```
