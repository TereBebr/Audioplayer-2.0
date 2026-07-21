import flet as ft
import os
import time
import mutagen
from mutagen.id3 import APIC
from pathlib import Path
from itertools import chain
import utils
import database
import pathlib
import threading
import time
import io
from PIL import Image, ImageDraw, ImageOps, ImageEnhance
import sqlite3
import random
from mutagen.flac import FLACNoHeaderError
import subprocess

player = None
tags = None
details = None
tec_audio_info_num = 0
curr_sec = 0
total_sec = 0
is_dragging = False
is_paused = False

SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.mp4'}

import configparser
config = configparser.ConfigParser()
config.read('config.txt', encoding='utf-8')

sorttype = config.getint('Main Settings', 'sorttype') # Не трогать, оставить 0 по стандарту
upd_time = config.getfloat('Main Settings', 'upd_time') # Время обновления динамических данных о музыке (с) \хавает проц. оптимально 0.25-0.5 c:0.25
autoplayswitch = config.getboolean('Main Settings', 'autoplayswitch') # Автопауза при смене трека
idxDirrs = config.getboolean('Main Settings', 'idxDirrs') # если True читает все подпапки во время добавления в очередь папки, если False, только то что внутри папки
max_histlen = (config.getint('Main Settings', 'max_histlen') * -1) # Максимальная длина истории проигранных треков
start_vol_val = config.getint('Main Settings', 'start_vol_val')

possible_covers = ["cover.jpg", "Cover.jpg", "cover.png", "folder.jpg"]

#Системные функции ----

def rgba(r: int, g: int, b: int, a: int = 255) -> str:
    """Конвертирует привычные RGBA (0-255) в формат ARGB-строки для Flet.
    a = 255 (полная непрозрачность по умолчанию), 0 (полная прозрачность)."""
    r, g, b, a = [max(0, min(255, x)) for x in (r, g, b, a)]
    return f"#{a:02x}{r:02x}{g:02x}{b:02x}"

def change_color(e): #изменение цвета кнопки при наведении
    image_content = e.control.content
    uicolor = rgba(79, 163, 196, 255)
    if str(e.data).lower() == "true":
        image_content.color = uicolor  # Цвет при наведении
        e.control.scale = 1.05         # Встроенная анимация: кнопка слегка увеличивается, приглашая нажать
    else:
        image_content.color = None
        e.control.scale = 1.0          # Возвращаем исходный размер
    e.control.update()

def extract_cover(audio, tec_audio_info_num, path):
        raw_data = None
        
        if tec_audio_info_num == 1: #mp3, ogg
            if hasattr(audio, 'tags') and audio.tags is not None:
                for tag in audio.tags.values():
                    if hasattr(tag, 'data') and (hasattr(tag, 'type') and 'pic' in str(tag).lower() or isinstance(tag, APIC)): # type: ignore
                        raw_data = tag.data
                        break
        elif tec_audio_info_num == 2: #flac, wav
            if hasattr(audio, 'pictures') and audio.pictures:
                raw_data = audio.pictures[0].data
        if not raw_data:
            folder_path = os.path.dirname(path)
            for cover_name in possible_covers:
                cover_path = os.path.join(folder_path, cover_name)

                if os.path.exists(cover_path):
                    image = Image.open(cover_path)
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")  
                    output_buffer = io.BytesIO()
                    image.save(output_buffer, format="JPEG", quality=90) #q=90-95
                    full_cover_bytes = output_buffer.getvalue()
                    return full_cover_bytes
        return raw_data

