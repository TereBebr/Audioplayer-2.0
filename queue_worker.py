import threading
import queue
import sqlite3
from contextlib import closing
import sources
import time
import logging
from collections import Counter

logger = logging.getLogger(__name__)

tracks_queue = queue.Queue()
in_progress = Counter()
in_progress_lock = threading.Lock()
db_lock = threading.Lock()

PROGRESS_SEC = 1.0   # прогресс (и перерисовка очереди) не чаще раза в столько секунд

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
    """Фоновый поток: берёт URI из очереди, читает теги, вставляет строку
    в queue.db, шлёт 'queue_progress' (и 'queue_head_changed' для id 0)."""
    def run():
        processed_count = 0
        last_sent = [0.0]
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue:
            con_queue.execute("PRAGMA journal_mode=WAL;")
            # Коммит на каждый трек, но без fsync: в WAL с NORMAL база не бьётся,
            # при отключении питания теряются только последние вставки. С FULL
            # большой альбом вставлялся секундами
            con_queue.execute("PRAGMA synchronous=NORMAL;")
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
                    if tags.get("_stub"):
                        logger.warning(f"Пропущен {track_uri}: мета недоступна")
                        continue
                    name = tags["Название"]
                    author = tags.get("Автор") or "Неизвестно"
                    # Обложку здесь не тянем: на 1000 треков это 1000 HTTP-запросов
                    # (или разборов картинки), а видно из них штук 15. Миниатюру
                    # попросит сама строка очереди, когда появится на экране
                    # (build_queue_cell -> cover_worker.request_cover)

                    with db_lock: # Вставка в конец
                        cursor = con_queue.cursor() 
                        if item_insert_at is None:
                            cursor.execute("SELECT COALESCE(MAX(id), -1) + 1 FROM queue")
                            target_id = cursor.fetchone()[0]
                        else: # Вставка по индексу
                            target_id = item_insert_at
                        cursor.execute(
                            "INSERT INTO queue (id, name, author, path, cov_bytes) VALUES (?, ?, ?, ?, NULL)",
                            (target_id, name, author, track_uri))
                        con_queue.commit()
                    if target_id == 0:
                        # трек встал на место играющего — UI должен его загрузить. Раньше
                        # это делал сам обработчик drop сразу после add_queue, но вставка
                        # асинхронная: в тот момент на id 0 было пусто или старый трек
                        page.pubsub.send_all_on_topic("queue_head_changed", {"path": track_uri})

                except Exception as e:
                    logger.error(f"Ошибка загрузки {track_uri}: {e}")
                finally:
                    processed_count += 1
                    with in_progress_lock:
                        in_progress[track_uri] -= 1
                        if in_progress[track_uri] <= 0:
                            del in_progress[track_uri]
                        left_to_process = sum(in_progress.values())
                    # Не чаще раза в PROGRESS_SEC — каждое сообщение перерисовывает
                    # очередь. Последнее сообщение (left == 0) шлём всегда.
                    now = time.time()
                    due = (now - last_sent[0] >= PROGRESS_SEC) or left_to_process == 0
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