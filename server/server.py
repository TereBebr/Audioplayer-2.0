from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import ClientDisconnect
import anyio
import hashlib
import hmac
import logging
import os
import shutil
import uuid
from pathlib import Path
from contextlib import closing
import threading
import db, indexer, uploads
from config import load_config
from importlib.metadata import version
app = FastAPI()

# fastapi dev server\server.py


cfg = load_config()
db.init_db(cfg.db_path)
# логгер uvicorn: его вывод попадает в journalctl, а корневой логгер тут не настроен
log = logging.getLogger("uvicorn.error")


def stream_sig(token: str, track_id) -> str:
    """Подпись ссылки на стрим одного трека: HMAC(token, "stream:<id>").

    VLC не умеет слать заголовок Authorization, поэтому для /server/stream/{id}
    в ссылку кладётся ?s=<подпись>, а не сам токен. Попади ссылка в лог — по ней
    можно скачать только этот трек, и токен из неё не восстановить.
    Две одинаковые копии: server/server.py и sources.py — менять обе."""
    return hmac.new(token.encode(), f"stream:{track_id}".encode(), hashlib.sha256).hexdigest()[:32]


def who_is(request: Request) -> str | None:
    """Имя из [Tokens], чей токен пришёл с запросом, или None.
    Заголовок Authorization: Bearer <token>; у стрима — ещё и ?s=<stream_sig> (так ходит VLC)."""
    # bytes, а не str: compare_digest падает на не-ASCII строках, а заголовок
    # может прислать кто угодно
    auth = request.headers.get("authorization", "").encode()
    path = request.url.path
    stream_id = path.rsplit("/", 1)[-1] if path.startswith("/server/stream/") else None
    sig = request.query_params.get("s", "").encode()
    for name, token in cfg.tokens.items():
        if hmac.compare_digest(auth, f"Bearer {token}".encode()):
            return name
        if stream_id is not None and hmac.compare_digest(sig, stream_sig(token, stream_id).encode()):
            return name
    return None


@app.middleware("http")
async def check_token(request: Request, call_next):
    """Токены из server.ini ([Tokens] и старый [Server] token). Нет ни одного —
    сервер открыт, как раньше. Есть — запрос без своего токена получает 401."""
    if cfg.tokens:
        who = who_is(request)
        if who is None:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        path = request.url.path
        # кто что слушает: только первый запрос трека, а не каждый кусок при перемотке
        if path.startswith("/server/stream/") and request.headers.get("range", "bytes=0-").startswith("bytes=0-"):
            log.info("%s слушает трек %s", who, path.rsplit("/", 1)[-1])
    return await call_next(request)

# из конфига ===========

BASE_DIR = Path(__file__).resolve().parent
# MUSIC_FOLDER_PATH = BASE_DIR / "music"

SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4"}
sorttype = 0
search_tracks_limit = 200
# ===========================================

def safe_path(rel: str) -> Path:
    root = cfg.root.resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(403, "path outside library")
    return target

def folder_content(folder_path):
    if checkout_folder(folder_path):
        root = cfg.root.resolve()
        folders = []
        tracks = []
        try:
            for obj in Path(folder_path).iterdir():
                if obj.is_dir():
                    folders.append({"name": obj.name, "path": obj.relative_to(root).as_posix(), "type": "folder"})
                elif obj.is_file() and obj.suffix.lower() in SUPPORTED_FORMATS:
                    tracks.append({"name": obj.name, "path": obj.relative_to(root).as_posix(), "type": "track"})
        except PermissionError:
            # Защита от системных папок, куда Windows не пускает
            pass
        #Виды сортировок // потом как-нибудь + на клиенте
        match sorttype:
            case 0: 
                folders.sort(key=lambda x: x["name"].lower())
                tracks.sort(key=lambda x: x["name"].lower())
            case 1:
                pass
    
        return folders + tracks
    return []

def checkout_folder(folder_path: str):
    if Path(folder_path).is_dir():
        return True
    return False

@app.get("/server/ping")
def ping():
    with closing(db.get_conn(cfg.db_path)) as con:
        tracks = db.track_count(con)
        return {
            "status": "OK", 
            "fastapi version": version("fastapi"), 
            "server version": "0.2",
            "tracks": tracks, **indexer.scan_status(con),
            **_disk_usage(),
        }
    raise HTTPException(404)