def extract_cover_bytes(path): # Извлечение миниатюры 50x50p
    global possible_covers
    # if not os.path.exists(path):
    #     return None
    raw_data = None
    # === ШАГ 1: Извлечение оригинальных байтов ===
    try:
        try:
            audio = mutagen.File(path)
            if audio is None:
                raise FLACNoHeaderError("Файл не распознан")
        except (FLACNoHeaderError, Exception):
            print(f"Попытка исправления файла: {path}")
            audio = fix_and_load_flac(path)
        
        # (ID3)
        if audio:
            if hasattr(audio, 'tags') and audio.tags:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC) or (hasattr(tag, 'type') and 'pic' in str(tag).lower()): # type: ignore
                        raw_data = tag.data
                        break
            
            # (FLAC, OGG, некоторые MP4)
            if not raw_data and hasattr(audio, 'pictures') and audio.pictures:
                raw_data = audio.pictures[0].data

    except Exception as e:
        print(f"Ошибка при чтении тегов из {path}: {e}. Идет поиск обложки в папке")

    # === ШАГ 2: Сжатие для базы данных ===
    if raw_data:
        try:
            image = Image.open(io.BytesIO(raw_data))
            
            # Убираем альфа-канал, если это PNG, чтобы JPEG не выдал ошибку
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            image.thumbnail((50,50), Image.Resampling.LANCZOS)
            # Сохраняем в новый байтовый буфер
            output_buffer = io.BytesIO()
            image.save(output_buffer, format="JPEG", quality=85)
            
            return output_buffer.getvalue()
            
        except Exception as e:
            print(f"Ошибка при сжатии картинки {path}: {e}")
            # Если Pillow не смог прочитать байты (битая картинка), 
            # возвращаем оригинальные байты как страховку
            return raw_data
    else:
        folder_path = os.path.dirname(path) 
        for cover_name in possible_covers:
            cover_path = os.path.join(folder_path, cover_name)

            if os.path.exists(cover_path):
                print(f"Найдена локальная обложка: {cover_path}")
                try:
                    image = Image.open(cover_path)
                    
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")    
                    image.thumbnail((50,50), Image.Resampling.LANCZOS)
                    output_buffer = io.BytesIO()
                    image.save(output_buffer, format="JPEG", quality=85)
                    return output_buffer.getvalue()
                
                except Exception as e:
                    print(f"Ошибка при обработке локального cover.jpg в папке {folder_path}: {e}")
    print(f"Обложка для {path} не найдена ни в тегах, ни в папке.")
    return None

#Функции проводника ----

def get_folder_content(folder_path: str | Path):#анализ текущей папки (выбранной)
    path = Path(folder_path)
    if not path.exists() or not path.is_dir():
        return [], []
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

    #Виды сортировок // потом как-нибудь
    match sorttype:
        case 0: 
            folders.sort(key=lambda x: x["name"].lower())
            tracks.sort(key=lambda x: x["name"].lower())
        case 1:
            pass

    return folders + tracks

def fix_and_load_flac(path):
    """Пытается исправить заголовок через ffmpeg и прочитать файл."""
    str_path = str(path)
    fixed_path = str_path.replace(".flac", "_fixed.flac")
    
    # ffmpeg копирует поток в новый контейнер, исправляя структуру заголовка
    cmd = ['ffmpeg', '-y', '-i', str_path, '-c:a', 'copy', fixed_path]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        # После исправления пробуем прочитать уже новый файл
        return mutagen.File(fixed_path, easy=True)
    except Exception as e:
        print(f"Не удалось исправить файл {path}: {e}")
        return None

def on_item_click(e, rebuild_callback, play_btn_obj): #при клике на объект
        text = e.control.data
        p = Path(text).resolve()
        if p.is_dir():
            print(f"папка: {p}")
            new_items = fnew_path(p)
            rebuild_callback(new_items, p)    # Вызываем функцию перерисовки UI
        else:
            #в 0 эл. очереди
            try:
                audio = mutagen.File(p)
                if audio is None:
                    raise FLACNoHeaderError("Файл не распознан")
            except (FLACNoHeaderError, Exception):
                print(f"Попытка исправления файла: {p}")
                audio = fix_and_load_flac(p)
            
            if audio:
                print("Файл успешно открыт:", audio.get('title'))
            # else:
            #     print("Ошибка: файл не удалось открыть даже после исправления.")

            tags = utils.get_audio_tags(audio, p)
            miniature = extract_cover_bytes(p)

            con_queue = sqlite3.connect('queue.db')
            cursor = con_queue.cursor()
            cursor.execute('DELETE FROM queue WHERE id = ?', (0,))
            cursor.execute("INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)", 
                           (0, tags["Название"] if tags["Название"] else p.name, tags["Автор"], str(p), miniature))
            con_queue.commit()
            con_queue.close()

            load_track(e.page,p, play_btn_obj, 0)
            print(f"файл: {p}")

def fnew_path(p):
    folder_items = get_folder_content(p)
    #print(p)
    return folder_items

def on_accept_drag(e): #Конец перетаскивания
     pass

#строка пути
def on_segment_click(e, target_path, rebuild_callback):
    """Срабатывает при клике на сегмент (TextSpan) пути."""
    p = Path(target_path).resolve()
    if p.exists() and p.is_dir():
        new_items = get_folder_content(p) 
        rebuild_callback(new_items, p)
    else:
        print(f"{p} не существует")


