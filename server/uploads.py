"""Загрузка и удаление файлов библиотеки: правила структуры, журнал операций, уборка.

Правила (docs/TZ_server_panel.md §3) — строго «Исполнитель/Альбом/трек»:
аудио на глубине 3, картинки на глубине 3 или 4 внутри covers/, остальное нельзя.
Имена сравниваются без учёта регистра: диск в NTFS, в Windows это один файл.

Журнал — отдельная uploads.db рядом с library.db: library.db бывает пересоздана,
а история загрузок (и возможность откатить свою) теряться не должна.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

log = logging.getLogger("uvicorn.error")

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4"}   # = indexer.SUPPORTED_FORMATS
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
COVERS_DIR = "covers"
PART_SUFFIX = ".part"

# Недопустимо в именах Windows. Диск подключают и к Windows — там такие имена битые.
_BAD_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
# Папки, в которые indexer не заходит (indexer.SKIP_DIRS): исполнитель или альбом
# с таким именем был бы невидим для плеера
_SKIP_DIRS = {"covers", "lost+found", "$recycle.bin", "system volume information", ".cache"}
MAX_NAME = 200   # символов; NTFS держит 255, запас — на суффикс .part


class RuleError(ValueError):
    """Путь нарушает §3. Текст — для пользователя."""


def file_kind(name: str) -> str | None:
    ext = os.path.splitext(name)[1].lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def check_name(name: str) -> None:
    if not name or name in (".", ".."):
        raise RuleError("пустое имя")
    if len(name) > MAX_NAME:
        raise RuleError(f"имя длиннее {MAX_NAME} символов: {name[:40]}…")
    if name.startswith("."):
        raise RuleError(f"имя начинается с точки: {name}")
    if name[-1] in ". ":
        raise RuleError(f"точка или пробел в конце имени: {name!r}")
    bad = sorted(set(name) & _BAD_CHARS)
    if bad:
        shown = " ".join(c if c.isprintable() else f"\\x{ord(c):02x}" for c in bad)
        raise RuleError(f"недопустимые символы {shown} в имени: {name}")
    if os.path.splitext(name)[0].lower() in _RESERVED:
        raise RuleError(f"зарезервированное имя Windows: {name}")


def check_upload_path(rel: str) -> list[str]:
    """Проверка пути загружаемого файла по §3. Возвращает части пути."""
    if not rel or rel.startswith("/") or "\\" in rel:
        raise RuleError("путь должен быть относительным, через /")
    parts = rel.split("/")
    for p in parts:
        check_name(p)
    for p in parts[:2]:
        if p.lower() in _SKIP_DIRS:
            raise RuleError(f"папка «{p}» не может быть исполнителем или альбомом")
    kind = file_kind(parts[-1])
    if kind == "audio":
        if len(parts) != 3:
            raise RuleError("трек должен лежать в «Исполнитель/Альбом/»")
    elif kind == "image":
        if len(parts) == 4:
            if parts[2].lower() != COVERS_DIR:
                raise RuleError("картинка в подпапке альбома может быть только в covers/")
        elif len(parts) != 3:
            raise RuleError("картинка — в папке альбома или в covers/")
    else:
        raise RuleError(f"тип файла не переносится: {parts[-1]}")
    return parts


def resolve_ci(root: Path, parts: list[str]) -> Path:
    """Путь в библиотеке, где каждая существующая часть взята с регистром диска.

    На Pi NTFS смонтирован в Linux, и там Muse и muse — разные папки. Загрузка в
    «muse/…» должна попасть в существующую «Muse/», иначе в Windows будет каша.
    Несуществующие части остаются как пришли."""
    cur = root
    for i, part in enumerate(parts):
        # имена из листинга, а не exists(): в Windows exists() не смотрит на регистр
        # и вернул бы путь с регистром запроса, а не диска
        found = None
        low = part.lower()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if e.name == part:
                        found = part
                        break
                    if found is None and e.name.lower() == low:
                        found = e.name
        except OSError:      # папки ещё нет
            pass
        if found is None:
            return cur.joinpath(*parts[i:])
        cur = cur / found
    return cur


def remove_empty_dirs(root: Path, start: Path) -> list[str]:
    """Удаляет пустые папки от start вверх, не выше корня. Возвращает удалённые (rel)."""
    removed = []
    root = root.resolve()
    cur = start
    while cur != root and root in cur.parents:
        try:
            cur.rmdir()          # только пустую; непустая — OSError, и на этом стоп
        except OSError:
            break
        removed.append(cur.relative_to(root).as_posix())
        cur = cur.parent
    return removed


def clean_parts(root: Path) -> int:
    """Удаляет недокачанные *.part, оставшиеся после выключения посреди загрузки."""
    n = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(PART_SUFFIX):
                try:
                    os.remove(os.path.join(dirpath, f))
                    n += 1
                except OSError as e:
                    log.warning("не удалить %s: %s", f, e)
    if n:
        log.info("удалено недокачанных файлов: %d", n)
    return n


def list_files(root: Path, folder: Path) -> list[dict]:
    """Все аудио и картинки под папкой, рекурсивно, включая covers/. Для скачивания."""
    out = []
    root = root.resolve()
    for dirpath, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            kind = file_kind(f)
            if kind is None or f.startswith("."):
                continue
            p = Path(dirpath) / f
            try:
                size = p.stat().st_size
            except OSError:
                continue
            out.append({"rel_path": p.relative_to(root).as_posix(), "size": size, "kind": kind})
    out.sort(key=lambda x: x["rel_path"].lower())
    return out


def list_dir(root: Path, folder: Path) -> dict:
    """Содержимое одной папки для файлового менеджера плеера. Без обхода вглубь:
    в корне это тысячи исполнителей, и подсчёт файлов в каждом обошёл бы весь диск."""
    root = root.resolve()
    dirs, files = [], []
    with os.scandir(folder) as it:
        for e in it:
            if e.name.startswith("."):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    dirs.append({"name": e.name, "path": Path(e.path).relative_to(root).as_posix()})
                elif e.is_file(follow_symlinks=False):
                    kind = file_kind(e.name)
                    if kind:
                        files.append({"name": e.name, "path": Path(e.path).relative_to(root).as_posix(),
                                      "size": e.stat().st_size, "kind": kind})
            except OSError:
                continue
    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())
    return {"dirs": dirs, "files": files}


# ------------------------------------------------------------- журнал операций

SCHEMA = """
CREATE TABLE IF NOT EXISTS ops (
    op_id   TEXT PRIMARY KEY,
    who     TEXT NOT NULL,          -- имя из [Tokens]; '' — сервер открыт
    folder  TEXT NOT NULL,          -- куда грузили (для списка)
    created INTEGER NOT NULL,
    undone  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS files (
    op_id    TEXT NOT NULL REFERENCES ops(op_id),
    rel_path TEXT NOT NULL,
    size     INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,      -- откат удалит файл, только если size и mtime те же
    created  INTEGER NOT NULL,
    removed  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS files_op ON files(op_id);
"""


class Journal:
    def __init__(self, path: Path):
        self.path = path
        with closing(self._conn()) as con, con:
            con.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode = WAL")
        return con

    def new_op(self, who: str, folder: str) -> str:
        op_id = uuid.uuid4().hex
        with closing(self._conn()) as con, con:
            con.execute("INSERT INTO ops(op_id, who, folder, created) VALUES (?,?,?,?)",
                        (op_id, who, folder, int(time.time())))
        return op_id

    def get_op(self, op_id: str) -> sqlite3.Row | None:
        with closing(self._conn()) as con:
            return con.execute("SELECT * FROM ops WHERE op_id = ?", (op_id,)).fetchone()

    def add_file(self, op_id: str, rel_path: str, size: int, mtime_ns: int) -> None:
        with closing(self._conn()) as con, con:
            con.execute("INSERT INTO files(op_id, rel_path, size, mtime_ns, created) VALUES (?,?,?,?,?)",
                        (op_id, rel_path, size, mtime_ns, int(time.time())))

    def files(self, op_id: str, only_present: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT rowid, * FROM files WHERE op_id = ?" + (" AND removed = 0" if only_present else "")
        with closing(self._conn()) as con:
            return con.execute(sql + " ORDER BY rel_path", (op_id,)).fetchall()

    def mark_removed(self, rowids: list[int]) -> None:
        with closing(self._conn()) as con, con:
            con.executemany("UPDATE files SET removed = 1 WHERE rowid = ?", [(r,) for r in rowids])

    def mark_undone(self, op_id: str) -> None:
        with closing(self._conn()) as con, con:
            con.execute("UPDATE ops SET undone = 1 WHERE op_id = ?", (op_id,))

    def list_ops(self, who: str | None, limit: int = 100) -> list[dict]:
        """Операции, где загружен хотя бы один файл. who=None — все (для администратора)."""
        sql = """SELECT o.op_id, o.who, o.folder, o.created, o.undone,
                        COUNT(f.rowid) AS files, COALESCE(SUM(f.size), 0) AS bytes,
                        COALESCE(SUM(f.removed = 0), 0) AS present
                 FROM ops o JOIN files f ON f.op_id = o.op_id"""
        args: tuple = ()
        if who is not None:
            sql += " WHERE o.who = ?"
            args = (who,)
        sql += " GROUP BY o.op_id ORDER BY o.created DESC LIMIT ?"
        with closing(self._conn()) as con:
            return [dict(r) for r in con.execute(sql, args + (limit,))]


# ------------------------------------------------------------- отложенный скан

class ScanScheduler:
    """Скан после изменений файлов, с задержкой: альбом грузится по файлу,
    и запускать скан после каждого незачем. Каждый новый вызов сдвигает таймер."""

    def __init__(self, run, busy_exc: type[Exception], delay: float = 5.0, retry: float = 30.0):
        self._run = run           # функция без аргументов
        self._busy = busy_exc     # её исключение «скан уже идёт» — тогда повтор позже
        self._delay = delay
        self._retry = retry
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def schedule(self, delay: float | None = None) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay if delay is None else delay, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        try:
            self._run()
        except self._busy as e:
            # идёт другой скан: он мог начаться до изменения и не увидеть его
            log.info("скан после изменения файлов отложен: %s", e)
            self.schedule(self._retry)
        except Exception:
            log.exception("скан после изменения файлов упал")
