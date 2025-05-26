import asyncio
import websockets
import json
import sqlite3
from datetime import datetime

# Активные подключения
USERS = {}

# Инициализация SQLite
conn = sqlite3.connect('chat.db', check_same_thread=False)
cursor = conn.cursor()

# Таблицы
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE,
    password TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS AuthLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT,
    event TEXT,
    timestamp TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ChatLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    receiver TEXT,
    message TEXT,
    timestamp TEXT
)
''')
conn.commit()

# Логгеры
def log_auth(login, event):
    ts = str(datetime.now())
    print(f"[AUTH] {event.upper()} | Пользователь: {login} | Время: {ts}")
    cursor.execute('INSERT INTO AuthLog (login, event, timestamp) VALUES (?, ?, ?)', (login, event, ts))
    conn.commit()

def log_chat(sender, receiver, message):
    ts = str(datetime.now())
    print(f"[CHAT] {sender} -> {receiver} | Сообщение: {message} | Время: {ts}")
    cursor.execute('INSERT INTO ChatLog (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)', (sender, receiver, message, ts))
    conn.commit()

# Основной обработчик клиента
async def handle_client(websocket):
    user = None
    try:
        async for message in websocket:
            data = json.loads(message)
            command = data.get("command")
            print(f"[RECEIVED] Команда: {command} | Данные: {data}")

            if command == "register":
                login = data["login"]
                password = data["password"]
                try:
                    cursor.execute('INSERT INTO Users (login, password) VALUES (?, ?)', (login, password))
                    conn.commit()
                    await websocket.send(json.dumps({"status": "registered"}))
                    log_auth(login, "register")
                except sqlite3.IntegrityError:
                    await websocket.send(json.dumps({"status": "error", "message": "Login already exists"}))
                    print(f"[ERROR] Регистрация не удалась: login '{login}' уже существует")

            elif command == "login":
                login = data["login"]
                password = data["password"]
                cursor.execute('SELECT * FROM Users WHERE login=? AND password=?', (login, password))
                if cursor.fetchone():
                    USERS[login] = websocket
                    user = login
                    await websocket.send(json.dumps({"status": "logged_in"}))
                    log_auth(login, "login")
                else:
                    await websocket.send(json.dumps({"status": "error", "message": "Invalid credentials"}))
                    print(f"[ERROR] Ошибка входа: login '{login}' не найден или неправильный пароль")

            elif command == "logout":
                if user:
                    USERS.pop(user, None)
                    log_auth(user, "logout")
                    await websocket.send(json.dumps({"status": "logged_out"}))
                    print(f"[INFO] Пользователь {user} вышел из системы")
                    user = None

            elif command == "send_message":
                if not user:
                    await websocket.send(json.dumps({"status": "error", "message": "Unauthorized"}))
                    print(f"[ERROR] Невозможно отправить сообщение: пользователь не авторизован")
                    continue

                receiver = data["to"]
                msg = data["message"]
                log_chat(user, receiver, msg)
                if receiver in USERS:
                    await USERS[receiver].send(json.dumps({"from": user, "message": msg}))
                    await websocket.send(json.dumps({"status": "sent"}))
                    print(f"[INFO] Сообщение от {user} к {receiver} доставлено")
                else:
                    await websocket.send(json.dumps({"status": "error", "message": "Receiver not online"}))
                    print(f"[WARNING] Получатель {receiver} не в сети")

            elif command == "get_history":
                if not user:
                    await websocket.send(json.dumps({"status": "error", "message": "Not authorized"}))
                    continue

                cursor.execute('''
                    SELECT sender, receiver, message, timestamp FROM ChatLog
                    WHERE sender = ? OR receiver = ?
                    ORDER BY timestamp
                ''', (user, user))
                rows = cursor.fetchall()

                history = {}
                for sender, receiver, message, timestamp in rows:
                    other = receiver if sender == user else sender
                    history.setdefault(other, []).append({
                        "from": sender,
                        "message": message,
                        "timestamp": timestamp
                    })

                await websocket.send(json.dumps({
                    "command": "chat_history",
                    "history": history
                }))

    except websockets.exceptions.ConnectionClosed:
        print(f"[DISCONNECT] Клиент отключился: {user}")
        if user:
            USERS.pop(user, None)
            log_auth(user, "disconnected")

# Запуск сервера
async def main():
    print("[START] WebSocket-сервер запущен на ws://localhost:6789")
    async with websockets.serve(handle_client, "localhost", 6789):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