def on_dialog_result(directory_path, rebuild_callback):
    """Срабатывает, когда пользователь выбрал папку в системном окне."""
    p = Path(directory_path).resolve()
    
    if p.exists() and p.is_dir():
        new_items = get_folder_content(p) # Твоя функция чтения папки
        rebuild_callback(new_items, p)
    else:
        print(f"Выбранная папка {p} не существует или недоступна")

#Функции кнопок ----

def playpause_btn_ev(e, play_btn_obj):
        #анимация --
        global is_paused
        e.control.scale = 0.92 # Делаем микро-сжатие при клике
        e.control.update()
        time.sleep(0.05) # крошечная пауза для визуального эффекта зажатия
        e.control.scale = 1.05 # возвращаем к размеру наведения
        e.control.update()
        #--

        if player: 
            if player.is_playing():
                player.pause()
                is_paused = True
                play_btn_obj.src = "assets/icons/play_ico_inac.png"
            else: 
                player.play()
                is_paused = False
                play_btn_obj.src="assets/icons/pause_ico_inac.png"
            play_btn_obj.update()
        else:
            try:
                con_queue = sqlite3.connect('queue.db')
                cursor = con_queue.cursor()
                cursor.execute("SELECT path FROM queue WHERE id = 0")
                r = cursor.fetchone()
                con_queue.close()
                
                if r:
                    load_track(e.page, r[0], play_btn_obj, -2)
                    #player.play()
                    #смена иконки
            except Exception as ex:
                print(f"Нет id 0: {ex}")
                pass
            #player.play()
            #смена иконки

def slider_on_dragging(e: ft.ControlEvent, time_label): #чтоб не дергался при перемотке
    global is_dragging
    sec = int(e.control.value)
    time_label.value = f"{sec // 60:02d}:{sec % 60:02d}"
    time_label.update()

    #e.page.update()
    is_dragging = True

def slider_event(e: ft.ControlEvent, time_label):
    global curr_sec, is_dragging
    if player:
        sec = int(e.control.value)
        player.set_time(sec * 1000)

        time_label.value = f"{sec // 60:02d}:{sec % 60:02d}"
        time_label.update()

        curr_sec = sec
    else:
        print("!player")
    is_dragging = False

def vol_slider_event(e, vol_label):
    if player:
        vol_label.value = int(e.control.value)
        vol_label.update()
        player.audio_set_volume(int(e.control.value))
    else:
        print("!player")

#Логика воспроизведение аудио ----

def load_track(page,path, play_btn_obj, idx): #через проводник
    global player, tags, details, tec_audio_info_num, curr_sec, total_sec, is_paused
    curr_sec = 0
    total_sec = 0
    p = Path(path).resolve()
    
    try:
        audio = mutagen.File(p)
        if audio is None:
            raise FLACNoHeaderError("Файл не распознан")
    except (FLACNoHeaderError, Exception):
        print(f"Попытка исправления файла: {p}")
        audio = fix_and_load_flac(p)
    
    if audio:
        print("Файл успешно открыт:", audio.get('title'))
    # else:
    #     print("Ошибка: файл не удалось открыть даже после исправления.")

    if player:
        player.stop()
        player.set_mrl(path)
        if autoplayswitch == False:
            player.play()
            play_btn_obj.src = "assets/icons/pause_ico_inac.png"
            is_paused = False
        else: 
            play_btn_obj.src = "assets/icons/play_ico_inac.png"
            is_paused = False
        play_btn_obj.update()
    else:
        player = utils.create_player(p, start_vol_val)
        time.sleep(0.5)
        #vol_slider.set(self.player.audio_get_volume())
        #vol_label.configure(text=f"{self.player.audio_get_volume()}%")
        player.play()
        is_paused = False
        play_btn_obj.src = "assets/icons/pause_ico_inac.png"
        play_btn_obj.update()
    tags = utils.get_audio_tags(audio, p)
    tec_audio_info_num = utils.tec_info(str(p), audio)
    details = utils.get_audio_info(audio, tec_audio_info_num)
    #cover = extract_cover(audio, tec_audio_info_num, p)
    tags["cover"] = extract_cover(audio, tec_audio_info_num, p)
    tags["idx"] = idx
    page.pubsub.send_all_on_topic("tags_update", tags)
    # очистка истории < max_histlen
    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()
    cursor.execute('DELETE FROM queue WHERE id < ?', (max_histlen,))
    con_queue.commit()
    con_queue.close()


