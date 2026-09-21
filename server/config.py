"""Чтение server.ini. Один источник настроек для indexer.py и server.py.

Все пути в ini считаются относительно папки, где лежит сам ini, а не текущей
рабочей директории: под systemd cwd будет `/`, и `./music` уйдёт не туда.
Каждое поле — с fallback: старый ini без новой секции не должен ронять запуск.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INI_PATH = BASE_DIR / "server.ini"


@dataclass(frozen=True)
class Config:
    root: Path              # корень библиотеки
    covers_dir: Path        # <sha1>_50.jpg / <sha1>_full.jpg
    db_path: Path           # library.db
    batch_size: int
    auto_rescan_minutes: int
    host: str
    port: int
    token: str | None


def _abs(base: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def load_config(ini_path: Path = INI_PATH) -> Config:
    # inline_comment_prefixes обязателен: в ini есть `root = ./music ; на Pi: /mnt/music`,
    # без него значение станет "./music ; на Pi: /mnt/music" целиком
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cp.read(ini_path, encoding="utf-8")
    base = ini_path.resolve().parent

    token = cp.get("Server", "token", fallback="").strip()
    return Config(
        root=_abs(base, cp.get("Library", "root", fallback="./music")),
        covers_dir=_abs(base, cp.get("Library", "covers_dir", fallback="./covers")),
        db_path=_abs(base, cp.get("Library", "db", fallback="./library.db")),
        batch_size=cp.getint("Index", "batch_size", fallback=200),
        auto_rescan_minutes=cp.getint("Index", "auto_rescan_minutes", fallback=0),
        host=cp.get("Server", "host", fallback="127.0.0.1"),
        port=cp.getint("Server", "port", fallback=8000),
        token=token or None,
    )
