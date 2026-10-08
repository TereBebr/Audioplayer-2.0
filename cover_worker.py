import threading
import queue
import sqlite3
from contextlib import closing
import sources
import time
import logging

logger = logging.getLogger(__name__)

cover_queue = queue.Queue()
in_progress = set()
in_progress_lock = threading.Lock()

no_cover = set()

def request_cover(uri):
    """Поставить обложку в очередь на дозагрузку. Вызывается из отрисовки строки."""
    if uri in no_cover:
        return
    with in_progress_lock:
        if uri in in_progress:
            return
        in_progress.add(uri)
    cover_queue.put((uri))

def start_cover_worker(page):
    """Фоновый поток: берёт URI из очереди, тянет cover(uri, '50'),
    пишет в БД, шлёт 'cover_ready' с uid строки."""
    def run():
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue, closing(sqlite3.connect('app.db', timeout=10.0)) as con_app:
            con_queue.execute("PRAGMA journal_mode=WAL;")
            con_app.execute("PRAGMA journal_mode=WAL;")
            while True:
                uri = cover_queue.get()
                try:
                    if sources.server_online():
                        src = sources.get(uri)
                        miniature = src.cover(uri, "50")
                        if miniature is None:
                            # У трека нет обложки. Запоминаем, чтобы не просить снова
                            # при каждой перерисовке строки, и берём следующий из очереди.
                            no_cover.add(uri)
                            continue
                        with con_queue: # транзакция
                            cursor = con_queue.cursor()
                            cursor.execute("UPDATE queue SET cov_bytes = ? WHERE path = ?",(miniature, uri))
                        with con_app:
                            cursor = con_app.cursor()
                            cursor.execute("UPDATE tracks SET cov_bytes = ? WHERE path = ?", (miniature, uri))

                        # left говорит UI, когда можно перерисовать список:
                        # на каждой обложке делать это слишком дорого
                        page.pubsub.send_all_on_topic(
                            "cover_ready",
                            {"uri": uri, "cov": miniature, "left": cover_queue.qsize()})
                    else:
                        # Сервер не отвечает — копить заявки бессмысленно, сливаем очередь
                        while not cover_queue.empty():
                            try:
                                dump_uri = cover_queue.get_nowait()
                                with in_progress_lock:
                                    in_progress.discard(dump_uri)
                            except queue.Empty:
                                break
                        time.sleep(1)   # пауза ПОСЛЕ слива, а не на каждом элементе
                except Exception as e:
                    logger.error(f"Ошибка загрузки обложки {uri}: {e}")
                finally:
                    with in_progress_lock:
                        in_progress.discard(uri)
    threading.Thread(target=run, daemon=True).start()