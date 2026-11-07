from pathlib import Path
import os
import mutagen
from mutagen.id3 import APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from PIL import Image
import io
import utils
from tinytag import TinyTag
import requests
import search_rank
import hashlib
import hmac
from requests.exceptions import RequestException
import time
import threading
import logging

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.mp4'}
COVER_NAMES = ["Прости меня моя любовь (фронт).jpg", "cover.jpg", "cover.png", "1.jpg", "1.png", "folder.jpg", "folder.png", "front.jpg", "front.png", "img001.jpg", "img001.png", "img01.jpg", "img01.png", "img1.jpg", "img1.png", "img.jpg", "img.png", "image.jpg", "image.png"]
COVER_DIR_NAMES = ["covers", "cover", "scans", "artwork"]

import configparser
config = configparser.ConfigParser()
config.read('config.txt', encoding='utf-8')
idxDirrs = config.getboolean('Main Settings', 'idxDirrs')

SRV_ENABLED = config.getboolean('Server', 'enabled', fallback=False)
SRV_ID = config.get('Server', 'server_id', fallback='home')
SRV_BASE_URL = config.get('Server', 'base_url', fallback='').rstrip('/')
SRV_TOKEN = config.get('Server', 'token', fallback='').strip()
SRV_TIMEOUT = config.getfloat('Server', 'timeout', fallback=5.0)
SRV_CACHING = config.getint('Server', 'network_caching', fallback=5000)

