import os
import sys
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from pathlib import Path
import pathlib
import logging

logger = logging.getLogger(__name__)
#ИМПОРТ И ПРОВЕРКА VLC СРАЗУ ПОСЛЕ ЗАГРУЗКИ ФАЙЛА ---

base_dir = os.path.dirname(os.path.abspath(__file__))
vlc_dir = os.path.join(base_dir, 'vlc_engine')
vlc_dll_path = os.path.join(vlc_dir, 'libvlc.dll')
if os.path.exists(vlc_dll_path):
    os.environ['PYTHON_VLC_LIB_PATH'] = vlc_dll_path
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(vlc_dir)
# ТЕПЕРЬ импортируем vlc глобально для этого файла
try:
    import vlc
except ImportError:
    logger.debug("Ошибка: Библиотека python-vlc не установлена. Выполните: pip install python-vlc")

# ---

def import_VLC(base_dir):
    # Эта функция теперь просто проверяет, что всё ок
    if 'vlc' in globals():
        logger.debug(f"VLC движок найден и готов к работе: {vlc_dir}")
    return vlc_dir
    
def import_paths(base_dir,file_name): 
    #~~ ЧТЕНИЕ ФАЙЛА ~~
    file_path = "music/used"
    #file_name = "144.Raven.flac"
    full_path = os.path.join(base_dir, file_path, file_name)
    return file_path, file_name, full_path

from mutagen import FileType

def tec_info(audio):
    #~~ ТЕХ ДАННЫЕ ФАЙЛА ~~
    if audio is None:
        return 0
    if not isinstance(audio, FileType):
        logger.error("Mutagen не поддерживает медиафайл")
        return 0
    if isinstance(audio, MP3):
        return 1
    if isinstance(audio, FLAC):
        return 2
    if isinstance(audio, OggVorbis):
        return 3
    if isinstance(audio, MP4):
        return 4
    return 0

def get_audio_info(audio, tec_audio_info_num):
    if audio is None:
        return "Неизвестный формат"

    data = audio.info
    match tec_audio_info_num:
        case 0: #-
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
        case 1: #MP3
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Битрейт": f"{data.bitrate // 1000} kbps",
                "Каналы": f"{data.channels}",
            }
        case 2: #FLAC
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Битрейт": f"{getattr(data, 'bitrate', 0) // 1000} kbps",
                "Глубина бит": getattr(data, 'bits_per_sample', '-'),
                "Каналы": f"{data.channels}",
            }
        case 3: #OGG
            details = {
                "Длительность": f"{data.length:.2f} сек",
                "Частота": f"{data.sample_rate} Гц",
                "Каналы": f"{data.channels}",
            }
            bitrate = getattr(data, 'bitrate', None)
            if bitrate:
                details["Битрейт"] = f"{bitrate // 1000} kbps"
        case 4: #MP4
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
        case _:
            details = {
                "Длительность": f"{getattr(data, 'length', 0):.2f} сек",
                "Частота": f"{getattr(data, 'sample_rate', '-')} Гц",
                "Каналы": f"{getattr(data, 'channels', '-')}",
            }
    return details
    
def get_audio_tags(audio, path):
    if audio is None or audio.tags is None:
        return {"Название": path.stem, "Автор": (path.parent.parent).stem, "Альбом": (path.parent).stem, "Год": "", "Жанр": "",}
    tags = {}
    
    # 1. Если MP3 (ID3)
    if isinstance(audio, MP3):
        tags = {
            "Название": str(audio.get('TIT2', path.stem)),
            "Автор": str(audio.get('TPE1', (path.parent.parent).stem)),
            "Альбом": str(audio.get('TALB', (path.parent).stem)),
            "Год": str(audio.get('TDRC', audio.get('TYER', '-'))),
            "Жанр": str(audio.get('TCON', '-'))
        }
    # 2. Если FLAC или др с Vorbis Comments
    elif isinstance(audio, FLAC) or hasattr(audio, 'tags'):
        # У Vorbis тегов ключи обычно в нижнем регистре и возвращают список
        def get_vorbis(key, default):
            val = audio.get(key)
            return val[0] if val else default

        tags = {
            "Название": get_vorbis('title', path.stem),
            "Автор": get_vorbis('artist', (path.parent.parent).stem),
            "Альбом": get_vorbis('album', (path.parent).stem),
            "Год": get_vorbis('date', '-'),
            "Жанр": get_vorbis('genre', '-')
        }
    elif isinstance(audio, MP4):
        tags = {
            "Название": str(audio.get('\xa9nam', [path.stem])[0]),
            "Автор": str(audio.get('\xa9ART', [(path.parent.parent).stem])[0]),
            "Альбом": str(audio.get('\xa9alb', [(path.parent).stem])[0]),
            "Год": str(audio.get('\xa9day', ['-'])[0]),
            "Жанр": str(audio.get('\xa9gen', ['-'])[0]),
        }
    else:
        tags = {
            "Название": str(audio.get('\xa9nam', [path.stem])[0]),
            "Автор": str(audio.get('\xa9ART', [(path.parent.parent).stem])[0]),
            "Альбом": str(audio.get('\xa9alb', [(path.parent).stem])[0]),
            "Год": str(audio.get('\xa9day', ['-'])[0]),
            "Жанр": str(audio.get('\xa9gen', ['-'])[0]),
        }
    return {k: str(v) for k, v in tags.items()}

def create_player(path, start_vol_val):
    # 1. Создаем экземпляр с параметрами    
    vlc_args = [
        '--no-video', 
        '--quiet',
        '--audio-filter=normvol',
        '--norm-max-level=2.0' 
    ]
    instance = vlc.Instance(*vlc_args)

    media_list = instance.media_list_new()
    # 2. Создаем плеер
    player = instance.media_player_new()
    # 3. Загружаем файл
    media = instance.media_new(path)
    player.audio_set_volume(start_vol_val)
    player.set_media(media)
    logger.debug("VLC Объект плеера создан")
    return player


import io
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

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
    logger.error(f"⚠️ mutagen не смог прочитать файл штатно, анализируем содержимое: {path}")

    with open(path, "rb") as f:
        data = f.read()

    # 1. Пробуем как настоящий FLAC (с пропуском мусора перед маркером)
    offset = find_flac_offset(data)
    if offset != -1:
        try:
            audio = FLAC(io.BytesIO(data[offset:]))
            logger.debug(f"✅ Валидный FLAC-поток (смещение {offset}): {path}")
            return audio
        except Exception as e:
            logger.debug(f"fLaC-маркер найден, но разбор не удался: {e}")

    # 2. Похоже, это MP3 под чужим расширением
    if find_mpeg_sync(data) != -1:
        try:
            audio = MP3(path)
            logger.debug(f"✅ Файл на самом деле MP3 (переименован/не докодирован): {path}")
            return audio
        except Exception as e:
            logger.debug(f"MPEG sync найден, но MP3-парсер не справился: {e}")

    logger.error(f"❌ Формат не определён, будут использованы значения по умолчанию: {path}")
    return None