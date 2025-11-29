import telebot
from telebot import types
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GENESIS_ADMIN_ID = int(os.getenv("GENESIS_ADMIN_ID"))

if not all([BOT_TOKEN, GENESIS_ADMIN_ID]):
    raise ValueError("Не все необходимые переменные окружения установлены в .env файле")

bot = telebot.TeleBot(BOT_TOKEN)

DB_NAME = "tasks_bot.db"

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица задач
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_text TEXT NOT NULL,
            is_done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица администраторов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Получение соединения с базой данных"""
    return sqlite3.connect(DB_NAME)


def ensure_user_exists(user_id, username=None, first_name=None, last_name=None):
    """Создает запись пользователя если не существует"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
        (user_id, username, first_name, last_name)
    )
    
    conn.commit()
    conn.close()

def get_user_tasks(user_id):
    """Получение задач пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT task_id, task_text, is_done FROM tasks WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    )
    
    tasks = cursor.fetchall()
    conn.close()
    
    return [{"id": task[0], "text": task[1], "done": bool(task[2])} for task in tasks]

def add_user_task(user_id, task_text):
    """Добавление новой задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO tasks (user_id, task_text) VALUES (?, ?)',
        (user_id, task_text)
    )
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return task_id

def update_task_status(task_id, is_done):
    """Обновление статуса задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE tasks SET is_done = ? WHERE task_id = ?',
        (is_done, task_id)
    )
    
    conn.commit()
    conn.close()

def delete_task(task_id):
    """Удаление задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    
    conn.commit()
    conn.close()

def is_admin(user_id):
    """Проверка является ли пользователь администратором"""
    if user_id == GENESIS_ADMIN_ID:
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def add_admin(user_id, added_by=None):
    """Добавление администратора"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT OR REPLACE INTO admins (user_id, added_by) VALUES (?, ?)',
        (user_id, added_by)
    )
    
    conn.commit()
    conn.close()

def get_all_users():
    """Получение списка всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, first_name, last_name FROM users')
    users = cursor.fetchall()
    conn.close()
    
    return [{"id": user[0], "username": user[1], "first_name": user[2], "last_name": user[3]} for user in users]

def get_user_tasks_by_id(user_id):
    """Получение задач конкретного пользователя (для админа)"""
    return get_user_tasks(user_id)


def main_menu(user_id):
    kb = types.InlineKeyboardMarkup()

    my_tasks = types.InlineKeyboardButton("📋 Мои задачи", callback_data="my_tasks")
    add_task = types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")

    kb.add(my_tasks)
    kb.add(add_task)

    if is_admin(user_id):
        admin_panel = types.InlineKeyboardButton("🛠 Админ-панель", callback_data="admin_panel")
        kb.add(admin_panel)

    if user_id == GENESIS_ADMIN_ID:
        genesis_btn = types.InlineKeyboardButton("👑 Назначить админа", callback_data="genesis_add_admin")
        kb.add(genesis_btn)

    return kb

@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    first_name = msg.from_user.first_name
    last_name = msg.from_user.last_name

    ensure_user_exists(user_id, username, first_name, last_name)

    bot.send_message(
        msg.chat.id,
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_menu(user_id)
    )

# Добавление задач

user_states = {}  # {user_id: "add_task"}

@bot.callback_query_handler(func=lambda c: c.data == "add_task")
def add_task_start(call):
    user_states[call.from_user.id] = "add_task"
    back = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back.add("⬅ Назад")
    bot.send_message(call.message.chat.id, "Напишите текст задачи:", reply_markup=back)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "add_task")
