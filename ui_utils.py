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
from contextlib import closing
from mutagen.flac import FLACNoHeaderError
import subprocess
import logging
import sources
import queue_worker

logger = logging.getLogger(__name__)

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
start_vol_val = config.getint('Main Settings', 'start_vol_val') # Начальное значение звука

possible_covers = ["cover.jpg", "Cover.jpg", "cover.png", "folder.jpg"]

#Работа с БД ----

# Все соединения открываются через closing(), иначе sqlite3 не освобождает
# файловые дескрипторы: `with sqlite3.connect(...)` управляет только транзакцией.

def db_query_one(db_name, sql, params=()):
    """Читает одну строку. Соединение закрывается всегда."""
    try:
        with closing(sqlite3.connect(db_name, timeout=10.0)) as con:
            return con.execute(sql, params).fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка чтения из {db_name}: {e}")
        return None

def db_query_all(db_name, sql, params=()):
    """Читает все строки. Соединение закрывается всегда."""
    try:
        with closing(sqlite3.connect(db_name, timeout=10.0)) as con:
            return con.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка чтения из {db_name}: {e}")
        return []

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

#Функции проводника ----


def on_item_click(e, rebuild_callback, play_btn_obj): #при клике на объект
        uri = e.control.data
        src = sources.get(uri)
        if src.is_dir(uri):
            rebuild_callback(src.list_dir(uri), uri)
        else:
            tags = src.meta(uri)
            miniature = src.cover(uri, "50")

            try:
                with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
                    with con_queue: # транзакция: commit при успехе, rollback при ошибке
                        con_queue.execute('DELETE FROM queue WHERE id = ?', (0,))
                        con_queue.execute("INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)",
                                          (0, tags["Название"], tags["Автор"], uri, miniature))
            except sqlite3.Error as ex:
                logger.error(f"Ошибка БД при постановке трека в очередь: {ex}")
                return

            load_track(e.page, uri, play_btn_obj, -2)  # было 0
            logger.info(f"файл: {uri}")

def on_accept_drag(e): #Конец перетаскивания
     pass

def open_file_folder(e, uri):
    # «Расположение файла»: у RemoteSource reveal — пустышка, ничего не откроется
    try:
        sources.get(uri).reveal(uri)
    except Exception as ex:
        logger.error(f"Не найдена директория {uri}: {ex}")

def open_file_in_player_explorer(e, uri, rebuild_callback, explorer_mode):
    src = sources.get(uri)
    folder = uri if src.is_dir(uri) else src.parent(uri)
    if not src.is_dir(folder):
        logger.error(f"Не найдена директория {folder}")
        return
    rebuild_callback(src.list_dir(folder), folder)
    if src.is_remote:
        explorer_mode(1)
    else:
        explorer_mode(0)

#строка пути
def on_segment_click(e, target_path, rebuild_callback):
    """Срабатывает при клике на сегмент (TextSpan) пути."""
    src = sources.get(target_path)
    if src.is_dir(target_path):
        rebuild_callback(src.list_dir(target_path), target_path)
    else:
        logger.info(f"{target_path} не существует")


def on_dialog_result(directory_path, rebuild_callback):
    """Срабатывает, когда пользователь выбрал папку в системном окне (всегда локальная)."""
    src = sources.get(directory_path)
    if src.is_dir(directory_path):
        rebuild_callback(src.list_dir(directory_path), directory_path)
    else:
        logger.debug(f"Выбранная папка {directory_path} не существует или недоступна")

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
            r = db_query_one('queue.db', "SELECT path FROM queue WHERE id = 0")
            if r:
                load_track(e.page, r[0], play_btn_obj, -2)
            else:
                logger.info("Нет трека с id = 0, воспроизводить нечего")

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
    is_dragging = False

