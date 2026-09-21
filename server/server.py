from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import closing
import threading
import db, indexer
from config import load_config
from importlib.metadata import version
app = FastAPI()

'''
fastapi dev desktop\server\server.py

эндпоинты: 3/8

'''

cfg = load_config()
db.init_db(cfg.db_path)

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
            "server version": "0.1", 
            "tracks": tracks, **indexer.scan_status(con)
        }
    raise HTTPException(404)

@app.get("/server/browse") # C:\Users\Dmitry\Desktop\server\music
def get_folder_content(folder_path: str):
    folder = safe_path(folder_path)
    if not folder.is_dir():
        raise HTTPException(404, "folder not found")
    folders = [item for item in folder_content(folder) if item["type"] == "folder"]
    with closing(db.get_conn(cfg.db_path)) as con:
        tracks = [dict(r) | {"type": "track"} for r in db.tracks_in_dir(con, folder_path)]
    return folders + tracks

@app.get("/server/search")
def all_library_search(filename: str):
    with closing(db.get_conn(cfg.db_path)) as con:
        content = db.search_tracks(con, filename, search_tracks_limit)
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