def play_next_or_pred(e, switch, play_btn_obj): #Если True, то следующий, если False - предыдущий
    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()
    if switch:
        cursor.execute("SELECT path FROM queue WHERE id = 1")
        r = cursor.fetchone()
        idx = 1
        if r:
            cursor.execute("UPDATE queue SET id = id -1")
    else:
        cursor.execute("SELECT path FROM queue WHERE id = -1")
        r = cursor.fetchone()
        idx = 0
        if r:
            cursor.execute("UPDATE queue SET id = id +1")

    # cursor.execute("SELECT path FROM queue WHERE id = 0")
    # r = cursor.fetchone()
            
    con_queue.commit()
    con_queue.close()
    
    if r:
        real_path = r[0] # Берем строку из кортежа
        # load_track сам сделает Path(real_path).resolve()
        load_track(e.page, real_path, play_btn_obj, idx)
    else:
        print("В очереди нет треков для воспроизведения")

def add_queue(p, insert_at=None): # <--- Добавили аргумент insert_at
    path = Path(p)
    files_to_add = []

    if path.is_dir():
        pattern = path.rglob('*') if idxDirrs else path.iterdir()
        for obj in pattern:
            if obj.is_file() and obj.suffix.lower() in SUPPORTED_FORMATS:
                files_to_add.append(obj)
    elif path.is_file():
        if path.suffix.lower() in SUPPORTED_FORMATS:
            files_to_add.append(path)

    if not files_to_add:
        return

    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()
    
    try:
        if insert_at is None:
            # Обычное добавление в конец
            cursor.execute("SELECT MAX(id) FROM queue")
            max_id = cursor.fetchone()[0]
            start_id = 0 if max_id is None else max_id + 1
        else:
            # Вставка по индексу: сдвигаем все элементы вниз на количество новых файлов
            num_files = len(files_to_add)
            cursor.execute("UPDATE queue SET id = id + ? WHERE id >= ?", (num_files, insert_at))
            start_id = insert_at
            
        current_id = start_id
        for obj in files_to_add:
            try:
                try:
                    audio = mutagen.File(obj)
                    if audio is None:
                        raise FLACNoHeaderError("Файл не распознан")
                except (FLACNoHeaderError, Exception):
                    print(f"Попытка исправления файла: {obj}")
                    audio = fix_and_load_flac(obj)
                
                if audio:
                    print("Файл успешно открыт:", audio.get('title'))
                # else:
                #     print("Ошибка: файл не удалось открыть даже после исправления.")

                tags = utils.get_audio_tags(audio, obj)
                name = tags["Название"] if tags.get("Название") else obj.name
                author = tags.get("Автор", "Неизвестно")
                miniature = extract_cover_bytes(obj)

                cursor.execute(
                    "INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)",
                    (current_id, name, author, str(obj), miniature))
                current_id += 1
            except Exception as e:
                print(f"Ошибка чтения файла {obj}: {e}")
        
        con_queue.commit()
    except Exception as e:
        print(f"Ошибка БД при добавлении в очередь: {e}")
        con_queue.rollback()
    finally:
        con_queue.close()
        print(f"Добавлено {len(files_to_add)} файлов.")

def mix_queue(rebuild_queue):
    con = sqlite3.connect('queue.db')
    cursor = con.cursor()
    cursor.execute("SELECT rowid, id FROM queue WHERE id > 0;")
    rows = cursor.fetchall()
    if rows:
        rowids = [row[0] for row in rows]
        ids = [row[1] for row in rows]
        random.shuffle(ids)
        # zip(ids, rowids) создаст пары вида (новый_id, старый_rowid)
        cursor.executemany("UPDATE queue SET id = ? WHERE rowid = ?;", zip(ids, rowids))
    con.commit()
    con.close()
    rebuild_queue()

#----
# Плейлисты ----