def process_task_text(msg):
    if msg.text == "⬅ Назад":
        user_states[msg.from_user.id] = None
        bot.send_message(msg.chat.id, "Меню:", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(msg.chat.id, "Выберите действие:", reply_markup=main_menu(msg.from_user.id))
        return

    task_text = msg.text
    user_id = msg.from_user.id

    add_user_task(user_id, task_text)
    user_states[user_id] = None

    bot.send_message(msg.chat.id, "Задача добавлена!", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(msg.chat.id, "Выберите действие:", reply_markup=main_menu(user_id))

# Кнопка мои задачи

@bot.callback_query_handler(func=lambda c: c.data == "my_tasks")
def my_tasks(call):
    user_id = call.from_user.id
    tasks = get_user_tasks(user_id)

    kb = types.InlineKeyboardMarkup()

    if not tasks:
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        bot.edit_message_text(
            "У вас пока нет задач",
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=kb
        )
        return

    for task in tasks:
        status = "✅" if task["done"] else "🔘"
        task_text = task['text'][:30] + "..." if len(task['text']) > 30 else task['text']
        btn = types.InlineKeyboardButton(
            f"{status} {task_text}",
            callback_data=f"task_{task['id']}"
        )
        kb.add(btn)

    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))

    bot.edit_message_text(
        "Ваши задачи:",
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("task_"))
def task_options(call):
    task_id = int(call.data.split("_")[1])
    user_id = call.from_user.id

    # Получаем задачу из базы
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT task_text, is_done FROM tasks WHERE task_id = ?', (task_id,))
    task_data = cursor.fetchone()
    conn.close()

    if not task_data:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return

    task_text, is_done = task_data
    task = {"text": task_text, "done": bool(is_done)}

    kb = types.InlineKeyboardMarkup()
    if not task["done"]:
        kb.add(types.InlineKeyboardButton("✔ Выполнено", callback_data=f"done_{task_id}"))
    kb.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{task_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="my_tasks"))

    bot.edit_message_text(
        f"Задача:\n{task['text']}\nСтатус: {'Выполнено' if task['done'] else 'Не выполнено'}",
        call.message.chat.id,
        call.message.id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def mark_done(call):
    task_id = int(call.data.split("_")[1])
    update_task_status(task_id, True)
    my_tasks(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_task_handler(call):
    task_id = int(call.data.split("_")[1])
    delete_task(task_id)
    my_tasks(call)

# Кнопка назад

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main(call):
    bot.edit_message_text(
        "Выберите действие:",
        call.message.chat.id,
        call.message.id,
        reply_markup=main_menu(call.from_user.id)
    )

# Админ-панель
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def admin_panel(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    kb = types.InlineKeyboardMarkup()

    all_users = get_all_users()
    
    if not all_users:
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        bot.edit_message_text(
            "Нет зарегистрированных пользователей",
            call.message.chat.id,
            call.message.id,
            reply_markup=kb
        )
        return

    for user in all_users:
        display_name = user['username'] or f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or f"User {user['id']}"
        btn_text = f"👤 {display_name}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"admin_view_{user['id']}"))

    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))

    bot.edit_message_text(
        "Список сотрудников:",
        call.message.chat.id,
        call.message.id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_view_"))
def admin_view(call):
    user_id = int(call.data.split("_")[2])

    tasks = get_user_tasks_by_id(user_id)

    text = f"Задачи пользователя {user_id}:\n\n"
    if not tasks:
        text += "Нет задач."
    else:
        for task in tasks:
            text += f"{'✅' if task['done'] else '🔘'} {task['text']}\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="admin_panel"))

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.id,
        reply_markup=kb
    )

# Главный админ

@bot.callback_query_handler(func=lambda c: c.data == "genesis_add_admin")
def genesis_add_admin(call):
    if call.from_user.id != GENESIS_ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    user_states[call.from_user.id] = "add_admin"
    back = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back.add("⬅ Назад")
    bot.send_message(call.message.chat.id, "Отправьте ID пользователя, которого хотите сделать админом:", reply_markup=back)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "add_admin")
def process_add_admin(msg):
    if msg.text == "⬅ Назад":
        user_states[msg.from_user.id] = None
        bot.send_message(msg.chat.id, "Отменено", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(msg.chat.id, "Выберите действие:", reply_markup=main_menu(msg.from_user.id))
        return
        
    try:
        new_admin_id = int(msg.text)
        # Создаем запись пользователя если не существует
        ensure_user_exists(new_admin_id)
        add_admin(new_admin_id, added_by=msg.from_user.id)

        user_states[msg.from_user.id] = None
        bot.send_message(msg.chat.id, f"Пользователь {new_admin_id} назначен админом.", reply_markup=types.ReplyKeyboardRemove())
    except ValueError:
        bot.send_message(msg.chat.id, "Некорректный ID. Введите число.")

# ОБРАБОТКА НЕИЗВЕСТНЫХ СООБЩЕНИЙ

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    bot.send_message(message.chat.id, "Используйте меню для навигации", reply_markup=main_menu(user_id))

# ---------------------------------------------------------
# START BOT
# ---------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("База данных инициализирована")
    print("Бот запущен...")
    bot.infinity_polling()
