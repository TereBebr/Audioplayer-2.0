"""Индексатор библиотеки: обходит корень, читает теги, наполняет library.db.

Запуск:
    python indexer.py             инкрементальный скан
    python indexer.py --full      перечитать теги у всех файлов
    python indexer.py --purge     удалить строки с missing = 1 и обложки без ссылок
    python indexer.py --stats     состояние базы

Из server.py вызывается scan() в фоновом потоке — это POST /api/rescan.
Диск только читается. Строки без --purge не удаляются: пропавший файл получает
missing = 1, а его id остаётся — на него ссылаются плейлисты плеера.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import logging
import os
import sqlite3
import sys
import threading
import time
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import db
import tags as tagreader
from config import Config, load_config

logger = logging.getLogger("indexer")

SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4"}

# Папки, в которые обход не заходит. Сравнение без учёта регистра.
SKIP_DIRS = {"covers", "lost+found", "$recycle.bin", "system volume information", ".cache"}

# Если предыдущий скан помечен как идущий дольше этого — считаем его упавшим
STALE_LOCK_SEC = 3600

# tags.read_tags отдаёт ключи в том виде, как в плеере; здесь — их имена в базе
TAG_KEYS = {
    "Название": "name",
    "Автор": "author",
    "Альбом": "album",
    "Год": "year",
    "Жанр": "genre",
    "Длительность": "duration",
    "Частота": "sample_rate",
    "Битрейт": "bitrate",
    "Каналы": "channels",
    "Глубина Бит": "bits",
    "Обложка": "cover",
}

# Один процесс — один скан. Для сервера, где rescan может прилететь дважды.
_scan_lock = threading.Lock()


@dataclass
class ScanReport:
    gen: int = 0
    seen: int = 0          # файлов на диске с поддерживаемым расширением
    unchanged: int = 0     # size+mtime совпали, файл не открывался
    added: int = 0
    updated: int = 0       # size или mtime изменились, теги перечитаны
    renamed: int = 0
    missing: int = 0       # помечены missing = 1 в этом скане
    restored: int = 0      # были missing, снова нашлись
    covers_written: int = 0
    errors: int = 0
    aborted: str | None = None
    seconds: float = 0.0
    error_files: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.aborted:
            return f"скан прерван: {self.aborted}"
        return (f"gen={self.gen} seen={self.seen} unchanged={self.unchanged} "
                f"added={self.added} updated={self.updated} renamed={self.renamed} "
                f"missing={self.missing} restored={self.restored} "
                f"covers={self.covers_written} errors={self.errors} "
                f"time={self.seconds:.1f}s")


class ScanInProgress(RuntimeError):
    pass


class ScanAborted(RuntimeError):
    """Ожидаемое прерывание (пустой корень и т.п.) — без трейсбека в логе."""


# ---------------------------------------------------------------- обход диска

@dataclass(frozen=True)
class FileEntry:
    rel_path: str   # POSIX, относительно корня
    abs_path: Path
    size: int
    mtime: int


def walk(root: Path) -> list[FileEntry]:
    """os.scandir рекурсивно: stat приходит вместе с именем, на HDD это в разы быстрее rglob.
    Скрытые папки и SKIP_DIRS пропускаются, симлинки не разыменовываются."""
    out: list[FileEntry] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            name = entry.name
                            if name.startswith(".") or name.lower() in SKIP_DIRS:
                                continue
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            if os.path.splitext(entry.name)[1].lower() not in SUPPORTED_FORMATS:
                                continue
                            st = entry.stat(follow_symlinks=False)
                            p = Path(entry.path)
                            out.append(FileEntry(
                                rel_path=p.relative_to(root).as_posix(),
                                abs_path=p,
                                size=st.st_size,
                                mtime=int(st.st_mtime),
                            ))
                    except OSError as e:
                        logger.warning("пропущен %s: %s", entry.path, e)
        except OSError as e:
            logger.warning("не открыть папку %s: %s", current, e)
    return out


def rel_dir(rel_path: str) -> str:
    """'Rock/Muse/x.flac' -> 'Rock/Muse'; 'x.flac' -> ''"""
    i = rel_path.rfind("/")
    return rel_path[:i] if i >= 0 else ""


# ---------------------------------------------------------------- теги и обложки

def _clean_str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _clean_float(v) -> float | None:
    try:
        f = float(v) if v is not None else None
        return f if f is not None and f > 0 else None
    except (TypeError, ValueError):
        return None


def read_row(path: Path) -> tuple[dict, bytes | None]:
    """read_tags -> (поля для tracks, байты обложки)."""
    raw = tagreader.read_tags(path)
    t = {TAG_KEYS.get(k, k): v for k, v in raw.items()}
    row = {
        "name": _clean_str(t.get("name")) or path.stem,
        "author": _clean_str(t.get("author")),
        "album": _clean_str(t.get("album")),
        "year": _clean_str(t.get("year")),
        "genre": _clean_str(t.get("genre")),
        "duration": _clean_float(t.get("duration")),
        "sample_rate": _clean_int(t.get("sample_rate")),
        "bitrate": _clean_int(t.get("bitrate")),
        "channels": _clean_int(t.get("channels")),
        "bits": _clean_int(t.get("bits")),
    }
    cover = t.get("cover")
    return row, (cover if isinstance(cover, (bytes, bytearray)) and cover else None)


def store_cover(cover: bytes, covers_dir: Path) -> tuple[str | None, bool]:
    """Кладёт <sha1>_full.jpg и <sha1>_50.jpg. Возвращает (hash, записано_ли_новое).
    Одинаковая обложка у 12 треков альбома пишется один раз."""
    h = hashlib.sha1(cover).hexdigest()
    full = covers_dir / f"{h}_full.jpg"
    mini = covers_dir / f"{h}_50.jpg"
    if full.exists() and mini.exists():
        return h, False
    try:
        with Image.open(io.BytesIO(cover)) as im:
            im.load()
            if im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")
            covers_dir.mkdir(parents=True, exist_ok=True)
            im.save(full, format="JPEG", quality=90)
            im.thumbnail((50, 50), Image.Resampling.LANCZOS)
            im.save(mini, format="JPEG", quality=85)
        return h, True
    except Exception as e:
        # битая картинка в тегах — не повод не индексировать трек
        logger.warning("обложка не сохранена (%s): %s", h[:8], e)
        for p in (full, mini):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        return None, False


# ---------------------------------------------------------------- скан

ROW_COLS = ("name", "author", "album", "year", "genre",
            "duration", "sample_rate", "bitrate", "channels", "bits")


def scan(cfg: Config, *, full: bool = False, progress=None) -> ScanReport:
    """Один проход по библиотеке. Потокобезопасен в пределах процесса.

    progress(report) вызывается после каждой пачки — для логов или UI.
    Бросает ScanInProgress, если другой скан уже идёт.
    """
    if not _scan_lock.acquire(blocking=False):
        raise ScanInProgress("скан уже выполняется в этом процессе")
    try:
        return _scan_locked(cfg, full=full, progress=progress)
    finally:
        _scan_lock.release()


def _scan_locked(cfg: Config, *, full: bool, progress) -> ScanReport:
    t0 = time.time()
    rep = ScanReport()
    db.init_db(cfg.db_path)

    with closing(db.get_conn(cfg.db_path)) as con:
        # --- блокировка между процессами (CLI и сервер могут работать одновременно)
        if db.meta_get(con, "scan_running") == "1":
            started = float(db.meta_get(con, "scan_started", "0") or 0)
            if time.time() - started < STALE_LOCK_SEC:
                raise ScanInProgress("скан уже выполняется (meta.scan_running = 1)")
            logger.warning("предыдущий скан не завершился, считаем упавшим")

        # Поколение обязано строго расти: два скана в одну секунду получили бы
        # одинаковый gen, и seen_gen < gen не нашёл бы пропавшие файлы
        last_gen = int(db.meta_get(con, "scan_gen", "0") or 0)
        gen = max(int(time.time()), last_gen + 1)
        rep.gen = gen
        with con:
            db.meta_set(con, "scan_running", 1)
            db.meta_set(con, "scan_started", int(time.time()))
            db.meta_set(con, "scan_gen", gen)
            db.meta_set(con, "scan_seen", 0)
            db.meta_set(con, "scan_parsed", 0)
            db.meta_set(con, "scan_total", 0)
            db.meta_set(con, "last_error", None)

        try:
            _scan_body(con, cfg, gen, full, rep, progress)
        except ScanAborted as e:
            logger.error("скан прерван: %s", e)
            rep.aborted = str(e)
            with con:
                db.meta_set(con, "last_error", rep.aborted)
        except Exception as e:
            logger.exception("скан упал")
            rep.aborted = f"{type(e).__name__}: {e}"
            with con:
                db.meta_set(con, "last_error", rep.aborted)
        finally:
            with con:
                db.meta_set(con, "scan_running", 0)
                db.meta_set(con, "scan_finished", int(time.time()))

    rep.seconds = time.time() - t0
    logger.info(rep.summary())
    return rep


def _scan_body(con: sqlite3.Connection, cfg: Config, gen: int, full: bool,
               rep: ScanReport, progress) -> None:
    root = cfg.root

    # --- 1. обход: только имена и stat, файлы не открываются
    if not root.is_dir():
        raise ScanAborted(f"корень библиотеки не существует: {root}")
    files = walk(root)
    rep.seen = len(files)
    existing = con.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    # --- защита от непримонтированного диска: пустой корень при непустой базе
    if not files and existing > 0:
        raise ScanAborted(
            f"в {root} нет ни одного аудиофайла, а в базе {existing} треков — "
            "похоже, диск не примонтирован. База не тронута.")

    with con:
        db.meta_set(con, "scan_total", len(files))

    max_id_before = con.execute("SELECT COALESCE(MAX(id), 0) FROM tracks").fetchone()[0]

    # --- 2. по файлам, коммит пачками
    batch = max(1, cfg.batch_size)
    in_batch = 0
    parsed = 0
    con.execute("BEGIN")
    try:
        for i, f in enumerate(files, 1):
            row = con.execute(
                "SELECT id, size, mtime, missing FROM tracks WHERE rel_path = ?",
                (f.rel_path,)).fetchone()

            if row is None:
                _insert(con, cfg, f, gen, rep)
                parsed += 1
            elif not full and row["size"] == f.size and row["mtime"] == f.mtime:
                con.execute("UPDATE tracks SET seen_gen = ?, missing = 0 WHERE id = ?",
                            (gen, row["id"]))
                rep.unchanged += 1
                if row["missing"]:
                    rep.restored += 1
            else:
                _update(con, cfg, f, gen, row["id"], rep)
                parsed += 1
                if row["missing"]:
                    rep.restored += 1

            in_batch += 1
            if in_batch >= batch:
                db.meta_set(con, "scan_seen", i)
                db.meta_set(con, "scan_parsed", parsed)
                con.execute("COMMIT")
                in_batch = 0
                if progress:
                    progress(rep)
                con.execute("BEGIN")

        db.meta_set(con, "scan_seen", len(files))
        db.meta_set(con, "scan_parsed", parsed)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    # --- 3. переименования и пропавшие
    with con:
        _resolve_gone(con, gen, max_id_before, rep)

    if progress:
        progress(rep)


def _insert(con, cfg: Config, f: FileEntry, gen: int, rep: ScanReport) -> None:
    row, cover = _read_or_stub(f, rep)
    cover_hash = _cover(cover, cfg, rep)
    con.execute(
        "INSERT INTO tracks (rel_path, dir, name, author, album, year, genre, duration, "
        "sample_rate, bitrate, channels, bits, size, mtime, cover_hash, seen_gen, missing) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
        (f.rel_path, rel_dir(f.rel_path), *[row[c] for c in ROW_COLS],
         f.size, f.mtime, cover_hash, gen))
    rep.added += 1


def _update(con, cfg: Config, f: FileEntry, gen: int, track_id: int, rep: ScanReport) -> None:
    row, cover = _read_or_stub(f, rep)
    cover_hash = _cover(cover, cfg, rep)
    con.execute(
        "UPDATE tracks SET dir=?, name=?, author=?, album=?, year=?, genre=?, duration=?, "
        "sample_rate=?, bitrate=?, channels=?, bits=?, size=?, mtime=?, cover_hash=?, "
        "seen_gen=?, missing=0 WHERE id=?",
        (rel_dir(f.rel_path), *[row[c] for c in ROW_COLS],
         f.size, f.mtime, cover_hash, gen, track_id))
    rep.updated += 1


def _read_or_stub(f: FileEntry, rep: ScanReport) -> tuple[dict, bytes | None]:
    try:
        return read_row(f.abs_path)
    except Exception as e:
        # read_tags обещает не бросать, но страховка дешёвая: трек попадёт в базу
        # с именем файла, а не потеряется вместе со всей пачкой
        rep.errors += 1
        rep.error_files.append(f.rel_path)
        logger.warning("теги не прочитаны %s: %s", f.rel_path, e)
        return {c: None for c in ROW_COLS} | {"name": f.abs_path.stem}, None


def _cover(cover: bytes | None, cfg: Config, rep: ScanReport) -> str | None:
    if not cover:
        return None
    h, written = store_cover(cover, cfg.covers_dir)
    if written:
        rep.covers_written += 1
    return h


def _resolve_gone(con: sqlite3.Connection, gen: int, max_id_before: int, rep: ScanReport) -> None:
    """Строки, которых не встретили в этом поколении: либо переименование, либо missing."""
    gone = con.execute(
        "SELECT id, size, mtime, missing FROM tracks WHERE seen_gen < ?", (gen,)).fetchall()
    if not gone:
        return

    # Кандидаты на «это тот же файл под новым именем»: новые строки этого скана
    new_rows = con.execute(
        "SELECT id, rel_path, dir, size, mtime FROM tracks WHERE id > ? AND seen_gen = ?",
        (max_id_before, gen)).fetchall()
    by_sig: dict[tuple[int, int], list] = defaultdict(list)
    for r in new_rows:
        by_sig[(r["size"], r["mtime"])].append(r)
    gone_sig = Counter((r["size"], r["mtime"]) for r in gone)

    for old in gone:
        sig = (old["size"], old["mtime"])
        candidates = by_sig.get(sig, [])
        # Однозначно только 1 ↔ 1. Иначе не гадаем: помечаем missing.
        if len(candidates) == 1 and gone_sig[sig] == 1:
            new = candidates[0]
            # UNIQUE(rel_path): сначала убрать новую строку, потом переставить старую
            con.execute("DELETE FROM tracks WHERE id = ?", (new["id"],))
            con.execute(
                "UPDATE tracks SET rel_path = ?, dir = ?, seen_gen = ?, missing = 0 WHERE id = ?",
                (new["rel_path"], new["dir"], gen, old["id"]))
            by_sig[sig] = []
            rep.renamed += 1
            rep.added -= 1          # это не новый трек, а старый под новым путём
            logger.info("переименование: id=%d -> %s", old["id"], new["rel_path"])
        elif not old["missing"]:
            con.execute("UPDATE tracks SET missing = 1 WHERE id = ?", (old["id"],))
            rep.missing += 1


# ---------------------------------------------------------------- обслуживание

def purge(cfg: Config) -> tuple[int, int]:
    """Удаляет строки с missing = 1 и обложки, на которые больше никто не ссылается.
    Возвращает (удалено строк, удалено файлов обложек)."""
    db.init_db(cfg.db_path)
    with closing(db.get_conn(cfg.db_path)) as con:
        with con:
            n_rows = con.execute("DELETE FROM tracks WHERE missing = 1").rowcount
            used = {r[0] for r in con.execute(
                "SELECT DISTINCT cover_hash FROM tracks WHERE cover_hash IS NOT NULL")}
    n_files = 0
    if cfg.covers_dir.is_dir():
        for p in cfg.covers_dir.iterdir():
            h = p.name.split("_", 1)[0]
            if p.is_file() and p.suffix == ".jpg" and h not in used:
                try:
                    p.unlink()
                    n_files += 1
                except OSError as e:
                    logger.warning("не удалить %s: %s", p, e)
    logger.info("purge: строк=%d, обложек=%d", n_rows, n_files)
    return n_rows, n_files


def stats(cfg: Config) -> dict:
    db.init_db(cfg.db_path)
    with closing(db.get_conn(cfg.db_path)) as con:
        total = con.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        missing = con.execute("SELECT COUNT(*) FROM tracks WHERE missing = 1").fetchone()[0]
        covers = con.execute(
            "SELECT COUNT(DISTINCT cover_hash) FROM tracks WHERE cover_hash IS NOT NULL").fetchone()[0]
        meta = db.meta_all(con)
    try:
        db_size = cfg.db_path.stat().st_size
    except OSError:
        db_size = 0
    return {
        "db": str(cfg.db_path),
        "root": str(cfg.root),
        "tracks": total - missing,
        "missing": missing,
        "covers": covers,
        "db_size_kb": db_size // 1024,
        **{k: v for k, v in meta.items()},
    }


def scan_status(con: sqlite3.Connection) -> dict:
    """То, что ping отдаёт плееру."""
    m = db.meta_all(con)
    running = m.get("scan_running") == "1"
    return {
        "library_uuid": m.get("library_uuid"),
        "tracks": db.track_count(con),
        "scan_running": running,
        "scan_progress": (f"{m.get('scan_seen', 0)}/{m.get('scan_total', 0)}" if running else None),
        "last_scan": int(m["scan_finished"]) if m.get("scan_finished") else None,
        "last_error": m.get("last_error"),
    }


# ---------------------------------------------------------------- CLI

def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Индексатор библиотеки")
    ap.add_argument("--full", action="store_true", help="перечитать теги у всех файлов")
    ap.add_argument("--purge", action="store_true", help="удалить строки missing = 1 и лишние обложки")
    ap.add_argument("--stats", action="store_true", help="показать состояние базы")
    ap.add_argument("--ini", type=Path, default=None, help="путь к server.ini")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # mutagen/PIL на DEBUG очень болтливы
    logging.getLogger("PIL").setLevel(logging.WARNING)

    cfg = load_config(args.ini) if args.ini else load_config()

    if args.stats:
        for k, v in stats(cfg).items():
            print(f"{k:>18}: {v}")
        return 0
    if args.purge:
        purge(cfg)
        return 0

    def show(rep: ScanReport):
        logger.info("… %d/%d, новых %d, обновлено %d", rep.added + rep.updated + rep.unchanged,
                    rep.seen, rep.added, rep.updated)

    try:
        rep = scan(cfg, full=args.full, progress=show)
    except ScanInProgress as e:
        logger.error("%s", e)
        return 2
    if rep.error_files:
        logger.warning("файлы с ошибками тегов (%d):", len(rep.error_files))
        for p in rep.error_files[:20]:
            logger.warning("  %s", p)
    return 1 if rep.aborted else 0


if __name__ == "__main__":
    sys.exit(_cli())
