from pathlib import Path
from tinytag import TinyTag
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from mutagen.id3 import APIC
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)
# TODO сделать проверку в extract_cover если есть папка то взять какую-нибудь картинку
COVER_NAMES = ["Прости меня моя любовь (фронт).jpg", "cover.jpg", "cover.png", "1.jpg", "1.png", "folder.jpg", "folder.png", "front.jpg", "front.png", "img001.jpg", "img001.png", "img01.jpg", "img01.png", "img1.jpg", "img1.png", "img.jpg", "img.png", "image.jpg", "image.png"]
COVER_DIR_NAMES = ["covers", "cover", "scans", "artwork"]

def tt_parse(path: Path) -> dict:
    try:
        tag = TinyTag.get(path)
    except Exception:
        tag = None

    def safe_get(attr):
        return getattr(tag, attr, None) if tag else None

    duration = safe_get('duration')
    bitrate = safe_get('bitrate')

    cover = None
    if tag:
        try:
            cover = tag.get_image()
        except Exception:
            cover = None
    if cover is None:
        cover = possible_covers(path)

    return {
        "Название": safe_get('title') or path.stem,
        "Автор": safe_get('artist') or path.parent.parent.stem,
        "Альбом": safe_get('album') or path.parent.stem,
        "Год": str(safe_get('year')) if safe_get('year') else None,
        "Жанр": safe_get('genre'),
        "Длительность": float(f"{duration:.2f}") if duration and duration > 0 else None,
        "Частота": safe_get('samplerate'),
        "Битрейт": bitrate if bitrate and bitrate > 0 else None,
        "Каналы": safe_get('channels'),
        "Глубина Бит": safe_get('bitdepth'),
        "Обложка": cover
    }

def read_tags(path: Path) -> dict:
    """
    Возвращает:
      name, author, album, year, genre   -> str | None
      duration                           -> float | None
      sample_rate, bitrate, channels, bits -> int | None
      cover                              -> bytes | None  (оригинальные байты, не сжатые)
    Никогда не бросает исключение наружу: если файл не читается,
    возвращает словарь с name = path.stem, родителями - альбомом и автором, потому что именно
    такой у меня паттерн и хранения данных. Так же попробовал распарсить duration через tinytag
    """
    try:
        return _read_tags(path)
    except Exception as e:
        # Обещание «никогда не бросает» держим здесь: битый файл, PermissionError,
        # неожиданный формат — всё уходит в лог, индексатор получает заглушку
        logger.warning("read_tags: %s: %s", path, e)
        return tt_parse(path)


