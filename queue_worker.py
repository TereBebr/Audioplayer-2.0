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
    src = sources.get(uri)
    if src.is_dir(uri):
        files_to_add = src.expand(uri)
    else:
        files_to_add = [uri]

    with in_progress_lock:
        for new_uri in files_to_add:
            in_progress[new_uri] += 1

    curr_pos = insert_at
    for file_uri in files_to_add:
        tracks_queue.put((file_uri, curr_pos))
        if curr_pos is not None:
            curr_pos += 1

step = 1

def start_queue_worker(page):
    """Фоновый поток: берёт URI из очереди, тянет cover(uri, '50'),
    пишет в БД, шлёт 'cover_ready' с uid строки."""
    global step
    def run():
        processed_count = 0
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
            con_queue.execute("PRAGMA journal_mode=WAL;")
            while True:
                if not sources.server_online():
                    tracks_queue.put((track_uri, item_insert_at)) # Возвращаем в очередь
                    time.sleep(5)
                    continue
                try:
                    track_uri, item_insert_at = tracks_queue.get()
                    src = sources.get(track_uri)
                    tags = src.meta(track_uri)
                    name = tags["Название"]
                    author = tags.get("Автор") or "Неизвестно"
                    if src.is_remote:
                        miniature = cover_worker.request_cover(track_uri)
                    else:
                        miniature = src.cover(track_uri, "50")

                    with db_lock:
                        cursor = con_queue.cursor()
                        if item_insert_at is None: # Вставка в конец
                                cursor.execute("SELECT MAX(id) FROM queue")
                                max_id = cursor.fetchone()[0]
                                target_id = 0 if max_id is None else max_id + 1
                        else: # Вставка по индексу
                            cursor.execute("UPDATE queue SET id = id + 1 WHERE id >= ?", (item_insert_at,))
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
                    if left_to_process > 100:
                        step = 20
                    elif left_to_process > 20:
                        step = 5
                    else:
                        step = 1
                    if processed_count % step == 0 or left_to_process == 0:
                        page.pubsub.send_all_on_topic("queue_progress", 
                            {
                                "status": "loading" if left_to_process > 0 else "done",
                                "left": left_to_process,
                                "processed_session": processed_count
                            }
                        )
                    tracks_queue.task_done()
    threading.Thread(target=run, daemon=True).start()