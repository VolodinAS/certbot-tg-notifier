#!/usr/bin/env python3

import subprocess
import re
from datetime import datetime
import sys
from pathlib import Path
import os


# Определяем BASE_DIR — папку, где лежит этот скрипт
BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / ".config"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(CONFIG_FILE)

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
    certs = []
    blocks = re.split(r"-{40,}", output)
    for block in blocks:
        name_match = re.search(r"Certificate Name:\s*(.+)", block)
        expiry_match = re.search(r"Expiry Date:\s*([\d\-:\+\s]+)", block)
        domains_match = re.search(r"Domains:\s*(.+)", block)

        if name_match and expiry_match:
            name = name_match.group(1).strip()
            expiry_str = expiry_match.group(1).strip()
            domains = domains_match.group(1).strip() if domains_match else name

            try:
                expiry_date = datetime.fromisoformat(expiry_str.replace("+00:00", "+00:00"))
                days_left = (expiry_date - datetime.now(expiry_date.tzinfo)).days
            except Exception as exc:
                print(f"Ошибка парсинга даты для {name}: {exc}")
                days_left = -1

            certs.append({
                "name": name,
                "domains": domains,
                "days_left": days_left
            })
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
        subprocess.run([
            "curl", "-s", "-X", "POST",
            f"https://api.telegram.org/bot{token}/sendMessage",
            "-d", f"chat_id={chat_id}",
            "-d", f"text={message}",
            "-d", "parse_mode=HTML"
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Не удалось отправить в чат {chat_id}: {e}")


def send_alert_to_admins(message):
    """Отправка алерта админам (для ошибок)"""
    try:
        config = load_config()
        token = config["bot_api_key"]
        chat_ids = [cid.strip() for cid in config["admins"].split(",") if cid.strip()]
        for chat_id in chat_ids:
            send_telegram_message(token, chat_id, message)
    except Exception:
        # Если даже конфиг сломан — ничего не поделать
        pass


def main():
    config = load_config()
    token = config["bot_api_key"]

    output = get_certificates()
    certs = parse_certificates(output)

    critical_certs = [c for c in certs if 0 <= c["days_left"] <= 7]
    expired_certs = [c for c in certs if c["days_left"] < 0]

    if not critical_certs and not expired_certs:
        return  # Ничего не отправляем

    lines = [
        "<b>ОПОВЕЩЕНИЕ</b>",
        "<b>ОБ ИСТЕЧЕНИИ</b>",
        "<b>СРОКОВ SSL-СЕРТИФИКАТОВ</b>",
        "<b>ДОМЕНОВ</b>",
        ""
    ]

    for cert in sorted(critical_certs, key=lambda x: x["days_left"]):
        lines.append(f"⚠️ Домен <code>{cert['domains']}</code> — осталось {format_days(cert['days_left'])}")

    for cert in expired_certs:
        lines.append(f"🚨 Домен <code>{cert['domains']}</code> — <b>СРОК ИССЯК</b>")

    message = "\n".join(lines)
    chat_ids = [cid.strip() for cid in config["admins"].split(",") if cid.strip()]

    for chat_id in chat_ids:
        send_telegram_message(token, chat_id, message)


if __name__ == "__main__":
    print("Начали...")
    main()