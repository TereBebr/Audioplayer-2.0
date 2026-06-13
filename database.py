import sqlite3

def create_queue():
    con_queue = sqlite3.connect('queue.db')
    cursor = con_queue.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS "queue" (
    "id" INTEGER NOT NULL,
	"name"	TEXT NOT NULL,
	"author" TEXT,
	"cov_bites"	TEXT,
	"path"	TEXT NOT NULL
    ) ''')
    #connection.commit()
    #con_queue.close()
    con_queue.close()
    print("queue.db инициализорована")
    
def create_plfav():
    con_fav = sqlite3.connect('favoritepl.db')
    cursor = con_fav.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS "favorite" (
	"name"	TEXT NOT NULL,
	"adress"	TEXT NOT NULL,
	"path"	TEXT NOT NULL,
	"seed"	INTEGER NOT NULL,
	"reps" INTEGER

	) ''')
	
    con_fav.commit()
    con_fav.close()
    print("favoritepl.db инициализорована")