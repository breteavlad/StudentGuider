import tkinter as tk
from tkinter import messagebox
import socket
import json
import sqlite3

# Raspberry Pi IP and port
PI_HOST = "192.168.1.108"
PI_PORT = 9999
DB_FILE="students_db.db"


def sendStudentName():
    win=tk.Toplevel(root)
    win.title("New student")

    tk.Label(win,text="Nume student: ").grid(column=0,row=0)
    nume=tk.Entry(win)
    nume.grid(column=2,row=0)
    
    tk.Label(win,text="Grupa: ").grid(column=0,row=1)
    grupa=tk.Entry(win)
    grupa.grid(column=2,row=1)
    
    tk.Label(win,text="Serie: ").grid(column=0,row=2)
    serie=tk.Entry(win)
    serie.grid(column=2,row=2)
    
    tk.Label(win,text="Facultate: ").grid(column=0,row=3)
    facultate=tk.Entry(win)
    facultate.grid(column=2,row=3)
    
    def save():
        data={
            "type": "student",
            "nume": nume.get(),
            "grupa": grupa.get(),
            "serie": serie.get(),
            "facultate": facultate.get()
        }
        try:
            client=socket.socket(socket.AF_INET,socket.SOCK_STREAM);
            client.connect((PI_HOST,PI_PORT))
            client.send(json.dumps(data).encode())
            response=client.recv(4096)
            messagebox.showinfo("Success", response)
            win.destroy()
        except Exception as e:
            messagebox.showinfo("Error", e)
    
    tk.Button(win,text="Save",command=save).grid(column=2,row=4)

    return 0
def sendSeriesQuestion():
    win=tk.Toplevel(root)
    win.title("Intrebare serie")

    tk.Label(win,text="Facultate: ").grid(column=0,row=0)
    facultate=tk.Entry(win)
    facultate.grid(column=2,row=0)
    
    tk.Label(win,text="Serie: ").grid(column=0,row=1)
    serie=tk.Entry(win)
    serie.grid(column=2,row=1)
    
    tk.Label(win,text="Intrebare: ").grid(column=0,row=2)
    intrebare=tk.Entry(win)
    intrebare.grid(column=2,row=2)
    
    tk.Label(win,text="Raspuns: ").grid(column=0,row=3)
    raspuns=tk.Entry(win)
    raspuns.grid(column=2,row=3)
    
    def save():
        data={
            "type": "serie",
            "facultate": facultate.get(),
            "serie": serie.get(),
            "intrebare": intrebare.get(),
            "raspuns":raspuns.get()
        }
        try:
            client=socket.socket(socket.AF_INET,socket.SOCK_STREAM);
            client.connect((PI_HOST,PI_PORT))
            client.send(json.dumps(data).encode())
            response=client.recv(4096)
            messagebox.showinfo("Success", response)
            win.destroy()
        except Exception as e:
            messagebox.showinfo("Error", e)
    
    tk.Button(win,text="Save",command=save).grid(column=2,row=4)

    return 0
def sendGroupQuestion():
    win=tk.Toplevel(root)
    win.title("Intrebare grupa")

    tk.Label(win,text="Facultate: ").grid(column=0,row=0)
    facultate=tk.Entry(win)
    facultate.grid(column=2,row=0)
    
    tk.Label(win,text="Grupa: ").grid(column=0,row=1)
    grupa=tk.Entry(win)
    grupa.grid(column=2,row=1)
    
    tk.Label(win,text="Intrebare: ").grid(column=0,row=2)
    intrebare=tk.Entry(win)
    intrebare.grid(column=2,row=2)
    
    tk.Label(win,text="Raspuns: ").grid(column=0,row=3)
    raspuns=tk.Entry(win)
    raspuns.grid(column=2,row=3)
    
    def save():
        data={
            "type": "grupa",
            "facultate": facultate.get(),
            "grupa": grupa.get(),
            "intrebare": intrebare.get(),
            "raspuns":raspuns.get()
        }
        try:
            client=socket.socket(socket.AF_INET,socket.SOCK_STREAM);
            client.connect((PI_HOST,PI_PORT))
            client.send(json.dumps(data).encode())
            response=client.recv(4096)
            messagebox.showinfo("Success", response)
            win.destroy()
        except Exception as e:
            messagebox.showinfo("Error", e)
    
    tk.Button(win,text="Save",command=save).grid(column=2,row=4)

    return 0
def sendGeneralQuestion():
    win=tk.Toplevel(root)
    win.title("Intrebare serie")
    
    tk.Label(win,text="Intrebare: ").grid(column=0,row=2)
    intrebare=tk.Entry(win)
    intrebare.grid(column=2,row=2)
    
    tk.Label(win,text="Raspuns: ").grid(column=0,row=3)
    raspuns=tk.Entry(win)
    raspuns.grid(column=2,row=3)
    
    def save():
        data={
            "type": "general",
            "intrebare": intrebare.get(),
            "raspuns":raspuns.get()
        }
        try:
            client=socket.socket(socket.AF_INET,socket.SOCK_STREAM);
            client.connect((PI_HOST,PI_PORT))
            client.send(json.dumps(data).encode())
            response=client.recv(4096)
            messagebox.showinfo("Success", response)
            win.destroy()
        except Exception as e:
            messagebox.showinfo("Error", e)
    
    tk.Button(win,text="Save",command=save).grid(column=2,row=4)

    return 0



root=tk.Tk()

tk.Button(root,text="New Student",command=sendStudentName).grid(column=1, row=0)
tk.Button(root,text="Send Group Question",command=sendGroupQuestion).grid(column=1,row=1)
tk.Button(root,text="Send Series Question",command=sendSeriesQuestion).grid(column=1,row=2)
tk.Button(root,text="Send General Question",command=sendGeneralQuestion).grid(column=1,row=3)


root.mainloop()