def add_track_to_playlist(cursor, playlist_id, track_id, insert_at=None):
    if insert_at is None:
        # Добавляем в конец плейлиста
        cursor.execute("SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
        last_pos = cursor.fetchone()[0] or 0
        new_position = last_pos + 1
    else:
        # Вставка по индексу: сдвигаем ПОЗИЦИИ (position) в плейлисте, а не ID треков!
        cursor.execute("""
            UPDATE playlist_tracks 
            SET position = position + 1 
            WHERE playlist_id = ? AND position >= ?
        """, (playlist_id, insert_at))
        new_position = insert_at

    # Добавляем трек в плейлист. 
    # Используем IGNORE, чтобы не добавить один и тот же трек в Избранное дважды
    cursor.execute("""
        INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position)
        VALUES (?, ?, ?)
    """, (playlist_id, track_id, new_position))


def add_favorite(p, insert_at=None):
    path = Path(p)
    files_to_add = []

    if path.is_dir():
        pattern = path.rglob('*') if idxDirrs else path.iterdir()
        for obj in pattern:
            if obj.is_file() and obj.suffix.lower() in SUPPORTED_FORMATS:
                files_to_add.append(obj)
    elif path.is_file():
        if path.suffix.lower() in SUPPORTED_FORMATS:
            files_to_add.append(path)

    if not files_to_add:
        return

    # ID плейлиста "Избранное". Убедитесь, что плейлист с ID=0 существует в таблице playlists!
    FAVORITE_PLAYLIST_ID = 0 
    
    con_queue = sqlite3.connect('app.db')
    cursor = con_queue.cursor()
    
    try:
        current_insert_pos = insert_at

        for obj in files_to_add:
            try:
                try:
                    audio = mutagen.File(obj)
                    if audio is None:
                        raise FLACNoHeaderError("Файл не распознан")
                except (FLACNoHeaderError, Exception):
                    print(f"Попытка исправления файла: {obj}")
                    audio = fix_and_load_flac(obj)
                
                if audio:
                    print("Файл успешно открыт:", audio.get('title'))
                # else:
                #     print("Ошибка: файл не удалось открыть даже после исправления.")

                tags = utils.get_audio_tags(audio, obj)
                name = tags["Название"] if tags.get("Название") else obj.name
                author = tags.get("Автор", "Неизвестно")
                miniature = extract_cover_bytes(obj) # Рекомендую в будущем перевести на файловую систему
                file_path_str = str(obj)
                
                # 1. Добавляем трек в общую базу (если его там еще нет). Без передачи ID!
                cursor.execute("""
                    INSERT OR IGNORE INTO tracks (name, author, path, cov_bytes) 
                    VALUES (?, ?, ?, ?)
                """, (name, author, file_path_str, miniature))
                
                # 2. Получаем НАСТОЯЩИЙ ID этого трека из базы (неважно, новый он или уже был)
                cursor.execute("SELECT id FROM tracks WHERE path = ?", (file_path_str,))
                track_id = cursor.fetchone()[0]
                
                # 3. Привязываем трек к плейлисту "Избранное"
                add_track_to_playlist(cursor, FAVORITE_PLAYLIST_ID, track_id, current_insert_pos)
                
                # Если вставляем по индексу, каждый следующий файл встает за предыдущим
                if current_insert_pos is not None:
                    current_insert_pos += 1
                    
            except Exception as e:
                print(f"Ошибка чтения файла {obj}: {e}")
        
        con_queue.commit()
        print(f"Добавлено {len(files_to_add)} файлов в Избранное.")
        
    except Exception as e:
        print(f"Ошибка БД при добавлении в Избранное: {e}")
        con_queue.rollback()
    finally:
        con_queue.close()


#----

def bg_ui_process(page: ft.Page, play_btn):
    """Функция, которая будет крутиться в фоне и генерировать данные"""
    def run():
        global curr_sec, total_sec, is_paused
        while True:
            # Обязательно проверяем, создан ли плеер, чтобы поток не крашился при старте!
            if player:
                # Если плеер играет и ползунок не перетаскивают
                if player.is_playing() and not is_dragging:
                    curr_sec = player.get_time() // 1000
                    total_length = player.get_length() # VLC возвращает миллисекунды, иногда -1 при ошибке
                    total_sec = total_length // 1000 if total_length > 0 else 0
                    
                    # Отправляем словарь с данными в UI-файл в топик "playback_update"
                    page.pubsub.send_all_on_topic("playback_update", {
                        "curr_sec": curr_sec,
                        "total_sec": total_sec
                    })
                
                # Если трек закончился
                elif not player.is_playing() and not is_paused and total_sec > 0 and curr_sec >= (total_sec - 1):
                    con_queue = sqlite3.connect('queue.db')
                    cursor = con_queue.cursor()
                    cursor.execute("SELECT path FROM queue WHERE id = 1")
                    r = cursor.fetchone()
                    if r:
                        cursor.execute("UPDATE queue SET id = id -1")
                        con_queue.commit()
                        con_queue.close()
                        real_path = r[0]
                        curr_sec = 0
                        total_sec = 0
                        load_track(page, real_path, play_btn, 1)
                    else: #все кончилось включая очередь
                        con_queue.commit()
                        con_queue.close()
                        pass
                
            time.sleep(upd_time)
    threading.Thread(target=run, daemon=True).start()