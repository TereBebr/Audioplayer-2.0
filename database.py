import sqlite3

def create_queue():
    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS "queue" (
    "id" INTEGER NOT NULL,
	"name"	TEXT NOT NULL,
	"author" TEXT,
	"path"	TEXT NOT NULL,
    "cov_bytes" BLOB
    ) ''')
    #connection.commit()
    #con_queue.close()
    con_queue.close()
    print("queue.db инициализирована")

def pl_app():
    con_app = sqlite3.connect('app.db')
    cursor = con_app.cursor()

    # 1. Таблица треков
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        author TEXT,
        path TEXT NOT NULL,
        cov_bytes BLOB,
        reps INTEGER
    )""")

    # 2. Таблица плейлистов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        cover_path TEXT
    )""")

    # 3. Связующая таблица
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER,
        track_id INTEGER,
        position INTEGER NOT NULL,
        PRIMARY KEY (playlist_id, track_id), -- Автоматически создает индекс
        FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
        FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
    )""")
    # Явное включение поддержки Foreign Keys в SQLite (обязательно!)
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # Избранное
        cursor.execute(
            "INSERT OR IGNORE INTO playlists (name, cover_path) VALUES (?, ?)",("Избранное","storage/playlists_covers/favorite.png"))
    except Exception as e:
        con_app.rollback()
        print(f"Ошибка при создании плейлиста: {e}")
        return -1

    con_app.commit()
    con_app.close()
    print("app.db инициализирована")