class LocalSource:
    is_remote = False

    def crumbs(self, uri):
        """[(подпись, URI), ...] для хлебных крошек.
        Путь C:/music/Rock даёт [("C:", "C:/"), ("music", "C:/music"), ("Rock", "C:/music/Rock")]"""
        normalized = str(uri).replace("\\", "/")
        segments = [s for s in normalized.split("/") if s]
        is_windows = ":" in normalized

        out = []
        for i, segment in enumerate(segments):
            if is_windows:
                sub = segments[0] + "/" + "/".join(segments[1:i + 1])
            else:
                sub = "/" + "/".join(segments[:i + 1])
            out.append((segment, str(Path(sub))))
        return out

    def list_dir(self, folder_path: str):#анализ текущей папки (выбранной)
        # Всегда абсолютный путь: иначе от start_path = ./music в БД попадали относительные
        # 'music\used\a.mp3', а через крошки тот же файл — абсолютный. Два URI на файл
        # ломали проверку дублей в плейлистах, а у .exe (другая рабочая папка) — и поиск файла
        path = Path(os.path.abspath(folder_path))
        if not path.exists() or not path.is_dir():
            return []
        folders = []
        tracks = []

        try:
            for obj in path.iterdir(): #iterdir работает очень быстро для одной директории
                if obj.is_dir():
                    folders.append({"name": obj.name, "path": str(obj), "type": "folder"})
                elif obj.is_file() and obj.suffix.lower() in SUPPORTED_FORMATS:
                    tracks.append({"name": obj.name, "path": str(obj), "type": "track"})
        except PermissionError:
            # Защита от системных папок, куда Windows не пускает
            pass
        # Возможный методы сортировок
        folders.sort(key=lambda x: x["name"].lower())
        tracks.sort(key=lambda x: x["name"].lower())
        return folders + tracks

    def get_local_cover_path(self, file_path):
            """Ищет обложку в папке с аудиофайлом и в подпапках (Scans, Covers и т.д.)"""
            try:
                folder_path = Path(file_path).resolve().parent
            except Exception:
                return None
            # Ищем в самой папке с аудиофайлом
            try:
                for item in folder_path.iterdir():
                    if item.is_file() and item.name.lower() in COVER_NAMES:
                        return item
            except Exception:
                return None
            # Ищем в подпапках (например, "Covers" или "Scans")
            try:
                for item in folder_path.iterdir():
                    if item.is_dir() and item.name.lower() in COVER_DIR_NAMES:
                        for sub_item in item.iterdir():
                            if sub_item.is_file() and sub_item.name.lower() in COVER_NAMES:
                                return sub_item
            except Exception:
                pass
            return None

    def cover(self, uri, size):
        """
        Извлекает обложку из аудиофайла или папки.
        size: "full" (оригинал) или "50" (миниатюра 50x50)
        """
        raw_data = None

        try:
            try:
                audio = mutagen.File(uri)
            except Exception:
                audio = utils.detect_and_load_audio(uri)

            if audio:
                # Поиск в ID3 (MP3) и других форматах с атрибутом .tags
                if hasattr(audio, 'tags') and audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC) or (hasattr(tag, 'type') and 'pic' in str(tag).lower()):
                            raw_data = tag.data
                            break
                
                # Поиск в FLAC, OGG, некоторых MP4
                if not raw_data and hasattr(audio, 'pictures') and audio.pictures:
                    raw_data = audio.pictures[0].data
        except Exception as e:
            pass

        local_cover_path = None
        if not raw_data:
            local_cover_path = self.get_local_cover_path(uri)

        # Если обложка вообще не найдена
        if not raw_data and not local_cover_path:
            return None

        if size == "full" and raw_data:
            return raw_data

        try:
            # Открываем изображение либо из памяти (теги), либо с диска (папка)
            if raw_data:
                image = Image.open(io.BytesIO(raw_data))
            else:
                image = Image.open(local_cover_path)

            # Безопасная конвертация для JPEG
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            if size == "50":
                image.thumbnail((50, 50), Image.Resampling.LANCZOS)
                quality = 85
            else:
                quality = 90

            output_buffer = io.BytesIO()
            image.save(output_buffer, format="JPEG", quality=quality)
            return output_buffer.getvalue()

        except Exception as e:
            # Fallback 1: отдаем оригинальные байты из тега
            if raw_data:
                return raw_data
            # Fallback 2: отдаем сырые байты файла, если Pillow не смог его открыть
            if local_cover_path:
                try:
                    return local_cover_path.read_bytes()
                except Exception:
                    pass
        return None

    def mrl(self, uri):
        return str(Path(uri).resolve())

    def is_dir(self, uri):
        return Path(uri).is_dir()

    def expand(self, uri):
        path = Path(os.path.abspath(uri))   # см. list_dir: только абсолютные URI
        files = []
        pattern = path.rglob('*') if idxDirrs else path.iterdir()

        for obj in pattern:
            if obj.is_file() and obj.suffix.lower() in SUPPORTED_FORMATS:
                files.append(obj)
        return [str(p) for p in files]

    def display_path(self, uri):
        """Строка для адресной строки / хлебных крошек."""
        return str(Path(uri).resolve())

    def parent(self, uri):
        """URI родительской папки."""
        return str(Path(uri).resolve().parent)

    def exists(self, uri):
        return Path(uri).exists()

    def reveal(self, uri):
        """Открыть папку с файлом в системном проводнике. У RemoteSource — no-op."""
        p = Path(uri).resolve()
        os.startfile(p if p.is_dir() else p.parent)

    def tt_lite_parse(self, uri):
        try:
            tag = TinyTag.get(uri)
        except Exception:
            tag = None

        def safe_get(attr):
            return getattr(tag, attr, None) if tag else None
        duration = safe_get('duration')

        return {
            "Название": safe_get('title') or uri.stem,
            "Автор": safe_get('artist') or uri.parent.parent.stem,
            "Альбом": safe_get('album') or uri.parent.stem,
            "Год": str(safe_get('year')) if safe_get('year') else None,
            "Жанр": safe_get('genre'),
            "Длительность": float(f"{duration:.2f}") if duration and duration > 0 else None,
        }

    def meta(self, uri):
        uri = Path(uri)
        try:
            audio = mutagen.File(uri)
        except Exception:
            audio = utils.detect_and_load_audio(uri)
        
        if audio is None or audio.tags is None:
            return self.tt_lite_parse(uri)
    
        if isinstance(audio, MP3):
            # В MP3 текст хранится внутри объекта фрейма, нужно доставать через .text[0]
            def get_id3(key, default):
                frame = audio.get(key)
                if frame and hasattr(frame, 'text') and frame.text:
                    return str(frame.text[0])
                return default
    
            tags = {
                "Название": get_id3('TIT2', uri.stem),
                "Автор": get_id3('TPE1', (uri.parent.parent).stem),
                "Альбом": get_id3('TALB', (uri.parent).stem),
                "Год": get_id3('TDRC', get_id3('TYER', None)),
                "Жанр": get_id3('TCON', None),
            }
    
        elif isinstance(audio, FLAC) or isinstance(audio, OggVorbis):
            def get_vorbis(key, default):
                val = audio.get(key)
                return str(val[0]) if val else default
    
            tags = {
                "Название": get_vorbis('title', uri.stem),
                "Автор": get_vorbis('artist', (uri.parent.parent).stem),
                "Альбом": get_vorbis('album', (uri.parent).stem),
                "Год": get_vorbis('date', None),
                "Жанр": get_vorbis('genre', None),
            }
    
        elif isinstance(audio, MP4):
            def get_mp4(key, default):
                val = audio.get(key)
                return str(val[0]) if val else default
    
            tags = {
                "Название": get_mp4('\xa9nam', uri.stem),
                "Автор": get_mp4('\xa9ART', (uri.parent.parent).stem),
                "Альбом": get_mp4('\xa9alb', (uri.parent).stem),
                "Год": get_mp4('\xa9day', None),
                "Жанр": get_mp4('\xa9gen', None),
            }
        else: tags = self.tt_lite_parse(uri)
        return tags

    def duration(self, uri):
        """Длительность в секундах или None. Для локального файла VLC знает длину сразу,
        поэтому подсказка не нужна."""
        return None

    def details(self, uri):
        uri = Path(uri)
        try:
            audio = mutagen.File(uri)
        except Exception:
            audio = utils.detect_and_load_audio(uri)
        data = audio.info

        if isinstance(audio, MP3):   
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Битрейт": f"{data.bitrate // 1000} kbps",
                "Каналы": f"{data.channels}",
            }
        elif isinstance(audio, FLAC) or isinstance(audio, OggVorbis):
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Битрейт": f"{getattr(data, 'bitrate', 0) // 1000} kbps",
                "Глубина бит": getattr(data, 'bits_per_sample', '-'),
                "Каналы": f"{data.channels}",
            }
        elif isinstance(audio, MP4):
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Каналы": f"{data.channels}",
            }
            bitrate = getattr(data, 'bitrate', None)
            if bitrate:
                details["Битрейт"] = f"{bitrate // 1000} kbps"
            
            # У MP4 иногда доступна глубина бита и кодек
            bits = getattr(data, 'bits_per_sample', None)
            if bits:
                details["Глубина бит"] = bits
        else:
            details = {
                "Длительность": f"{getattr(data, 'length', 0):.2f} сек",
                "Частота": f"{getattr(data, 'sample_rate', '-')} Гц",
                "Каналы": f"{getattr(data, 'channels', '-')}",
            }
            bitrate = getattr(data, 'bitrate', None)
            if bitrate:
                details["Битрейт"] = f"{bitrate // 1000} kbps"
            bits = getattr(data, 'bits_per_sample', None)
            if bits:
                details["Глубина бит"] = bits
        return details

    WALK_TTL = 60.0       # сколько секунд держать список файлов библиотеки
    SEARCH_LIMIT = 200    # как на сервере
    _walk_cache = {}      # root -> (время, [(имя файла, полный путь, путь от root для поиска)])

    def _walk(self, root):
        """Все треки под root, с подпапками. Поиск идёт на каждую паузу в наборе,
        а обход диска медленный — поэтому список кэшируется на WALK_TTL."""
        hit = self._walk_cache.get(root)
        if hit and time.time() - hit[0] < self.WALK_TTL:
            return hit[1]
        files = []
        for dirpath, _, filenames in os.walk(root):   # папки без доступа os.walk пропускает сам
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in SUPPORTED_FORMATS:
                    full = os.path.join(dirpath, fn)
                    files.append((fn, full, _fold(os.path.relpath(full, root))))
        self._walk_cache[root] = (time.time(), files)
        return files

    def search(self, query: str, folder_uri: str | None = None, items: list | None = None) -> list | None:
        """items задан — фильтр по уже открытой папке, без диска.
        Иначе — обход folder_uri со всеми подпапками (поиск по библиотеке), только треки;
        совпадение ищется в пути от folder_uri, т.е. и по имени файла, и по папкам."""
        q = _fold(query.strip())
        if items is not None:
            found = [{"name": item["name"], "path": item["path"], "type": item["type"]} for item in items if q in _fold(item["name"])]
            # тот же порядок, что на сервере (search_rank.py); sorted устойчивый, поэтому
            # внутри ранга остаётся порядок list_dir: папки, потом файлы, по алфавиту
            return sorted(found, key=lambda item: search_rank.rank(query, item["name"]))
        if not q or not folder_uri:
            return []
        found = [{"name": name, "path": full, "type": "track"}
                 for name, full, rel in self._walk(folder_uri) if q in rel]
        found.sort(key=lambda item: (search_rank.rank(query, item["name"]), item["path"].casefold()))
        return found[:self.SEARCH_LIMIT]