@app.get("/server/browse")
def get_folder_content(folder_path: str):
    folder = safe_path(folder_path)
    if not folder.is_dir():
        raise HTTPException(404, "folder not found")
    folders = [item for item in folder_content(folder) if item["type"] == "folder"]
    with closing(db.get_conn(cfg.db_path)) as con:
        tracks = [dict(r) | {"type": "track"} for r in db.tracks_in_dir(con, folder_path)]
    return folders + tracks

@app.get("/server/tracks_under")
def tracks_under(folder_path: str = ""):
    """Треки папки и всех подпапок — для «добавить папку в очередь» на клиенте."""
    folder = safe_path(folder_path)
    if not folder.is_dir():
        raise HTTPException(404, "folder not found")
    with closing(db.get_conn(cfg.db_path)) as con:
        return [dict(r) for r in db.tracks_under_dir(con, folder_path)]

@app.get("/server/search")
def all_library_search(q: str, folder_path: str=""):
    if folder_path and not safe_path(folder_path).is_dir():   # safe_path сам даст 403 на ../
        raise HTTPException(404, "folder not found")
    with closing(db.get_conn(cfg.db_path)) as con:
        content = db.search_tracks(con, q, search_tracks_limit, folder_path)
    return content

@app.get("/server/track/{track_id}")
def track(track_id: int):
    with closing(db.get_conn(cfg.db_path)) as con:
        row = db.get_track(con, track_id)
    if row is None:
        raise HTTPException(404)
    if row["missing"]:
        raise HTTPException(410, "file is gone from disk")
    return dict(row)

@app.get("/server/track/{track_id}/cover")
def cover(track_id: int, size: str):
    if size in ("50", "full"):
        with closing(db.get_conn(cfg.db_path)) as con:
            hash = db.get_cover(con, track_id)
        file_path = cfg.covers_dir / f"{hash}_{size}.jpg"
        if not file_path.is_file():
            raise HTTPException(404, "Cover file missing on disk")
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(400, "Invalid cover size")

@app.get("/server/tracks")
def get_data(ids):
    try:
        id_list = [int(x) for x in ids.split(",") if x][:500]
    except ValueError:
        raise HTTPException(400, "ids must be integers")
    with closing(db.get_conn(cfg.db_path)) as con:
        content = db.get_tracks(con, id_list)
    if content is None:
        raise HTTPException(404)
    return [dict(r) for r in content]
    
@app.get("/server/stream/{track_id}")
def stream(track_id: int):
    with closing(db.get_conn(cfg.db_path)) as con:
        row = db.get_track(con, track_id)
    if row is None: raise HTTPException(404)
    if row["missing"]: raise HTTPException(410)
    return FileResponse(safe_path(row["rel_path"]))

@app.post("/server/rescan")
def rescan(full: bool = False):
    with closing(db.get_conn(cfg.db_path)) as con:
        if indexer.scan_status(con)["scan_running"]:
            raise HTTPException(409, "scan already running")
    threading.Thread(target=indexer.scan, args=(cfg,), kwargs={"full": full}, daemon=True).start()
    return {"started": True}

@app.get("/server/tracks_under")
def tracks_under(folder_path: str = ""):
    safe_path(folder_path)                       # проверка обхода каталога
    with closing(db.get_conn(cfg.db_path)) as con:
        return [dict(r) for r in db.tracks_under_dir(con, folder_path)]

# ================================================================ файлы библиотеки
# Экран «Отладочный режим» плеера: docs/TZ_server_panel.md §2, §4.
# Загружать и скачивать может любой с токеном, откатить — свою загрузку,
# удалять — только [Server] admins. Перезаписать существующий файл нельзя никому.

journal = uploads.Journal(cfg.db_path.parent / "uploads.db")
scan_later = uploads.ScanScheduler(lambda: indexer.scan(cfg), indexer.ScanInProgress)
# недокачанные *.part после выключения посреди загрузки; обход диска — в фоне
threading.Thread(target=uploads.clean_parts, args=(cfg.root,), daemon=True).start()

