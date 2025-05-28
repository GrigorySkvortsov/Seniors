import asyncio
import websockets
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

SERVER_URI = "ws://localhost:6789"


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WebSocket Чат")
        self.root.geometry("900x700")

        self.ws = None
        self.login = ""
        self.tabs = {}
        self.text_areas = {}
        self.unread_tabs = set()
        self.loop = asyncio.new_event_loop()

        threading.Thread(target=self.start_loop, daemon=True).start()

        self.status_label = tk.Label(root, text="Вы не авторизованы", fg="blue")
        self.status_label.pack(pady=(0, 5))

        # Интерфейс
        self.login_entry = tk.Entry(root)
        self.login_entry.pack()
        self.login_entry.insert(0, "Логин")

        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack()
        self.password_entry.insert(0, "Пароль")

        self.register_btn = tk.Button(root, text="Зарегистрироваться", command=self.register)
        self.register_btn.pack(pady=2)

        self.login_btn = tk.Button(root, text="Войти", command=self.login_user)
        self.login_btn.pack(pady=(0, 5))

        self.to_entry = tk.Entry(root)
        self.to_entry.insert(0, "Кому (логин)")

        self.msg_entry = tk.Entry(root)
        self.msg_entry.insert(0, "Введите сообщение")

        self.send_btn = tk.Button(root, text="Отправить", command=self.send_message)

        self.notebook = ttk.Notebook(root)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.logout_btn = tk.Button(root, text="Выйти", command=self.logout)

        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

        self.set_authenticated(False)

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
            self.tabs[user] = frame
            self.text_areas[user] = text_area
            self.log_console("SYSTEM", f"Создана вкладка для чата с {user}")

    def format_timestamp(self, timestamp: str) -> str:
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return ""

    def write_message(self, chat_with, who, message, timestamp=None):
        self.create_chat_tab(chat_with)
        area = self.text_areas[chat_with]
        area.config(state='normal')
        time_str = f"[{self.format_timestamp(timestamp)}] " if timestamp else ""
        area.insert(tk.END, f"{time_str}{who}: {message}\n")
        area.see(tk.END)
        area.config(state='disabled')

        current_tab = self.notebook.tab(self.notebook.select(), "text")
        if chat_with != current_tab and chat_with not in self.unread_tabs:
            self.set_tab_label(chat_with, f"👁 {chat_with}")
            self.unread_tabs.add(chat_with)
            self.log_console("MIGRATE", f"Мигалка добавлена для {chat_with}")

    def clear_all_tabs(self):
        self.log_console("SYSTEM", "Очистка всех вкладок и чатов.")
        for user, frame in list(self.tabs.items()):
            try:
                self.notebook.forget(frame)
            except Exception as e:
                self.log_console("ERROR", f"Не удалось удалить вкладку {user}: {e}")
        self.tabs.clear()
        self.text_areas.clear()
        self.unread_tabs.clear()

    def set_authenticated(self, status: bool):
        if status:
            self.login_entry.pack_forget()
            self.password_entry.pack_forget()
            self.register_btn.pack_forget()
            self.login_btn.pack_forget()

            self.to_entry.pack()
            self.msg_entry.pack()
            self.send_btn.pack()
            self.notebook.pack(fill='both', expand=True)
            self.logout_btn.pack(pady=10, side='bottom')

            self.status_label.config(text=f"Вы вошли как: {self.login}", fg="green")
        else:
            self.to_entry.pack_forget()
            self.msg_entry.pack_forget()
            self.send_btn.pack_forget()
            self.notebook.pack_forget()
            self.logout_btn.pack_forget()

            self.login_entry.pack()
            self.password_entry.pack()
            self.register_btn.pack(pady=2)
            self.login_btn.pack(pady=(0, 5))

            self.status_label.config(text="Вы не авторизованы", fg="blue")

    def on_tab_changed(self, event):
        selected_index = self.notebook.index(self.notebook.select())
        tab_text = self.notebook.tab(selected_index, "text")
        clean_name = tab_text.replace("👁 ", "")
        self.to_entry.delete(0, tk.END)
        self.to_entry.insert(0, clean_name)

        if clean_name in self.unread_tabs:
            self.set_tab_label(clean_name, clean_name)
            self.unread_tabs.remove(clean_name)
            self.log_console("MIGRATE", f"Мигалка снята для {clean_name}")

    def set_tab_label(self, username, label_text):
        if username in self.tabs:
            index = self.notebook.index(self.tabs[username])
            self.notebook.tab(index, text=label_text)

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
                    msg = data["message"]
                    timestamp = data.get("timestamp")
                    self.write_message(sender, sender, msg, timestamp)
                    self.log_console("RECEIVE", f"{sender} → {self.login}: {msg}")
                elif data.get("command") == "chat_history":
                    self.load_history(data.get("history", {}))
                elif "status" in data:
                    self.handle_status(data)
        except websockets.ConnectionClosed:
            self.log_console("SYSTEM", "Соединение с сервером закрыто.")

    def load_history(self, history_dict):
        self.log_console("HISTORY", f"Загружается история чатов ({len(history_dict)} диалогов)...")
        for partner, messages in history_dict.items():
            self.create_chat_tab(partner)
            for msg in messages:
                sender = msg["from"]
                message = msg["message"]
                timestamp = msg.get("timestamp")
                self.write_message(partner, sender, message, timestamp)
        self.log_console("HISTORY", "История успешно загружена.")

    def handle_status(self, data):
        status = data.get("status")
        message = data.get("message", "")
        if status == "registered":
            self.log_console("INFO", f"Пользователь {self.login} зарегистрирован.")
        elif status == "logged_in":
            self.log_console("INFO", f"Пользователь {self.login} вошёл в систему.")
            self.clear_all_tabs()
            self.set_authenticated(True)
            self.send_json({"command": "get_history"})
        elif status == "logged_out":
            self.log_console("INFO", f"Пользователь {self.login} вышел.")
            self.clear_all_tabs()
            self.set_authenticated(False)
            self.login = ""
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
        now = datetime.now().isoformat()
        self.write_message(to_user, self.login, message, now)
        self.log_console("ACTION", f"{self.login} → {to_user}: {message}")

    def logout(self):
        self.send_json({"command": "logout"})
        self.clear_all_tabs()
        self.set_authenticated(False)
        self.log_console("ACTION", f"Пользователь {self.login} вышел из приложения.")
        self.login = ""


# Запуск клиента
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
