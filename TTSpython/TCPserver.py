import socket
import threading
import json
import sqlite3


def handle_client(client_socket):
    request = client_socket.recv(4096)
    data = json.loads(request.decode())

    conn = sqlite3.connect("students_db.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS students(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nume TEXT,
                    facultate TEXT,
                    serie TEXT,
                    grupa TEXT
                )""")
                
    c.execute("""CREATE TABLE IF NOT EXISTS series_questions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facultate TEXT,
                    serie TEXT,
                    intrebare TEXT,
                    raspuns TEXT,
                    FOREIGN KEY(facultate) REFERENCES students(facultate),
                    FOREIGN KEY(serie) REFERENCES students(serie)
                )""")
                
    c.execute("""CREATE TABLE IF NOT EXISTS group_questions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facultate TEXT,
                    grupa TEXT,
                    intrebare TEXT,
                    raspuns TEXT,
                    FOREIGN KEY(facultate) REFERENCES students(facultate),
                    FOREIGN KEY(grupa) REFERENCES students(grupa)
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS general_questions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intrebare TEXT,
                    raspuns TEXT
                )""")
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS locatii (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nume TEXT NOT NULL,
            categorie TEXT NOT NULL,
            latitudine REAL NOT NULL,
            longitudine REAL NOT NULL,
            descriere TEXT
        )
    """)
    if(data["type"]=="student"):
        c.execute("INSERT INTO students(nume,facultate, serie, grupa) VALUES (?, ?, ?, ?)",
              (data["nume"], data["facultate"], data["serie"], data["grupa"]))
    elif(data["type"]=="serie"):
        c.execute("INSERT INTO series_questions(facultate,serie, intrebare, raspuns) VALUES (?, ?, ?, ?)",
              (data["facultate"], data["serie"], data["intrebare"], data["raspuns"]))
    elif(data["type"]=="grupa"):
        c.execute("INSERT INTO group_questions(facultate, grupa, intrebare, raspuns) VALUES (?, ?, ?, ?)",
              (data["facultate"], data["grupa"], data["intrebare"], data["raspuns"]))
    elif(data["type"]=="general"):
        c.execute("INSERT INTO general_questions( intrebare, raspuns) VALUES (?, ?)",
              (data["intrebare"], data["raspuns"]))
    elif(data["type"]=="locatii"):
        c.execute("INSERT INTO locatii( nume, categorie,latitudine,longitudine,descriere) VALUES (?, ?,?,?,?)",
              (data["nume"], data["categorie"],data["latitudine"],data["longitudine"],data["descriere"]))
    conn.commit()
    conn.close()

    client_socket.send("Data inserted".encode())
    client_socket.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("0.0.0.0", 9999))
server.listen(5)
print("[+] Listening on port 9999")

while True:
    client, addr = server.accept()
    threading.Thread(target=handle_client, args=(client,)).start()
