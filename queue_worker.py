import threading
import queue
import sqlite3
from contextlib import closing
import sources
import time
import logging
from collections import Counter
import cover_worker

logger = logging.getLogger(__name__)

tracks_queue = queue.Queue()
in_progress = Counter()
in_progress_lock = threading.Lock()
db_lock = threading.Lock()

def request_track(uri, insert_at=None):
    """Поставить трек в очередь на дозагрузку"""
    try:
        src = sources.get(uri)
        if src.is_dir(uri):
            files_to_add = src.expand(uri)
        else:
            files_to_add = [uri]
    except Exception as e:
        logger.error(f"Не удалось прочитать URI {uri}: {e}")
        return

    if not files_to_add:
        return

    with in_progress_lock:
        for new_uri in files_to_add:
            in_progress[new_uri] += 1

    if insert_at is not None:
        shift_count = len(files_to_add)
        with db_lock:
            with closing(sqlite3.connect('queue.db', timeout=10.0)) as con:
                con.execute(
                    "UPDATE queue SET id = id + ? WHERE id >= ?", 
                    (shift_count, insert_at)
                )
                con.commit()

    curr_pos = insert_at
    for file_uri in files_to_add:
        tracks_queue.put((file_uri, curr_pos))
        if curr_pos is not None:
            curr_pos += 1

def start_queue_worker(page):
    """Фоновый поток: берёт URI из очереди, тянет cover(uri, '50'),
    пишет в БД, шлёт 'cover_ready' с uid строки."""
    def run():
        processed_count = 0
        last_sent = [0.0]
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
            con_queue.execute("PRAGMA journal_mode=WAL;")
            while True:
                # get() ДО любых проверок: на первой итерации track_uri ещё не существует,
                # и обращение к нему убивало поток молча — NameError вне try/except
                track_uri, item_insert_at = tracks_queue.get()

                # Сервер нужен только серверным трекам; локальные добавляем всегда
                if sources.is_remote(track_uri) and not sources.server_online():
                    tracks_queue.put((track_uri, item_insert_at))  # вернуть в очередь
                    tracks_queue.task_done()
                    time.sleep(5)
                    continue

                try:
                    src = sources.get(track_uri)
                    tags = src.meta(track_uri)
                    name = tags["Название"]
                    author = tags.get("Автор") or "Неизвестно"
                    if src.is_remote:
                        # request_cover ничего не возвращает: обложку дотянет
                        # cover_worker и сам впишет её в queue.db
                        miniature = None
                        cover_worker.request_cover(track_uri)
                    else:
                        miniature = src.cover(track_uri, "50")

                    with db_lock: # Вставка в конец
                        cursor = con_queue.cursor() 
                        if item_insert_at is None:
                            cursor.execute("SELECT COALESCE(MAX(id), -1) + 1 FROM queue")
                            target_id = cursor.fetchone()[0]
                        else: # Вставка по индексу
                            target_id = item_insert_at
                        cursor.execute(
                            "INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, ?)",
                            (target_id, name, author, track_uri, miniature))
                        con_queue.commit()

                except Exception as e:
                    logger.error(f"Ошибка загрузки {track_uri}: {e}")
                finally:
                    processed_count += 1
                    with in_progress_lock:
                        in_progress[track_uri] -= 1
                        if in_progress[track_uri] <= 0:
                            del in_progress[track_uri]
                        left_to_process = sum(in_progress.values())
                    # Не чаще раза в 0.3 с — иначе на тысяче треков UI захлебнётся
                    # перерисовками. Последнее сообщение (left == 0) шлём всегда.
                    now = time.time()
                    due = (now - last_sent[0] >= 0.3) or left_to_process == 0
                    if due:
                        last_sent[0] = now
                        page.pubsub.send_all_on_topic("queue_progress", 
                            {
                                "status": "loading" if left_to_process > 0 else "done",
                                "left": left_to_process,
                                "processed_session": processed_count
                            }
                        )
                        if left_to_process == 0:
                            processed_count = 0
                    tracks_queue.task_done()
    threading.Thread(target=run, daemon=True).start()