DISK_RESERVE = 200 * 1024 * 1024   # столько остаётся свободным после любой загрузки
FLUSH_BYTES = 1 << 20              # копить столько, потом одна запись в потоке
_commit_lock = threading.Lock()    # проверка «уже есть» + переименование — атомарно


def _disk_usage() -> dict:
    try:
        du = shutil.disk_usage(cfg.root)
    except OSError:                # диск отвалился — ping всё равно отвечает
        return {"disk_free": None, "disk_total": None}
    return {"disk_free": du.free, "disk_total": du.total}


def user(request: Request) -> tuple[str, bool]:
    """(имя, администратор ли). Сервер без токенов: ('', False) у всех."""
    if not cfg.tokens:
        return "", False
    who = who_is(request) or ""
    return who, who in cfg.admins


def _own_op(op_id: str, who: str, admin: bool = False):
    row = journal.get_op(op_id)
    if row is None:
        raise HTTPException(404, "unknown op")
    if row["who"] != who and not admin:
        raise HTTPException(403, "not your op")
    return row


@app.get("/server/me")
def me(request: Request):
    who, admin = user(request)
    return {"name": who or None, "admin": admin}


@app.get("/server/files")
def files_under(path: str = ""):
    """Все аудио и картинки под папкой, рекурсивно (вместе с covers/) — для скачивания."""
    folder = safe_path(path)
    if not folder.is_dir():
        raise HTTPException(404, "folder not found")
    return uploads.list_files(cfg.root, folder)


@app.get("/server/ls")
def ls_dir(path: str = ""):
    """Одна папка с диска, как есть: подпапки и разрешённые файлы с размерами.
    /server/browse берёт треки из индекса — там нет картинок, covers/ и размеров."""
    folder = safe_path(path)
    if not folder.is_dir():
        raise HTTPException(404, "folder not found")
    return uploads.list_dir(cfg.root, folder)


@app.get("/server/file")
def get_file(path: str):
    p = safe_path(path)
    if not p.is_file() or uploads.file_kind(p.name) is None:
        raise HTTPException(404, "file not found")
    return FileResponse(p)


@app.post("/server/ops")
def start_op(request: Request, folder: str = ""):
    who, _ = user(request)
    return {"op_id": journal.new_op(who, folder)}


@app.get("/server/ops")
def list_ops(request: Request, mine: bool = True):
    """Свои операции загрузки; администратор с mine=0 видит все."""
    who, admin = user(request)
    return journal.list_ops(None if admin and not mine else who)


@app.get("/server/ops/{op_id}")
def op_files(request: Request, op_id: str):
    who, admin = user(request)
    _own_op(op_id, who, admin)
    return [{"rel_path": f["rel_path"], "size": f["size"], "removed": bool(f["removed"])}
            for f in journal.files(op_id)]


def _commit(part: Path, parts: list[str], root: Path) -> Path:
    with _commit_lock:
        # второй раз: пока файл шёл, тот же путь мог загрузить кто-то ещё,
        # а os.rename в Linux молча перезаписывает
        target = uploads.resolve_ci(root, parts)
        if target.exists():
            raise HTTPException(409, "already exists")
        os.rename(part, target)
        return target


