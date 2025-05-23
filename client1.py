import asyncio
import websockets
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox

SERVER_URI = "ws://localhost:6789"


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WebSocket Чат")
        self.ws = None
        self.login = ""

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_loop, daemon=True).start()

        # Интерфейс
        tk.Label(root, text="Логин:").pack()
        self.login_entry = tk.Entry(root)
        self.login_entry.pack()

        tk.Label(root, text="Пароль:").pack()
        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack()

        self.register_btn = tk.Button(root, text="Зарегистрироваться", command=self.register)
        self.register_btn.pack()

        self.login_btn = tk.Button(root, text="Войти", command=self.login_user)
        self.login_btn.pack()

        tk.Label(root, text="Кому (login):").pack()
        self.to_entry = tk.Entry(root)
        self.to_entry.pack()

        tk.Label(root, text="Сообщение:").pack()
        self.msg_entry = tk.Entry(root)
        self.msg_entry.pack()

        self.send_btn = tk.Button(root, text="Отправить", command=self.send_message)
        self.send_btn.pack()

        self.chat_area = scrolledtext.ScrolledText(root, state='disabled', width=60, height=20)
        self.chat_area.pack()

        self.logout_btn = tk.Button(root, text="Выйти", command=self.logout)
        self.logout_btn.pack()

        # Подключение к серверу
        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def log_local(self, text):
        print(f"[CLIENT] {text}")
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, text + "\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    async def connect(self):
        try:
            self.ws = await websockets.connect(SERVER_URI)
            self.log_local("Подключено к серверу.")
            asyncio.create_task(self.listen())
        except Exception as e:
            self.log_local(f"Ошибка подключения: {e}")

    async def listen(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                self.log_local(f"Получено: {data}")
        except websockets.ConnectionClosed:
            self.log_local("Соединение с сервером закрыто.")

    def send_json(self, payload):
        if self.ws:
            self.log_local(f"Отправка: {payload}")
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(payload)), self.loop)
        else:
            self.log_local("Нет подключения к серверу.")

    def register(self):
        login = self.login_entry.get()
        password = self.password_entry.get()
        self.login = login
        self.send_json({
            "command": "register",
            "login": login,
            "password": password
        })

    def login_user(self):
        login = self.login_entry.get()
        password = self.password_entry.get()
        self.login = login
        self.send_json({
            "command": "login",
            "login": login,
            "password": password
        })

    def send_message(self):
        to_user = self.to_entry.get()
        message = self.msg_entry.get()
        if not to_user or not message:
            messagebox.showwarning("Ошибка", "Введите получателя и сообщение.")
            return
        self.send_json({
            "command": "send_message",
            "to": to_user,
            "message": message
        })

    def logout(self):
        self.send_json({"command": "logout"})


# Запуск клиента
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
