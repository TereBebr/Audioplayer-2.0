"""Пути и окружение приложения: одинаково работает в dev-режиме и в собранном .exe."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)

# Папка, рядом с которой лежат vlc_engine, assets, storage, конфиги и базы.
# В собранном виде это папка с .exe, в dev-режиме — папка проекта.
if FROZEN:
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def path(*parts):
    """Абсолютный путь внутри папки приложения."""
    return os.path.join(APP_DIR, *parts)


def setup():
    """Подготовка окружения. Вызывать первой строкой, до импорта flet и vlc."""
    # Весь код читает config.txt / app.db / queue.db относительными путями
    os.chdir(APP_DIR)

    # Готовый клиент Flet рядом с .exe — иначе flet при первом старте
    # качает с GitHub ~96 МБ и распаковывает их в ~/.flet
    client = path("flet_client")
    if os.path.isfile(os.path.join(client, "flet.exe")):
        os.environ.setdefault("FLET_VIEW_PATH", client)
