# створює базу transport з нуля і виконує sql файли по черзі
import os
from pathlib import Path

import psycopg

HOST = os.getenv("PGHOST", "localhost")
USER = os.getenv("PGUSER", "postgres")
PASSWORD = os.getenv("PGPASSWORD", "postgres")
APP_DIR = Path(__file__).resolve().parent
SQL_DIR = APP_DIR.parent / "docs"
SQL_FILES = ["schema_init.sql", "views_procedures_triggers.sql", "test_init_data.sql"]


def find_port():
    # якщо на компі кілька версій postgres, нова може сидіти на 5433, 5434...
    ports = [os.getenv("PGPORT")] if os.getenv("PGPORT") else ["5432", "5433", "5434", "5435"]
    for port in ports:
        try:
            psycopg.connect(host=HOST, port=port, user=USER, password=PASSWORD,
                            dbname="postgres", connect_timeout=3).close()
            return port
        except psycopg.Error:
            pass
    raise SystemExit(f"не вдалось підключитись до postgres (порти {', '.join(ports)}, пароль '{PASSWORD}')")


port = find_port()
print("postgres знайдено на порту", port)

with psycopg.connect(host=HOST, port=port, user=USER, password=PASSWORD, dbname="postgres", autocommit=True) as conn:
    conn.execute("drop database if exists transport with (force)")
    conn.execute("create database transport")

with psycopg.connect(host=HOST, port=port, user=USER, password=PASSWORD, dbname="transport", autocommit=True) as conn:
    for name in SQL_FILES:
        print("виконую", name)
        conn.execute((SQL_DIR / name).read_text(encoding="utf-8"))

# щоб main.py знав куди підключатись
(APP_DIR / "db.txt").write_text(
    f"host={HOST} port={port} dbname=transport user={USER} password={PASSWORD}", encoding="utf-8")

print("база transport готова")
