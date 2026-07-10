import os
import sys
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

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
    print("Ошибка: Библиотека python-vlc не установлена. Выполните: pip install python-vlc")

# ---

def import_VLC(base_dir):
    # Эта функция теперь просто проверяет, что всё ок
    if 'vlc' in globals():
        print(f"VLC движок готов: {vlc_dir}")
    return vlc_dir
    
def import_paths(base_dir,file_name): 
    #~~ ЧТЕНИЕ ФАЙЛА ~~
    file_path = "music/used"
    #file_name = "144.Raven.flac"
    full_path = os.path.join(base_dir, file_path, file_name)
    return file_path, file_name, full_path
    
def tec_info(full_path,audio):
    #~~ ТЕХ ДАННЫЕ ФАЙЛА ~~
    if audio is None:
        return 0
        print("Формат файла не поддерживается Mutagen")
    if full_path.lower().endswith(('.mp3', '.ogg', '.mp4')):
        #print("Формат тех. данных файла №1")
        return 1
    elif full_path.lower().endswith(('.flac','.wav')):
        #print("Формат тех. данных файла №2")
        return 2
    return 0

def get_audio_info(audio, tec_audio_info_num):
    if audio is None: return "Неизвестный формат"
    match tec_audio_info_num:
        case 0:
            details = {
                "Длительность": f"{audio.info.length:.2f} сек",
                "Частота": f"{audio.info.sample_rate} Гц",
                "Каналы": f"{audio.info.channels}",
            }
            
        case 1:
            details = {
                "Длительность": f"{audio.info.length:.2f} сек",
                "Частота": f"{audio.info.sample_rate} Гц",
                "Битрейт": f"{audio.info.bitrate // 1000} kbps",
                "Каналы": f"{audio.info.channels}",
            }
           
        case 2:
            details = {
                "Длительность": f"{audio.info.length:.2f} сек",
                "Частота": f"{audio.info.sample_rate} Гц",
                "Битрейт": f"{audio.info.bitrate // 1000} kbps",
                "Глубина бит": getattr(audio.info, 'bits_per_sample'),
                "Каналы": f"{audio.info.channels}",
            }  
    return details
    
def get_audio_tags(audio, file_name):
    if audio is None or audio.tags is None:
        return {"Название": file_name, "Автор": "Неизвестный исполнитель", "Альбом": "Неизвестный альбом", "Год": "", "Жанр": "",}
    tags = {}
    
    # 1. Если MP3 (ID3)
    if isinstance(audio, MP3):
        tags = {
            "Название": str(audio.get('TIT2', file_name)),
            "Автор": str(audio.get('TPE1', "Неизвестный исполнитель")),
            "Альбом": str(audio.get('TALB', '-')),
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
            "Название": get_vorbis('title', file_name),
            "Автор": get_vorbis('artist', "Неизвестный исполнитель"),
            "Альбом": get_vorbis('album', '-'),
            "Год": get_vorbis('date', '-'),
            "Жанр": get_vorbis('genre', '-')
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
    return player