def vol_slider_event(e, vol_label):
    global start_vol_val
    vol = int(e.control.value)
    # Метку двигаем всегда: раньше при player is None (ничего ещё не играло)
    # ползунок ехал, а число рядом не менялось
    vol_label.value = str(vol)
    vol_label.update()
    # и запоминаем громкость, чтобы плеер создался уже с ней
    start_vol_val = vol
    if player:
        player.audio_set_volume(vol)

#Логика воспроизведение аудио ----

def load_track(page, uri, play_btn_obj, idx): #через проводник
    global player, tags, details, tec_audio_info_num, curr_sec, total_sec, is_paused
    curr_sec = 0
    total_sec = 0

    src = sources.get(uri)
    mrl = src.mrl(uri)

    if player:
        player.stop()
        player.set_mrl(mrl)
        if autoplayswitch == False:
            player.play()
            play_btn_obj.src = "assets/icons/pause_ico_inac.png"
            is_paused = False
        else: 
            play_btn_obj.src = "assets/icons/play_ico_inac.png"
            is_paused = False
        play_btn_obj.update()
    else:
        player = utils.create_player(mrl, start_vol_val)
        time.sleep(0.5)
        #vol_slider.set(self.player.audio_get_volume())
        #vol_label.configure(text=f"{self.player.audio_get_volume()}%")
        player.play()
        is_paused = False
        play_btn_obj.src = "assets/icons/pause_ico_inac.png"
        play_btn_obj.update()
    tags = src.meta(uri)
    details = src.details(uri)
    tags["cover"] = src.cover(uri, "full")
    tags["idx"] = idx
    page.pubsub.send_all_on_topic("tags_update", tags)
    # очистка истории < max_histlen
    try:
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
            with con_queue:
                con_queue.execute('DELETE FROM queue WHERE id < ?', (max_histlen,))
    except sqlite3.Error as ex:
        logger.error(f"Ошибка БД при очистке истории: {ex}")


def play_next_or_pred(e, switch, play_btn_obj): #Если True, то следующий, если False - предыдущий
    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()
    try:
        if switch:
            cursor.execute("SELECT path FROM queue WHERE id = 1")
            r = cursor.fetchone()
            idx = 1
            if r:
                cursor.execute("UPDATE queue SET id = id -1")
        else:
            cursor.execute("SELECT path FROM queue WHERE id = -1")
            r = cursor.fetchone()
            idx = -2  # было 0
            if r:
                cursor.execute("UPDATE queue SET id = id +1")            
        con_queue.commit()
    
    except Exception as ex:
        logger.error(f"Ошибка при переходе трека: {ex}")
        con_queue.rollback()
        return
    finally:
        con_queue.close()
    
    if r:
        real_path = r[0] # Берем строку из кортежа
        # load_track сам сделает Path(real_path).resolve()
        load_track(e.page, real_path, play_btn_obj, idx)
        # e.page.pubsub.send_all_on_topic("queue_advanced", 1 if switch else -1)
    else:
        logger.info("В очереди нет треков для воспроизведения")

def add_queue(uri, insert_at): # <--- Добавили аргумент insert_at
    queue_worker.request_track(uri, insert_at)

def mix_queue(rebuild_queue):
    try:
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con:
            with con:
                rows = con.execute("SELECT rowid, id FROM queue WHERE id > 0;").fetchall()
                if rows:
                    rowids = [row[0] for row in rows]
                    ids = [row[1] for row in rows]
                    random.shuffle(ids)
                    # zip(ids, rowids) создаст пары вида (новый_id, старый_rowid)
                    con.executemany("UPDATE queue SET id = ? WHERE rowid = ?;", zip(ids, rowids))
    except sqlite3.Error as e:
        logger.error(f"Ошибка БД при перемешивании очереди: {e}")
        return
    rebuild_queue()

#----
# Плейлисты ----