def stream_sig(token: str, track_id) -> str:
    """Подпись ссылки на стрим одного трека: HMAC(token, "stream:<id>").

    VLC не умеет слать заголовок Authorization, поэтому для /server/stream/{id}
    в ссылку кладётся ?s=<подпись>, а не сам токен. Попади ссылка в лог — по ней
    можно скачать только этот трек, и токен из неё не восстановить.
    Две одинаковые копии: server/server.py и sources.py — менять обе."""
    return hmac.new(token.encode(), f"stream:{track_id}".encode(), hashlib.sha256).hexdigest()[:32]

# Чтение при передаче файла: 5 секунд SRV_TIMEOUT мало — сервер пишет на HDD
# и может не отвечать, пока сбрасывает буфер большого FLAC
TRANSFER_READ_TIMEOUT = 60


def _detail(r) -> str:
    """Текст ошибки FastAPI ({"detail": ...}) или пусто."""
    try:
        d = r.json().get("detail")
    except (ValueError, AttributeError):
        return ""
    return d if isinstance(d, str) else ""


class RemoteUnavailable(Exception):
    """Сервер недоступен или произошла сетевая ошибка."""
    pass

class RemoteNotFound(Exception):
    """404/410 — трека нет или файл пропал с диска."""

class RemoteSource:
    is_remote = True
    def __init__(self):
        self.session = requests.Session()
        self._cache = {}# track_id -> (когда_положили, данные)
        self._ttl = 60

    def ping(self, timeout=2.0):
        """Состояние сервера или None, если не ответил.
        Свой короткий таймаут: проверка доступности не должна ждать столько же,
        сколько обычный запрос."""
        saved, globals()["SRV_TIMEOUT"] = SRV_TIMEOUT, timeout
        try:
            return self._get("/server/ping", probe=True).json()
        except (RemoteUnavailable, RemoteNotFound, ValueError) as e:
            logger.info(f"ping: сервер не ответил: {e}")
            return None
        finally:
            globals()["SRV_TIMEOUT"] = saved

    def crumbs(self, uri):
        """[(подпись, URI), ...]. Первый сегмент — всегда корень сервера."""
        try:
            kind, rel = self._parse(uri)
        except RemoteNotFound:
            return [("Сервер", self._dir_uri(""))]
        if kind == 't':
            uri = self.parent(uri)
            kind, rel = self._parse(uri)

        out = [("Сервер", self._dir_uri(""))]
        acc = []
        for segment in [x for x in rel.split("/") if x]:
            acc.append(segment)
            out.append((segment, self._dir_uri("/".join(acc))))
        return out

    # ---- кэш строк треков ----
    # rebuild_queue_ui спрашивает название/автора для каждой видимой строки при
    # каждой прокрутке. Без кэша это HTTP-запрос на строку.

    def _prime(self, rows):
        """Положить в кэш строки, которые и так пришли в ответе list_dir/expand.
        После этого добавление альбома в очередь — один запрос вместо 50."""
        now = time.time()
        for row in rows:
            if "id" in row:
                self._cache[str(row["id"])] = (now, row)

    def _track_row(self, track_id):
        """Строка трека с сервера. Повторный вызов в пределах минуты сети не трогает."""
        track_id = str(track_id)
        hit = self._cache.get(track_id)
        if hit and time.time() - hit[0] < self._ttl:
            return hit[1]

        row = self._get(f"/server/track/{track_id}").json()
        if len(self._cache) > 2000:
            self._cache.clear()
        self._cache[track_id] = (time.time(), row)
        return row

    # ---- разбор URI ----

    def _parse(self, uri):
        """'srv://home/t/48213' -> ('t', '48213');  'srv://home/d/Rock/Muse' -> ('d', 'Rock/Muse')
        Корень сервера: 'srv://home/d' или 'srv://home/d/' -> ('d', '')"""

        if ((uri.removeprefix(f"srv://")).split('/',1))[0] != SRV_ID:
            raise RemoteNotFound("server_id отличается")

        row = uri.removeprefix(f"srv://{SRV_ID}").lstrip('/')

        if '/' in row:
            parts = row.split('/', 1)
            return (parts[0], parts[1] or '')
        else: return (row, '')

    def _track_uri(self, track_id) -> str:
        return f"srv://{SRV_ID}/t/{track_id}"

    def _dir_uri(self, rel_path) -> str:
        rel_path = rel_path.strip('/')
        if rel_path:
            return f"srv://{SRV_ID}/d/{rel_path}"
        return f"srv://{SRV_ID}/d"

    def _get(self, path, params=None, stream=False, probe=False):
        return self._request("GET", path, params=params, stream=stream, probe=probe)

    def _request(self, method, path, params=None, stream=False, probe=False,
                 headers=None, allow=(), data=None, timeout=None):
        """Единственная точка выхода в сеть. allow — коды ответа, которые вызывающий
        разбирает сам (например, 409 у rescan), вместо исключения.
        timeout — свой для передачи файлов: (подключение, чтение)."""
        url = f"{SRV_BASE_URL}{path}"
        if not SRV_ENABLED:
            # единственная точка выхода в сеть: при enabled = False не уходит ни один запрос
            raise RemoteUnavailable("сервер выключен в config.txt")
        if not probe and not _srv_state["online"]:
            # фоновый опрос уже знает, что сервера нет: не ждём таймаут на каждом запросе.
            # Сам опрос (ping) идёт с probe=True — иначе он не узнал бы, что сервер вернулся
            raise RemoteUnavailable("сервер недоступен (по последнему опросу)")
        headers = dict(headers or {})
        if SRV_TOKEN:
            headers["Authorization"] = f"Bearer {SRV_TOKEN}"
        try:
            r = self.session.request(method, url, params=params, headers=headers, data=data,
                                     stream=stream, timeout=timeout or SRV_TIMEOUT)
        except RequestException as err:
            if not probe:
                _wake.set()   # пусть опрос проверит сервер прямо сейчас
            raise RemoteUnavailable(f"Сервер недоступен [{url}]: {err}") from err
        if r.status_code in allow:
            return r
        if r.status_code == 403:
            raise RemoteUnavailable(f"{url} -> 403: {_detail(r) or 'нет прав'}")
        if r.status_code == 401:
            # отдельное сообщение: иначе неверный токен выглядит как «сервер недоступен»
            raise RemoteUnavailable(f"{url} -> 401: токен в config.txt не совпадает с server.ini")
        if r.status_code in (404, 410):
            raise RemoteNotFound(f"{url} -> {r.status_code}")
        if not r.ok:
            raise RemoteUnavailable(f"{url} -> {r.status_code}")
        return r

    # ---- методы источника, которым нужна сеть ----
    # Наружу исключения не выпускаем: вызывающий код (add_queue, rebuild_explorer,
    # load_track) писался под локальный источник и падения не переживёт.

    def list_dir(self, uri):
        try:
            _, rel = self._parse(uri)
            rows = self._get("/server/browse", params={"folder_path": rel}).json()
        except (RemoteUnavailable, RemoteNotFound) as e:
            logger.error(f"list_dir {uri}: {e}")
            return []
        self._prime(rows)
        return [
            {
                "name": row["name"],
                "path": self._dir_uri(row["path"]) if row["type"] == "folder"
                        else self._track_uri(row["id"]),
                "type": row["type"],
            }
            for row in rows
        ]

    def expand(self, uri):
        """URI папки -> плоский список URI треков, включая подпапки."""
        try:
            _, rel = self._parse(uri)
            rows = self._get("/server/tracks_under", params={"folder_path": rel}).json()
        except (RemoteUnavailable, RemoteNotFound) as e:
            logger.error(f"expand {uri}: {e}")
            return []
        self._prime(rows)
        return [self._track_uri(row["id"]) for row in rows]

    def meta(self, uri):
        """Ключи те же, что у LocalSource.meta."""
        track_id = "?"
        try:
            _, track_id = self._parse(uri)
            row = self._track_row(track_id)
        except RemoteNotFound as e:
            logger.error(f"meta {uri}: {e}")
            # _stub = True говорит вызывающему: это не настоящие теги, в БД не писать
            return {"Название": f"Трек {track_id} (нет на сервере)", "Автор": "Неизвестно",
                    "Альбом": None, "Год": None, "Жанр": None, "_stub": True}
        except RemoteUnavailable as e:
            logger.error(f"meta {uri}: {e}")
            return {"Название": f"Трек {track_id} (сервер недоступен)", "Автор": "Неизвестно",
                    "Альбом": None, "Год": None, "Жанр": None, "_stub": True}
        return {
            "Название": row.get("name") or f"Трек {track_id}",
            "Автор":    row.get("author") or "Неизвестно",
            "Альбом":   row.get("album"),
            "Год":      row.get("year"),
            "Жанр":     row.get("genre"),
        }

    def duration(self, uri):
        """Длительность в секундах из индекса сервера, None — неизвестно. Нужна слайдеру:
        для сетевого потока VLC первые секунды отдаёт get_length() = -1."""
        try:
            _, track_id = self._parse(uri)
            return self._track_row(track_id).get("duration")
        except (RemoteUnavailable, RemoteNotFound) as e:
            logger.error(f"duration {uri}: {e}")
            return None

    def details(self, uri):
        """Формат строк — как у LocalSource.details, иначе разница видна в UI.
        Битрейт сервер отдаёт уже в кбит/с: делить на 1000 НЕ нужно."""
        try:
            _, track_id = self._parse(uri)
            row = self._track_row(track_id)
        except (RemoteUnavailable, RemoteNotFound) as e:
            logger.error(f"details {uri}: {e}")
            return {"Длительность": "-", "Частота": "-", "Каналы": "-"}

        duration = row.get("duration")
        details = {
            "Длительность": f"{duration:.2f} сек" if duration else "-",
            "Частота": f"{row.get('sample_rate') or '-'} Гц",
            "Каналы": f"{row.get('channels') or '-'}",
        }
        # Ключи-опции добавляем только когда значение есть — как в LocalSource
        if row.get("bitrate"):
            details["Битрейт"] = f"{row['bitrate']} kbps"
        if row.get("bits"):
            details["Глубина бит"] = row["bits"]
        return details

    def cover(self, uri, size):
        try:
            _, track_id = self._parse(uri)
            return self._get(f"/server/track/{track_id}/cover",
                             params={"size": size}).content
        except (RemoteUnavailable, RemoteNotFound):
            return None   # обложки нет — штатная ситуация, не ошибка

    # ---- методы без сети ----

    def mrl(self, uri):
        track_id = self._parse(uri)[1]
        url = f"{SRV_BASE_URL}/server/stream/{track_id}"
        if SRV_TOKEN:
            # VLC заголовок не пошлёт — подпись в ссылке (см. stream_sig)
            url += f"?s={stream_sig(SRV_TOKEN, track_id)}"
        return url

    def is_dir(self, uri):
        try:
            return self._parse(uri)[0] == 'd'
        except RemoteNotFound:
            return False   # чужой server_id — точно не папка этого сервера

    def exists(self, uri):
        try:
            self._parse(uri)
            return True
        except RemoteNotFound:
            return False

    def reveal(self, uri):
        pass   # у сервера нет проводника

    def parent(self, uri):
        """URI родительской папки. Для трека — папка, в которой он лежит."""
        try:
            kind, rel = self._parse(uri)
        except RemoteNotFound:
            return self._dir_uri("")

        if kind == 't':
            # rel_path трека знает только сервер; если он недоступен,
            # возвращаем корень — это не критично
            try:
                rel = self._track_row(rel).get("rel_path", "")
            except (RemoteUnavailable, RemoteNotFound):
                return self._dir_uri("")

        rel = rel.strip('/')
        if '/' not in rel:
            return self._dir_uri("")          # на уровень выше — корень
        return self._dir_uri(rel.rsplit('/', 1)[0])

    def display_path(self, uri):
        """Подпись для адресной строки. Сети не требует."""
        try:
            kind, rel = self._parse(uri)
        except RemoteNotFound:
            return "Сервер"
        if kind == 't':
            return "Сервер"
        rel = rel.strip('/')
        return f"Сервер/{rel}" if rel else "Сервер"

    # ---- отладочный экран сервера (server_panel.py) ----
    # В отличие от методов выше, исключения RemoteUnavailable/RemoteNotFound
    # выпускаются наружу: экрану нужно показать, что именно не так

    def rescan(self):
        """Запустить пересканирование библиотеки. "started" или "running" (уже идёт)."""
        r = self._request("POST", "/server/rescan", allow=(409,))
        return "running" if r.status_code == 409 else "started"

    def _any_track_id(self):
        """id какого-нибудь трека для замера скорости: первая папка вглубь до трека.
        На строгой структуре Исполнитель/Альбом/трек это три запроса."""
        rel = ""
        for _ in range(6):
            rows = self._get("/server/browse", params={"folder_path": rel}).json()
            for row in rows:
                if row["type"] == "track":
                    return row["id"]
            folders = [row for row in rows if row["type"] == "folder"]
            if not folders:
                break
            rel = folders[0]["path"]
        raise RemoteNotFound("на сервере не нашлось ни одного трека")

    def measure_link(self, track_uri=None, samples=5, probe_bytes=2 * 1024 * 1024):
        """Замер связи для подбора network_caching.

        Время ответа — samples запросов /server/ping. Скорость — первые probe_bytes
        потока трека track_uri (или любого трека на сервере). Битрейт — из строки
        этого трека в индексе. Возвращает словарь для recommend_caching и экрана."""
        rtts = []
        for _ in range(samples):
            t0 = time.perf_counter()
            self._get("/server/ping")
            rtts.append((time.perf_counter() - t0) * 1000)

        track_id = self._parse(track_uri)[1] if track_uri and is_remote(track_uri) else self._any_track_id()
        row = self._track_row(track_id)
        t0 = time.perf_counter()
        r = self._request("GET", f"/server/stream/{track_id}", stream=True,
                          headers={"Range": f"bytes=0-{probe_bytes - 1}"})
        got = 0
        try:
            for chunk in r.iter_content(64 * 1024):
                got += len(chunk)
                if got >= probe_bytes:
                    break
        finally:
            r.close()
        sec = max(time.perf_counter() - t0, 1e-3)

        return {
            "rtt_avg": sum(rtts) / len(rtts),
            "rtt_max": max(rtts),
            "speed_kbps": got * 8 / 1000 / sec,
            "bitrate_kbps": row.get("bitrate") or 0,
            "track": f"{row.get('author') or '?'} — {row.get('name') or track_id}",
        }

    # ---- отладочный режим: файлы на сервере (docs/TZ_server_panel.md §5) ----
    # Исключения RemoteUnavailable / RemoteNotFound выходят наружу: экран показывает их сам.

    def me(self):
        """{"name": ..., "admin": bool}. RemoteNotFound — сервер старее 0.2."""
        return self._get("/server/me").json()

    def ls(self, rel=""):
        """Одна папка сервера с диска: {"dirs": [{name, path}], "files": [{name, path, size, kind}]}."""
        return self._get("/server/ls", params={"path": rel}).json()

    def list_files(self, rel=""):
        """Все аудио и картинки под папкой, рекурсивно: [{rel_path, size, kind}]."""
        return self._get("/server/files", params={"path": rel}).json()

    def start_op(self, folder):
        return self._request("POST", "/server/ops", params={"folder": folder}).json()["op_id"]

    def ops(self, mine=True):
        return self._get("/server/ops", params={"mine": int(mine)}).json()

    def undo(self, op_id):
        """{"removed": [...], "skipped": [{path, reason}], "dirs_removed": [...]}"""
        return self._request("POST", f"/server/ops/{op_id}/undo").json()

    def delete(self, rel):
        return self._request("DELETE", "/server/file", params={"path": rel}).json()

    def upload_file(self, rel, op_id, body):
        """PUT одного файла. body — объект с read() и __len__: requests шлёт его потоком
        с Content-Length, файл в память целиком не читается. Ответы 400/409/410/507
        возвращаются как есть — их причину экран показывает по файлу."""
        return self._request("PUT", "/server/file", params={"path": rel, "op": op_id}, data=body,
                             timeout=(SRV_TIMEOUT, TRANSFER_READ_TIMEOUT), allow=(400, 409, 410, 507))

    def download_file(self, rel):
        """GET одного файла потоком; закрыть ответ — дело вызывающего."""
        return self._request("GET", "/server/file", params={"path": rel}, stream=True,
                             timeout=(SRV_TIMEOUT, TRANSFER_READ_TIMEOUT))

    def search(self, query: str, folder_uri: str | None = None, items: list | None = None) -> list | None:
        """Функция активного поиска"""   
        if not query.strip():
            return []
        try:
            rel = ""
            if folder_uri:
                _, rel = self._parse(folder_uri)
            rows = self._get("/server/search", params={"q": query, "folder_path": rel}).json()
        except RemoteUnavailable as e:
            logger.error(f"search {query!r}: {e}")
            return None
        except RemoteNotFound as e:
            logger.error(f"search {query!r} в {folder_uri}: {e}")
            return []
        self._prime(rows)
        return [{"name": f"{row['author']} — {row['name']}" if row.get("author") else row["name"], "path": self._track_uri(row["id"]), "type": "track"} for row in rows]

