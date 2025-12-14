#!/usr/bin/env python3

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / ".config"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def load_config():
    if not CONFIG_FILE.exists():
        send_alert_to_admins("❌ Конфиг не найден: {CONFIG_FILE}")
        sys.exit(1)
    
    config = {}
    with open(CONFIG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def get_certificates():
    try:
        result = subprocess.run(
            ["certbot", "certificates"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        send_alert_to_admins(f"❌ Ошибка выполнения certbot: {e}")
        sys.exit(1)
    except FileNotFoundError:
        send_alert_to_admins("❌ certbot не установлен или не в PATH")
        sys.exit(1)


def parse_certificates(output):
    """
    Парсит вывод certbot certificates и возвращает список сертификатов.
    Каждый сертификат содержит: name, domains, days_left
    """
    certs = []
    
    # Разделяем вывод на блоки по "Certificate Name"
    blocks = re.findall(
        r"Certificate Name:\s*(.+?)(?=(?:\n\s*\n|Certificate Name:|$))",
        output,
        re.DOTALL
    )
    
    for block in blocks:
        # Убираем лишние отступы
        block = block.strip()
        
        # Ищем имя (уже получено, но проверим)
        name_match = re.match(r"(.+)", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        
        # Ищем домены
        domains_match = re.search(r"Domains:\s*([^\n]+)", block, re.IGNORECASE)
        if domains_match:
            domains = domains_match.group(1).strip()
        else:
            domains = name  # fallback
        
        # Ищем дату окончания
        expiry_match = re.search(r"Expiry Date:\s*([\d\-:\+\s]+)", block, re.IGNORECASE)
        if not expiry_match:
            days_left = -1
        else:
            expiry_str = expiry_match.group(1).strip()
            try:
                expiry_date = datetime.fromisoformat(expiry_str.replace("+00:00", "+00:00"))
                days_left = (expiry_date - datetime.now(expiry_date.tzinfo)).days
            except Exception as exc:
                print(f"Ошибка парсинга даты для {name}: {exc}")
                days_left = -1
        
        certs.append(
            {
                "name": name,
                "domains": domains,
                "days_left": days_left
            }
        )
    
    return certs


def format_days(days):
    if days < 0:
        return "СРОК ИССЯК"
    elif days == 0:
        return "сегодня!"
    elif days == 1:
        return "1 день"
    else:
        return f"{days} дня(ей)"


def send_telegram_message(token, chat_id, message):
    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                f"https://api.telegram.org/bot{token}/sendMessage",
                "-d", f"chat_id={chat_id}",
                "-d", f"text={message}",
                "-d", "parse_mode=HTML"
            ], check=True, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Не удалось отправить в чат {chat_id}: {e}")


def send_alert_to_admins(message):
    try:
        config = load_config()
        token = config["bot_api_key"]
        chat_ids = [cid.strip() for cid in config["admins"].split(",") if cid.strip()]
        for chat_id in chat_ids:
            send_telegram_message(token, chat_id, message)
    except Exception:
        pass


def main():
    config = load_config()
    token = config["bot_api_key"]
    notify_success = config.get("notify_success", "false").lower() == "true"
    
    output = get_certificates()
    certs = parse_certificates(output)
    
    # Сертификаты с истекающим сроком (≤7 дней и не просрочены)
    critical_certs = [c for c in certs if 0 <= c["days_left"] <= 7]
    # Просроченные
    expired_certs = [c for c in certs if c["days_left"] < 0]
    # Актуальные (>7 дней)
    valid_certs = [c for c in certs if c["days_left"] > 7]
    
    # Если есть проблемные — отправляем тревогу
    if critical_certs or expired_certs:
        lines = [
            "<b>ОПОВЕЩЕНИЕ</b>",
            "<b>ОБ ИСТЕЧЕНИИ</b>",
            "<b>СРОКОВ SSL-СЕРТИФИКАТОВ</b>",
            "<b>ДОМЕНОВ</b>",
            ""
        ]
        
        for cert in sorted(critical_certs, key=lambda x: x["days_left"]):
            lines.append(
                f"⚠️ Домен <code>{cert['domains']}</code> — осталось {format_days(cert['days_left'])}"
            )
        
        for cert in expired_certs:
            lines.append(f"🚨 Домен <code>{cert['domains']}</code> — <b>СРОК ИССЯК</b>")
        
        message = "\n".join(lines)
        chat_ids = [cid.strip() for cid in config["admins"].split(",") if cid.strip()]
        
        for chat_id in chat_ids:
            send_telegram_message(token, chat_id, message)
    
    # Если включено уведомление об успехе — отправляем список актуальных
    # Если включено уведомление об успехе — отправляем список актуальных
    elif notify_success and valid_certs:
        lines = [
            "<b>✅ АКТУАЛЬНЫЕ SSL-СЕРТИФИКАТЫ</b>",
            ""
        ]
        for cert in sorted(valid_certs, key=lambda x: x["days_left"]):
            lines.append(
                f"✅ Домен <code>{cert['domains']}</code> — актуален (дней: {cert['days_left']})"
            )
        
        message = "\n".join(lines)
        chat_ids = [cid.strip() for cid in config["admins"].split(",") if cid.strip()]
        
        for chat_id in chat_ids:
            send_telegram_message(token, chat_id, message)


if __name__ == "__main__":
    main()