def add_track_to_playlist(uri, playlist_id, insert_at=None):
    src = sources.get(uri)
    files_to_add = src.expand(uri) if src.is_dir(uri) else [uri]

    if not files_to_add:
        return

    tracks_data = []
    for track_uri in files_to_add:
        try:
            src = sources.get(track_uri)
            tags = src.meta(track_uri)
            name = tags["Название"]
            author = tags.get("Автор") or "Неизвестно"
            if src.is_remote:
                miniature = None
            else:
                miniature = src.cover(track_uri, "50") # TODO: перевести на файловую систему

            tracks_data.append({
                "path": track_uri,
                "name": name,
                "author": author,
                "cov_bytes": miniature
            })
        except Exception as e:
            logger.error(f"Ошибка чтения файла {track_uri}: {e}")
    if not tracks_data:
        return
    
    try:
        with closing(sqlite3.connect('app.db', timeout=10.0)) as con_app:
            with con_app:
                cursor = con_app.cursor()

                # 1. Резолвим id треков в общей таблице и отсеиваем те, что уже
                #    есть в плейлисте: PRIMARY KEY (playlist_id, track_id) не даст
                #    вставить дубль, а сдвиг позиций под него оставил бы дыру.
                new_track_ids = []
                for track in tracks_data:
                    cursor.execute("SELECT id FROM tracks WHERE path = ?", (track["path"],))
                    row = cursor.fetchone()
                    if row is None:
                        cursor.execute("""
                            INSERT INTO tracks (name, author, path, cov_bytes)
                            VALUES (?, ?, ?, ?)
                        """, (track["name"], track["author"], track["path"], track["cov_bytes"]))
                        track_id = cursor.lastrowid
                    else:
                        track_id = row[0]

                    cursor.execute("SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                                   (playlist_id, track_id))
                    if cursor.fetchone() is None and track_id not in new_track_ids:
                        new_track_ids.append(track_id)

                if not new_track_ids:
                    logger.info(f"Все треки уже есть в плейлисте #{playlist_id}, добавлять нечего.")
                    return

                # 2. Освобождаем место ровно под то количество, что реально вставим
                if insert_at is not None:
                    cursor.execute("""UPDATE playlist_tracks SET position = position + ? WHERE playlist_id = ? AND position >= ? """,
                                   (len(new_track_ids), playlist_id, insert_at))
                    current_position = insert_at
                else:
                    cursor.execute("SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
                    current_position = (cursor.fetchone()[0] or 0) + 1

                # 3. Запись треков
                for track_id in new_track_ids:
                    cursor.execute("""
                        INSERT INTO playlist_tracks (playlist_id, track_id, position)
                        VALUES (?, ?, ?)
                    """, (playlist_id, track_id, current_position))
                    current_position += 1

                logger.info(f"Успешно добавлено {len(new_track_ids)} файлов в плейлист #{playlist_id}.")

    except sqlite3.Error as e:
        logger.error(f"Ошибка БД при добавлении в плейлист: {e}")

def add_playlist_to_queue(playlist_id, insert_at=None):
    # 1. Получаем список треков из основной БД
    tracks = db_query_all(
        'app.db',
        """SELECT t.name, t.author, t.path, t.cov_bytes
           FROM tracks t
           JOIN playlist_tracks pt ON t.id = pt.track_id
           WHERE pt.playlist_id = ?
           ORDER BY pt.position ASC""",
        (playlist_id,)
    )

    if not tracks:
        return

    # Имя, автор и обложка уже лежат в app.db — перечитывать теги не нужно.
    # Для серверных треков это сэкономило по HTTP-запросу на каждый трек плейлиста.
    queue_records = [(name, author, uri, cov_bytes)
                     for name, author, uri, cov_bytes in tracks]

    if not queue_records:
        return

    # 3. Вставляем элементы с учетом нумерации по полю id
    try:
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
            with con_queue:
                cursor = con_queue.cursor()
                num_new_tracks = len(queue_records)

                if insert_at is None:
                    # Обычный добавление в конец: берем MAX(id), если очередь пуста — начинаем с 0
                    cursor.execute("SELECT MAX(id) FROM queue")
                    max_id = cursor.fetchone()[0]
                    start_id = 0 if max_id is None else max_id + 1
                else:
                    start_id = insert_at
                    # Сдвигаем элементы с id >= insert_at на num_new_tracks вперед.
                    cursor.execute("""UPDATE queue SET id = id + ? WHERE id >= ?""",(num_new_tracks, start_id))

                # Подготавливаем кортежи для вставки: (id, name, author, path, cov_bytes)
                records_to_insert = [
                    (start_id + idx, rec[0], rec[1], rec[2], rec[3])
                    for idx, rec in enumerate(queue_records)
                ]

                cursor.executemany(
                    "INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)",
                    records_to_insert
                )
    except sqlite3.Error as e:
        logger.error(f"Ошибка БД при добавлении плейлиста в очередь: {e}")
        return

    logger.info(f"Успешно добавлено {len(records_to_insert)} файлов в очередь.")

def delete_playlist(playlist_id : int):
    try:
        with closing(sqlite3.connect('app.db', timeout=10.0)) as con:
            # PRAGMA должен быть выставлен до начала транзакции
            con.execute("PRAGMA foreign_keys = ON")
            with con:
                # playlist_tracks чистится каскадом по FK, но удаляем явно —
                # на случай, если база создавалась без включённых foreign_keys
                con.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?",(playlist_id,))
                con.execute("DELETE FROM playlists WHERE id = ?",(playlist_id,))
                # треки, не оставшиеся ни в одном плейлисте, больше не нужны
                con.execute("""
                    DELETE FROM tracks
                    WHERE id NOT IN (SELECT track_id FROM playlist_tracks)
                """)
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении плейлиста: {e}")

def delete_playlist_track(track_id: int, playlist_id: int):
    con = sqlite3.connect('app.db')
    cursor = con.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # 1. Узнаем позицию удаляемого трека
        cursor.execute("""
            SELECT position FROM playlist_tracks 
            WHERE playlist_id = ? AND track_id = ?
        """, (playlist_id, track_id))
        
        row = cursor.fetchone()
        if not row:
            return  # Трека и так нет в этом плейлисте

        deleted_pos = row[0]

        # 2. Удаляем связку
        cursor.execute("""
            DELETE FROM playlist_tracks 
            WHERE playlist_id = ? AND track_id = ?
        """, (playlist_id, track_id))

        # 3. Сдвигаем позиции всех последующих треков
        cursor.execute("""
            UPDATE playlist_tracks 
            SET position = position - 1 
            WHERE playlist_id = ? AND position > ?
        """, (playlist_id, deleted_pos))

        # багфикс: если нет в альбомах удаляю из tracks
        cursor.execute("SELECT position FROM playlist_tracks WHERE track_id = ?",(track_id,))
        s = cursor.fetchone()
        if s is None:
            cursor.execute("DELETE FROM tracks WHERE id = ?",(track_id,))
        
        con.commit()
    except Exception as e:
        con.rollback()
        logger.error(f"Ошибка при удалении трека из плейлиста: {e}")
    finally:
        con.close()

def dublicate_queue_track(track_uid: int):
    con = sqlite3.connect("queue.db")
    cursor = con.cursor()
    try:
        cursor.execute("SELECT * FROM queue WHERE uid = ?", (track_uid,))
        r = cursor.fetchone()
        if r:
            cursor.execute("UPDATE queue SET id = id + 1 WHERE id > ?", (r[0],))
            cursor.execute("INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?,?,?,?,?)",(r[0] + 1, r[2],r[3],r[4],r[5]))
            con.commit()
        else:
            logger.error(f"Трек с uid={track_uid} не найден в очереди.")
    except Exception as e:
        con.rollback()
        logger.error(f"Ошибка вызова операции: {e}")
    finally:
        con.close()

def delete_track_from_queue(e, track_uid:int, play_btn_obj):
    """Удаляет трек из очереди.

    Возвращает True, если вместо удаления был выполнен переход на следующий трек
    (удаляли тот, что играет сейчас). В этом случае UI очереди уже обновит
    подписчик tags_update, и вызывать ребилд снаружи не нужно.
    """
    advanced = False
    try:
        with closing(sqlite3.connect("queue.db", timeout=10.0)) as con:
            cursor = con.cursor()
            cursor.execute("SELECT * FROM queue WHERE uid = ?",(track_uid,))
            r = cursor.fetchone()
            if r is None:
                logger.error(f"Трек с uid={track_uid} не найден в очереди.")
                return False
            if r[0] == 0:
                advanced = True
            else:
                with con:
                    con.execute('DELETE FROM queue WHERE uid = ?', (track_uid,))
                    con.execute("UPDATE queue SET id = id - 1 WHERE id > ?", (r[0],))
    except sqlite3.Error as er:
        logger.error(f"Ошибка вызова операции: {er}")
        return False

    # Переход делаем уже после закрытия соединения: load_track внутри
    # play_next_or_pred сам лезет в queue.db
    if advanced:
        play_next_or_pred(e, True, play_btn_obj)
    return advanced


#----

import vlc
def bg_ui_process(page: ft.Page, play_btn):
    """Функция, которая будет крутиться в фоне и генерировать данные"""
    def run():
        global curr_sec, total_sec, is_paused
        track_ended_handled = False
        while True:
            # Обязательно проверяем, создан ли плеер, чтобы поток не крашился при старте!
            if player:
                state = player.get_state()
                # print(state)
                # Если плеер играет и ползунок не перетаскивают
                if player.is_playing() and not is_dragging:
                    curr_sec = player.get_time() // 1000
                    total_length = player.get_length() # VLC возвращает миллисекунды, иногда -1 при ошибке
                    total_sec = total_length // 1000 if total_length > 0 else 0
                    
                    # Отправляем словарь с данными в UI-файл в топик "playback_update"
                    try:
                        page.pubsub.send_all_on_topic("playback_update", {
                            "curr_sec": curr_sec,
                            "total_sec": total_sec
                        })
                    except RuntimeError:
                        break #Сессия закрыта
                    track_ended_handled = False
                
                # Если трек закончился
                # elif not player.is_playing() and not is_paused and total_sec > 0 and curr_sec >= (total_sec - 1):
                elif state == vlc.State.Ended and not track_ended_handled:
                    track_ended_handled = True
                    r = None

                    try:
                        # 1. Открываем соединение с таймаутом ожидания блокировки.
                        # closing() обязателен: без него соединение остаётся открытым
                        # на каждом автопереходе и WAL растёт всю сессию.
                        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
                            con_queue.execute("PRAGMA journal_mode=WAL;")
                            with con_queue: # транзакция
                                cursor = con_queue.cursor()

                                # 2. Получаем текущий трек
                                cursor.execute("SELECT path FROM queue WHERE id = 1")
                                r = cursor.fetchone()

                                if r:
                                    # Сдвигаем очередь
                                    cursor.execute("UPDATE queue SET id = id - 1")
                                else:
                                    # Если id = 1 не найден, проверяем, есть ли другие треки
                                    cursor.execute("SELECT MAX(id) FROM queue")
                                    max_id_row = cursor.fetchone()

                                    if max_id_row and max_id_row[0] and max_id_row[0] > 0:
                                        cursor.execute("UPDATE queue SET id = id - 1 WHERE id > 1")

                    except Exception as ex:
                        logger.error(f"Ошибка при авто-переходе: {ex}")
                        r = None

                    # 3. Работа с интерфейсом/VLC происходит ПОСЛЕ закрытия соединения с БД
                    if r:
                        real_path = r[0]
                        curr_sec = 0
                        total_sec = 0
                        load_track(page, real_path, play_btn, 1)
                        page.pubsub.send_all_on_topic("queue_advanced", 1)
                        track_ended_handled = False
                
            time.sleep(upd_time)
    threading.Thread(target=run, daemon=True).start()