LOCAL = LocalSource()
REMOTE = RemoteSource()

# ---- фоновый опрос сервера ----
# Состояние живёт в модуле: любой код может спросить sources.server_online(),
# не дожидаясь сети. Обновляет его отдельный поток.

_srv_state = {"online": False, "info": None, "uuid": None, "uuid_changed": False}
# Будит фоновый опрос раньше срока. Ставит _get, когда запрос не дошёл до сервера:
# иначе при доступном сервере о его пропаже узнали бы только через interval_online (60 с),
# и всё это время проводник пускал бы в «Сервер» и ждал таймаут на каждом клике
_wake = threading.Event()

def server_online() -> bool:
    """Отвечал ли сервер при последней проверке. Мгновенно, без сети."""
    return _srv_state["online"]

def server_info() -> dict | None:
    """Последний ответ /server/ping или None."""
    return _srv_state["info"]

CACHING_MIN, CACHING_MAX = 300, 10000   # границы ползунка в отладочном экране, мс

def recommend_caching(m: dict) -> int:
    """Рекомендуемый network_caching по замеру measure_link. Эвристика:
    скорости впритык к битрейту — большой буфер, чтобы пережить провалы;
    с запасом по скорости хватает нескольких времён ответа."""
    bitrate = m["bitrate_kbps"] or 1000   # битрейт неизвестен — считаем как FLAC
    ratio = m["speed_kbps"] / bitrate
    if ratio < 2:
        ms = 8000
    elif ratio < 5:
        ms = 5000
    else:
        ms = max(1000, 3 * m["rtt_max"])
    return int(min(CACHING_MAX, max(CACHING_MIN, round(ms / 100) * 100)))

