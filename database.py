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
    con_fav = sqlite3.connect('app.db')
    cursor = con_fav.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS "tracks" (
	"id"	INTEGER NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"author"	TEXT,
	"path"	TEXT NOT NULL,
	"cov_bytes"	BLOB,
	"seed"	INTEGER NOT NULL,
	"reps"	INTEGER
    ); ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS "playlists" (
	"pl_id"	INTEGER NOT NULL,
	"pl_name"	TEXT NOT NULL,
	"pl_cover_path"	TEXT,
	PRIMARY KEY("pl_id")
    ); ''')
	
    con_fav.commit()
    con_fav.close()
    print("app.db инициализирована")