def _read_tags(path: Path) -> dict:
    try:
        audio = mutagen.File(path)
    except Exception:
        audio = detect_and_load_audio(path)

    if audio is None or audio.tags is None:
        return tt_parse(path)

    data = audio.info

    raw_bitrate = getattr(data, 'bitrate', None)
    bitrate_kbps = (raw_bitrate // 1000) if raw_bitrate else None
    raw_len = getattr(data, 'length', None)
    duration_val = round(float(raw_len), 2) if raw_len else None

    if isinstance(audio, MP3):
        # В MP3 текст хранится внутри объекта фрейма, нужно доставать через .text[0]
        def get_id3(key, default):
            frame = audio.get(key)
            if frame and hasattr(frame, 'text') and frame.text:
                return str(frame.text[0])
            return default

        tags = {
            "Название": get_id3('TIT2', path.stem),
            "Автор": get_id3('TPE1', (path.parent.parent).stem),
            "Альбом": get_id3('TALB', (path.parent).stem),
            "Год": get_id3('TDRC', get_id3('TYER', None)),
            "Жанр": get_id3('TCON', None),
            "Длительность": duration_val,
            "Частота": getattr(data, 'sample_rate', None),
            "Битрейт": bitrate_kbps,
            "Каналы": getattr(data, 'channels', None),
            "Глубина Бит": getattr(data, 'bits', None),
            "Обложка": extract_cover(audio, path, "MP3OGG")
        }

    elif isinstance(audio, FLAC) or isinstance(audio, OggVorbis):
        # У Vorbis тегов ключи обычно в нижнем регистре и возвращают список
        def get_vorbis(key, default):
            val = audio.get(key)
            return str(val[0]) if val else default

        tags = {
            "Название": get_vorbis('title', path.stem),
            "Автор": get_vorbis('artist', (path.parent.parent).stem),
            "Альбом": get_vorbis('album', (path.parent).stem),
            "Год": get_vorbis('date', None),
            "Жанр": get_vorbis('genre', None),
            "Длительность": duration_val,
            "Частота": getattr(data, 'sample_rate', None),
            "Битрейт": bitrate_kbps,
            "Каналы": getattr(data, 'channels', None),
            "Глубина Бит": getattr(data, 'bits_per_sample', None),
            "Обложка": extract_cover(audio, path, "FLACWAV")
        }

    elif isinstance(audio, MP4):
        def get_mp4(key, default):
            val = audio.get(key)
            return str(val[0]) if val else default

        tags = {
            "Название": get_mp4('\xa9nam', path.stem),
            "Автор": get_mp4('\xa9ART', (path.parent.parent).stem),
            "Альбом": get_mp4('\xa9alb', (path.parent).stem),
            "Год": get_mp4('\xa9day', None),
            "Жанр": get_mp4('\xa9gen', None),
            "Длительность": duration_val,
            "Частота": getattr(data, 'sample_rate', None),
            "Битрейт": bitrate_kbps,
            "Каналы": getattr(data, 'channels', None),
            "Глубина Бит": getattr(data, 'bits_per_sample', None),
            "Обложка": extract_cover(audio, path, "MP4")
        }

    else: tags = tt_parse(path)

    return tags


def extract_cover(audio, path, tec_audio_info=None):
        raw_data = None
        
        if tec_audio_info == "MP3OGG": #mp3, ogg
            if hasattr(audio, 'tags') and audio.tags is not None:
                for tag in audio.tags.values():
                    if hasattr(tag, 'data') and (hasattr(tag, 'type') and 'pic' in str(tag).lower() or isinstance(tag, APIC)): # type: ignore
                        raw_data = tag.data
                        break
        elif tec_audio_info == "FLACWAV": #flac, wav
            if hasattr(audio, 'pictures') and audio.pictures:
                raw_data = audio.pictures[0].data
        elif tec_audio_info == "MP4":
            covr = audio.get('covr') if hasattr(audio, 'get') else None
            if covr:
                raw_data = bytes(covr[0])
        if raw_data is None:
            raw_data = possible_covers(path)
        return raw_data


def possible_covers(path: Path):
    try:
        folder_path = Path(path).resolve().parent
    except Exception:
        return None
    cover_path = None

    # в папке с файлом
    try:
        for item in folder_path.iterdir():
            if item.is_file() and item.name.lower() in COVER_NAMES:
                cover_path = item
                break
    except Exception:
        return None
    if cover_path is None:
        try:
            for item in folder_path.iterdir():
                if item.is_dir() and item.name.lower() in COVER_DIR_NAMES:
                    for sub_item in item.iterdir():
                        if sub_item.is_file() and sub_item.name.lower() in COVER_NAMES:
                            cover_path = sub_item
                            break
                    if cover_path:
                        break
        except Exception:
            return None
    if cover_path and cover_path.exists():
        try:
            with Image.open(cover_path) as image:
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")
                
                output_buffer = io.BytesIO()
                image.save(output_buffer, format="JPEG", quality=90)
                return output_buffer.getvalue()
        except Exception:
            return None
    return None

def find_flac_offset(data: bytes) -> int:
    """Ищет валидный fLaC-маркер (с проверкой STREAMINFO) по всему буферу."""
    start = 0
    while True:
        idx = data.find(b"fLaC", start)
        if idx == -1:
            return -1
        if idx + 8 <= len(data):
            block_header = data[idx + 4: idx + 8]
            block_type = block_header[0] & 0x7F
            block_length = int.from_bytes(block_header[1:4], "big")
            if block_type == 0 and block_length == 34:
                return idx
        start = idx + 1


def find_mpeg_sync(data: bytes, start: int = 0) -> int:
    """Ищет валидный MPEG frame sync (0xFF Ex)."""
    i = start
    while i < len(data) - 1:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            return i
        i += 1
    return -1

def detect_and_load_audio(path):
    """
    Определяет реальный формат файла по содержимому, а не по расширению.
    Нужна для случаев, когда конвертер mp3->flac не отработал и файл
    физически остался MP3-потоком под .flac-именем (либо есть мусор/
    битый ID3-хвост перед настоящим fLaC-маркером).
    Файл на диске не модифицируется.
    """

    with open(path, "rb") as f:
        data = f.read()

    # 1. Пробуем как настоящий FLAC (с пропуском мусора перед маркером)
    offset = find_flac_offset(data)
    if offset != -1:
        try:
            audio = FLAC(io.BytesIO(data[offset:]))
            return audio
        except Exception as e:
            pass
    # 2. Похоже, это MP3 под чужим расширением
    if find_mpeg_sync(data) != -1:
        try:
            audio = MP3(path)
            return audio
        except Exception as e:
            pass
    return None