def set_network_caching(ms: int, path="config.txt"):
    """Новый буфер сети VLC: сразу в SRV_CACHING (load_track берёт его для каждого
    серверного трека) и в config.txt.

    В файле меняется только строка network_caching в [Server]: configparser.write
    стёр бы все комментарии. BOM и переводы строк сохраняются как были."""
    global SRV_CACHING
    SRV_CACHING = int(ms)

    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    line = f"network_caching = {SRV_CACHING}"

    section, header_at, done = None, None, False
    for i, l in enumerate(lines):
        st = l.strip()
        if st.startswith("[") and st.endswith("]"):
            section = st[1:-1].strip()
            if section == "Server":
                header_at = i
            continue
        if section == "Server" and st.split("=", 1)[0].strip() == "network_caching" and "=" in st:
            lines[i] = line
            done = True
            break
    if not done:
        if header_at is None:
            lines += ["", "[Server]", line]
        else:
            lines.insert(header_at + 1, line)

    data = nl.join(lines).encode("utf-8")
    with open(path, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + data)
    logger.info(f"network_caching = {SRV_CACHING} мс (сохранено в {path})")

def start_server_watch(page, interval_online=60.0, interval_offline=15.0):
    """Опрашивает сервер в фоне и шлёт 'server_status' в UI при смене состояния.

    Вызывать ПОСЛЕ отрисовки окна: main.py синхронный, и проверка в пути
    запуска задержала бы появление окна на таймаут TCP.
    """
    if not SRV_ENABLED:
        logger.info("Сервер выключен в config.txt, фоновый опрос не запускается")
        return

    def run():
        while True:
            info = REMOTE.ping()
            was = _srv_state["online"]
            _srv_state["online"] = info is not None
            _srv_state["info"] = info

            if info:
                uuid = info.get("library_uuid")
                # Пересозданная library.db = другие id у тех же треков:
                # srv://home/t/48213 в плейлисте начнёт играть другую песню
                if _srv_state["uuid"] and uuid and uuid != _srv_state["uuid"]:
                    _srv_state["uuid_changed"] = True
                    logger.warning("library_uuid сервера изменился — библиотека пересоздана")
                _srv_state["uuid"] = uuid

            if was != _srv_state["online"]:
                logger.info("Сервер %s", "доступен" if _srv_state["online"] else "не отвечает")
                try:
                    page.pubsub.send_all_on_topic("server_status", dict(_srv_state))
                except RuntimeError:
                    return   # сессия закрыта
            # Недоступный сервер опрашиваем чаще: Pi, включённый после плеера,
            # должен подхватиться сам, без перезапуска приложения
            # _wake прерывает ожидание, если запрос из приложения не дошёл до сервера
            _wake.wait(interval_online if _srv_state["online"] else interval_offline)
            _wake.clear()

    threading.Thread(target=run, daemon=True).start()

def is_remote(uri) -> bool:
    return isinstance(uri, str) and uri.startswith("srv://")

def get(uri):
    return REMOTE if is_remote(uri) else LOCAL

_fold = search_rank.fold   # регистр и ё не важны — так же, как на сервере