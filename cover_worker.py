import threading
import queue
import sqlite3
from contextlib import closing
import sources
import logging

logger = logging.getLogger(__name__)

# LIFO: первыми грузим обложки строк, которые попросили последними, — то есть
# те, что на экране сейчас, а не пролистанные
cover_queue = queue.LifoQueue()
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
    пишет в queue.db и app.db, шлёт 'cover_ready' с uri и байтами."""
    def run():
        with closing(sqlite3.connect('queue.db', timeout=10.0)) as con_queue, closing(sqlite3.connect('app.db', timeout=10.0)) as con_app:
            con_queue.execute("PRAGMA journal_mode=WAL;")
            con_app.execute("PRAGMA journal_mode=WAL;")
            while True:
                uri = cover_queue.get()
                try:
                    if sources.is_remote(uri) and not sources.server_online():
                        # Сервер не отвечает — заявку выбрасываем: строка, если она
                        # ещё на экране, попросит обложку снова при перерисовке
                        continue
                    src = sources.get(uri)
                    miniature = src.cover(uri, "50")
                    if miniature is None:
                        # У трека нет обложки. Запоминаем, чтобы не просить снова
                        # при каждой перерисовке строки, и берём следующий из очереди.
                        # Серверный cover() отдаёт None и на обрыв связи — такой не запоминаем
                        if not sources.is_remote(uri) or sources.server_online():
                            no_cover.add(uri)
                        continue
                    with con_queue: # транзакция
                        cursor = con_queue.cursor()
                        cursor.execute("UPDATE queue SET cov_bytes = ? WHERE path = ?",(miniature, uri))
                    with con_app:
                        cursor = con_app.cursor()
                        cursor.execute("UPDATE tracks SET cov_bytes = ? WHERE path = ?", (miniature, uri))

                    # UI подставит картинку в видимые строки с этим uri, без перерисовки списка
                    page.pubsub.send_all_on_topic("cover_ready", {"uri": uri, "cov": miniature})
                except Exception as e:
                    logger.error(f"Ошибка загрузки обложки {uri}: {e}")
                finally:
                    with in_progress_lock:
                        in_progress.discard(uri)
    threading.Thread(target=run, daemon=True).start()