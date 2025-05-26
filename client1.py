import asyncio
import websockets
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
from datetime import datetime

SERVER_URI = "ws://localhost:6789"


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WebSocket Чат")
        self.ws = None
        self.login = ""

        self.tabs = {}
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_loop, daemon=True).start()

        # Интерфейс
        self.login_entry = tk.Entry(root)
        self.login_entry.pack()
        self.login_entry.insert(0, "Логин")

        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack()
        self.password_entry.insert(0, "Пароль")

        tk.Button(root, text="Зарегистрироваться", command=self.register).pack()
        tk.Button(root, text="Войти", command=self.login_user).pack()

        self.to_entry = tk.Entry(root)
        self.to_entry.pack()
        self.to_entry.insert(0, "Кому (логин)")
        self.msg_entry = tk.Entry(root)
        self.msg_entry.pack()
        self.msg_entry.insert(0, "Введите сообщение")

        tk.Button(root, text="Отправить", command=self.send_message).pack()
        tk.Button(root, text="Выйти", command=self.logout).pack()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)

        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def log_console(self, tag, message):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{tag}] {now} | {message}")

    def create_chat_tab(self, user):
        if user not in self.tabs:
            frame = ttk.Frame(self.notebook)
            text_area = scrolledtext.ScrolledText(frame, state='disabled', width=60, height=20)
            text_area.pack(expand=True, fill='both')
            self.notebook.add(frame, text=user)
            self.tabs[user] = text_area
            self.log_console("SYSTEM", f"Создана вкладка для чата с {user}")

    def write_message(self, chat_with, who, message):
        self.create_chat_tab(chat_with)
        area = self.tabs[chat_with]
        area.config(state='normal')
        area.insert(tk.END, f"{who}: {message}\n")
        area.see(tk.END)
        area.config(state='disabled')

    async def connect(self):
        try:
            self.ws = await websockets.connect(SERVER_URI)
            self.log_console("SYSTEM", "Соединение с сервером установлено.")
            asyncio.create_task(self.listen())
        except Exception as e:
            self.log_console("ERROR", f"Не удалось подключиться к серверу: {e}")

    async def listen(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                if "from" in data and "message" in data:
                    sender = data["from"]
                    self.write_message(sender, sender, data["message"])
                    self.log_console("RECEIVE", f"{sender} → {self.login}: {data['message']}")
                elif "status" in data:
                    self.handle_status(data)
        except websockets.ConnectionClosed:
            self.log_console("SYSTEM", "Соединение с сервером закрыто.")

    def handle_status(self, data):
        status = data.get("status")
        message = data.get("message", "")
        if status == "registered":
            self.log_console("INFO", f"Пользователь {self.login} зарегистрирован.")
        elif status == "logged_in":
            self.log_console("INFO", f"Пользователь {self.login} вошёл в систему.")
        elif status == "logged_out":
            self.log_console("INFO", f"Пользователь {self.login} вышел.")
        elif status == "sent":
            self.log_console("INFO", "Сообщение отправлено.")
        elif status == "error":
            self.log_console("ERROR", f"Ошибка: {message}")
        else:
            self.log_console("INFO", f"Ответ от сервера: {data}")

    def send_json(self, payload):
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(payload)), self.loop)
        else:
            self.log_console("ERROR", "Нет подключения к серверу.")

    def register(self):
        login = self.login_entry.get()
        password = self.password_entry.get()
        self.login = login
        self.send_json({
            "command": "register",
            "login": login,
            "password": password
        })
        self.log_console("ACTION", f"Отправлена регистрация пользователя {login}.")

    def login_user(self):
        login = self.login_entry.get()
        password = self.password_entry.get()
        self.login = login
        self.send_json({
            "command": "login",
            "login": login,
            "password": password
        })
        self.log_console("ACTION", f"Попытка входа пользователя {login}.")

    def send_message(self):
        to_user = self.to_entry.get()
        message = self.msg_entry.get()
        if not to_user or not message:
            messagebox.showwarning("Ошибка", "Введите логин получателя и сообщение.")
            return
        self.send_json({
            "command": "send_message",
            "to": to_user,
            "message": message
        })
        self.write_message(to_user, self.login, message)
        self.log_console("ACTION", f"{self.login} → {to_user}: {message}")

    def logout(self):
        self.send_json({"command": "logout"})
        self.log_console("ACTION", f"Пользователь {self.login} вышел.")


# Запуск клиента
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
