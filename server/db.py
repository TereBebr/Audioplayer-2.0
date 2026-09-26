"""library.db: схема, соединение, таблица meta.

Единственный писатель — indexer.scan(). Сервер только читает.
WAL-режим даёт читателям работать, пока идёт скан.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path    TEXT    NOT NULL UNIQUE,   -- 'Rock/Muse/Absolution/04 Hysteria.flac', всегда POSIX
    dir         TEXT    NOT NULL,          -- 'Rock/Muse/Absolution'; '' для корня
    name        TEXT    NOT NULL,          -- из тегов, иначе имя файла без расширения
    author      TEXT,
    album       TEXT,
    year        TEXT,
    genre       TEXT,
    duration    REAL,                      -- секунды
    sample_rate INTEGER,                   -- Гц
    bitrate     INTEGER,                   -- кбит/с (так отдаёт tags.read_tags)
    channels    INTEGER,
    bits        INTEGER,                   -- глубина, NULL для mp3/ogg
    size        INTEGER NOT NULL,          -- байт
    mtime       INTEGER NOT NULL,          -- int(st_mtime)
    cover_hash  TEXT,                      -- sha1 байтов обложки; NULL = обложки нет
    seen_gen    INTEGER NOT NULL,          -- поколение скана, в котором файл видели последним
    missing     INTEGER NOT NULL DEFAULT 0 -- 1 = файла нет на диске, строка сохранена
);
CREATE INDEX IF NOT EXISTS idx_tracks_dir    ON tracks(dir);
CREATE INDEX IF NOT EXISTS idx_tracks_author ON tracks(author COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_album  ON tracks(album  COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_name   ON tracks(name   COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_seen   ON tracks(seen_gen);
CREATE INDEX IF NOT EXISTS idx_tracks_sizemt ON tracks(size, mtime);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn(db_path: Path | str) -> sqlite3.Connection:
    """Соединение с нужными PRAGMA. Закрывать через closing() или with."""
    con = sqlite3.connect(str(db_path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")   # в WAL это безопасно и заметно быстрее на SD/HDD
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: Path | str) -> None:
    """Создаёт схему, если её нет. Повторный вызов безопасен."""
    with get_conn(db_path) as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            logger.info("library.db создана, схема v%d", SCHEMA_VERSION)
        elif version != SCHEMA_VERSION:
            # Здесь будут миграции. Пока версии одна — просто не даём работать с чужой базой.
            raise RuntimeError(
                f"library.db имеет версию схемы {version}, код ожидает {SCHEMA_VERSION}")

        # uuid библиотеки: ping отдаёт его плееру, чтобы тот заметил пересозданную базу
        if meta_get(con, "library_uuid") is None:
            meta_set(con, "library_uuid", str(uuid.uuid4()))


# ---- meta ----

def meta_get(con: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row is not None else default


def meta_set(con: sqlite3.Connection, key: str, value) -> None:
    con.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, None if value is None else str(value)),
    )


def meta_all(con: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}


# ---- запросы, которые нужны серверу ----

def track_count(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) FROM tracks WHERE missing = 0").fetchone()[0]


def get_track(con: sqlite3.Connection, track_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()


def get_tracks(con: sqlite3.Connection, ids: list[int]) -> list[sqlite3.Row]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return con.execute(f"SELECT * FROM tracks WHERE id IN ({marks})", ids).fetchall()

def get_cover(con: sqlite3.Connection, id: int):
    row = con.execute("SELECT cover_hash FROM tracks WHERE id = ?", (id,)).fetchone()
    if not row or not row[0]:
        return None
    return row[0]
    
    

def tracks_in_dir(con: sqlite3.Connection, rel_dir: str) -> list[sqlite3.Row]:
    """Треки прямо в папке (без подпапок), для browse."""
    return con.execute(
        "SELECT * "
        "FROM tracks WHERE dir = ? AND missing = 0 ORDER BY name COLLATE NOCASE",
        (rel_dir,),
    ).fetchall()


def tracks_under_dir(con: sqlite3.Connection, rel_dir: str) -> list[sqlite3.Row]:
    """Треки в папке и всех подпапках, для «добавить папку в очередь».
    substr вместо LIKE/GLOB: в именах папок бывают %, _ и [ — их пришлось бы экранировать."""
    if rel_dir == "":
        return con.execute(
            "SELECT * "
            "FROM tracks WHERE missing = 0 ORDER BY rel_path").fetchall()
    prefix = rel_dir + "/"
    return con.execute(
        "SELECT * "
        "FROM tracks WHERE missing = 0 AND (dir = ? OR substr(dir, 1, ?) = ?) "
        "ORDER BY rel_path",
        (rel_dir, len(prefix), prefix),
    ).fetchall()


def search_tracks(con: sqlite3.Connection, query: str, limit: int = 200) -> list[sqlite3.Row]:
    q = query.strip()
    if not q:
        return []
    # LIKE-подстановки в пользовательском запросе экранируем сами
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{esc}%"
    return con.execute(
        "SELECT * FROM tracks "
        "WHERE missing = 0 AND (name LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\' "
        "OR album LIKE ? ESCAPE '\\') "
        "ORDER BY author COLLATE NOCASE, album COLLATE NOCASE, name COLLATE NOCASE LIMIT ?",
        (pat, pat, pat, limit),
    ).fetchall()