@app.put("/server/file")
async def put_file(request: Request, path: str, op: str):
    who, _ = user(request)
    row = await anyio.to_thread.run_sync(journal.get_op, op)
    if row is None:
        raise HTTPException(404, "unknown op")
    if row["who"] != who:
        raise HTTPException(403, "not your op")
    if row["undone"]:
        raise HTTPException(410, "op is undone")
    try:
        parts = uploads.check_upload_path(path)
    except uploads.RuleError as e:
        raise HTTPException(400, str(e))
    root = cfg.root.resolve()
    if not root.is_dir():
        raise HTTPException(503, "library root unavailable")

    target = await anyio.to_thread.run_sync(uploads.resolve_ci, root, parts)
    safe_path(target.relative_to(root).as_posix())
    if target.exists():
        raise HTTPException(409, "already exists")
    length = request.headers.get("content-length", "")
    if not length.isdigit():
        raise HTTPException(411, "Content-Length required")
    length = int(length)
    if shutil.disk_usage(root).free < length + DISK_RESERVE:
        raise HTTPException(507, "not enough disk space")

    await anyio.to_thread.run_sync(lambda: target.parent.mkdir(parents=True, exist_ok=True))
    part = target.with_name(f"{target.name}.{uuid.uuid4().hex[:8]}{uploads.PART_SUFFIX}")
    f = await anyio.to_thread.run_sync(open, part, "xb")
    done = False
    try:
        buf = bytearray()
        received = 0
        try:
            async for chunk in request.stream():
                received += len(chunk)
                if received > length:
                    raise HTTPException(400, "body longer than Content-Length")
                buf += chunk
                if len(buf) >= FLUSH_BYTES:
                    data = bytes(buf)
                    buf.clear()
                    # запись — в потоке: event loop в это время отдаёт музыку другим
                    await anyio.to_thread.run_sync(f.write, data)
        except ClientDisconnect:
            log.info("%s оборвал загрузку %s", who or "?", path)
            raise HTTPException(400, "client disconnected")
        if buf:
            await anyio.to_thread.run_sync(f.write, bytes(buf))
        await anyio.to_thread.run_sync(f.close)
        if received != length:
            raise HTTPException(400, "incomplete upload")
        target = await anyio.to_thread.run_sync(_commit, part, parts, root)
        done = True
    finally:
        if not done:
            # синхронно: при отмене задачи await здесь уже не выполнится
            f.close()
            part.unlink(missing_ok=True)
            uploads.remove_empty_dirs(root, part.parent)

    st = target.stat()
    rel = target.relative_to(root).as_posix()
    await anyio.to_thread.run_sync(journal.add_file, op, rel, st.st_size, st.st_mtime_ns)
    scan_later.schedule()
    log.info("%s загрузил %s", who or "?", rel)
    return {"path": rel, "size": st.st_size}


@app.post("/server/ops/{op_id}/undo")
def undo_op(request: Request, op_id: str):
    """Удаляет файлы операции — только те, что с загрузки не меняли (size и mtime)."""
    who, admin = user(request)
    _own_op(op_id, who, admin)
    root = cfg.root.resolve()
    removed, skipped, gone_rows, parents = [], [], [], set()
    for f in journal.files(op_id, only_present=True):
        rel = f["rel_path"]
        try:
            p = safe_path(rel)
            st = p.stat()
        except FileNotFoundError:
            skipped.append({"path": rel, "reason": "файла уже нет"})
            gone_rows.append(f["rowid"])
            continue
        except (OSError, HTTPException) as e:
            skipped.append({"path": rel, "reason": f"ошибка: {e}"})
            continue
        if st.st_size != f["size"] or st.st_mtime_ns != f["mtime_ns"]:
            skipped.append({"path": rel, "reason": "файл изменён после загрузки"})
            continue
        try:
            p.unlink()
        except OSError as e:
            skipped.append({"path": rel, "reason": f"ошибка: {e}"})
            continue
        removed.append(rel)
        gone_rows.append(f["rowid"])
        parents.add(p.parent)
    journal.mark_removed(gone_rows)
    journal.mark_undone(op_id)
    dirs = []
    for d in sorted(parents, key=lambda x: len(x.parts), reverse=True):
        dirs += uploads.remove_empty_dirs(root, d)
    if removed:
        scan_later.schedule(1)
    log.info("%s откатил загрузку %s: удалено %d, пропущено %d",
             who or "?", op_id, len(removed), len(skipped))
    return {"removed": removed, "skipped": skipped, "dirs_removed": dirs}


@app.delete("/server/file")
def delete_path(request: Request, path: str):
    """Удалить файл или папку целиком. Только администраторы."""
    who, admin = user(request)
    if not admin:
        raise HTTPException(403, "admins only")
    root = cfg.root.resolve()
    p = safe_path(path)
    if p == root:
        raise HTTPException(400, "cannot delete library root")
    if not p.exists():
        raise HTTPException(404, "not found")
    rel = p.relative_to(root).as_posix()
    if p.is_dir() and not p.is_symlink():
        n = sum(len(fs) for _d, _ds, fs in os.walk(p))
        shutil.rmtree(p)
    else:
        n = 1
        p.unlink()
    dirs = uploads.remove_empty_dirs(root, p.parent)
    scan_later.schedule(1)
    log.warning("%s удалил %s (файлов: %d)", who, rel, n)
    return {"deleted": rel, "files": n, "dirs_removed": dirs}
