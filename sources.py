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


SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.mp4'}
COVER_NAMES = ["Прости меня моя любовь (фронт).jpg", "cover.jpg", "cover.png", "1.jpg", "1.png", "folder.jpg", "folder.png", "front.jpg", "front.png", "img001.jpg", "img001.png", "img01.jpg", "img01.png", "img1.jpg", "img1.png", "img.jpg", "img.png", "image.jpg", "image.png"]
COVER_DIR_NAMES = ["covers", "cover", "scans", "artwork"]

import configparser
config = configparser.ConfigParser()
config.read('config.txt', encoding='utf-8')
idxDirrs = config.getboolean('Main Settings', 'idxDirrs')

class LocalSource:

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


class RemoteSource:
    pass

LOCAL = LocalSource()
REMOTE = RemoteSource()

def is_remote(uri) -> bool:
    return isinstance(uri, str) and uri.startswith("srv://")

def get(uri):
    return REMOTE if is_remote(uri) else LOCAL