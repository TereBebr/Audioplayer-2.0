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
from requests.exceptions import RequestException
import time
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

    def list_dir(self, folder_path: str):#анализ текущей папки (выбранной)
        path = Path(folder_path)
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
        path = Path(uri)
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

    def _get(self, path, params=None, stream=False):
        url = f"{SRV_BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {SRV_TOKEN}"} if SRV_TOKEN else {}
        try:
            r = self.session.get(url, params=params, headers=headers,
                                stream=stream, timeout=SRV_TIMEOUT)
        except RequestException as err:
            raise RemoteUnavailable(f"Сервер недоступен [{url}]: {err}") from err
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
        except (RemoteUnavailable, RemoteNotFound) as e:
            logger.error(f"meta {uri}: {e}")
            # Заглушка: строка в очереди останется читаемой, в БД не уедет None
            return {"Название": f"Трек {track_id} (сервер недоступен)",
                    "Автор": "Неизвестно", "Альбом": None, "Год": None, "Жанр": None}
        return {
            "Название": row.get("name") or f"Трек {track_id}",
            "Автор":    row.get("author") or "Неизвестно",
            "Альбом":   row.get("album"),
            "Год":      row.get("year"),
            "Жанр":     row.get("genre"),
        }

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
        return f"{SRV_BASE_URL}/server/stream/{track_id}"

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


LOCAL = LocalSource()
REMOTE = RemoteSource()

def is_remote(uri) -> bool:
    return isinstance(uri, str) and uri.startswith("srv://")

def get(uri):
    return REMOTE if is_remote(uri) else LOCAL