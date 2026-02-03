import telebot
from telebot import types
import sqlite3
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import random
import string

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле")

bot = telebot.TeleBot(BOT_TOKEN)

DB_NAME = "tasks_bot.db"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_action(user_id, action, details=""):
    logger.info(f"User {user_id}: {action}. {details}")

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Команды
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            team_code TEXT UNIQUE,
            created_by INTEGER,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (user_id)
        )
    ''')
    
    # Участники команд (админы команд помечаются здесь)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_members (
            user_id INTEGER,
            team_id INTEGER,
            is_team_admin BOOLEAN DEFAULT FALSE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, team_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Задачи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            team_id INTEGER,
            task_text TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            deadline TEXT,
            is_done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Индексы
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_team ON tasks(team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_members ON team_members(user_id, team_id)')
    
    conn.commit()
    conn.close()

def get_db_connection():
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

def generate_team_code():
    """Генерация уникального кода команды"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(8))

def create_team(team_name, creator_id, description=""):
    """Создание новой команды"""
    team_code = generate_team_code()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Создаем команду
    cursor.execute(
        'INSERT INTO teams (team_name, team_code, created_by, description) VALUES (?, ?, ?, ?)',
        (team_name, team_code, creator_id, description)
    )
    
    team_id = cursor.lastrowid
    
    # Добавляем создателя как админа команды
    cursor.execute(
        'INSERT INTO team_members (user_id, team_id, is_team_admin) VALUES (?, ?, ?)',
        (creator_id, team_id, True)
    )
    
    conn.commit()
    conn.close()
    
    log_action(creator_id, f"Создал команду '{team_name}'", f"Team ID: {team_id}, Code: {team_code}")
    return team_id, team_code

def join_team(user_id, team_code):
    """Присоединение пользователя к команде"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT team_id FROM teams WHERE team_code = ? AND is_active = TRUE', (team_code,))
    team = cursor.fetchone()
    
    if not team:
        conn.close()
        return False, "Команда не найдена или неактивна"
    
    team_id = team[0]
    
    # Проверяем, не состоит ли уже пользователь в команде
    cursor.execute('SELECT 1 FROM team_members WHERE user_id = ? AND team_id = ?', 
                   (user_id, team_id))
    if cursor.fetchone():
        conn.close()
        return False, "Вы уже состоите в этой команде"
    
    # Проверяем не является ли пользователь создателем команды
    cursor.execute('SELECT created_by FROM teams WHERE team_id = ?', (team_id,))
    creator_id = cursor.fetchone()[0]
    is_admin = True if user_id == creator_id else False
    
    cursor.execute(
        'INSERT INTO team_members (user_id, team_id, is_team_admin) VALUES (?, ?, ?)',
        (user_id, team_id, is_admin)
    )
    
    conn.commit()
    conn.close()
    
    log_action(user_id, f"Присоединился к команде", f"Team ID: {team_id}")
    return True, "Вы успешно присоединились к команде"

def is_team_admin(user_id, team_id):
    """Проверка является ли пользователь админом команды"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_team_admin FROM team_members WHERE user_id = ? AND team_id = ?', 
                   (user_id, team_id))
    result = cursor.fetchone()
    conn.close()
    
    return result and bool(result[0])

def is_team_creator(user_id, team_id):
    """Проверка является ли пользователь создателем команды"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT created_by FROM teams WHERE team_id = ?', (team_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result and result[0] == user_id

def get_user_teams(user_id):
    """Получение списка команд пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.team_id, t.team_name, t.team_code, tm.is_team_admin 
        FROM teams t
        JOIN team_members tm ON t.team_id = tm.team_id
        WHERE tm.user_id = ? AND t.is_active = TRUE
        ORDER BY tm.joined_at DESC
    ''', (user_id,))
    
    teams = cursor.fetchall()
    conn.close()
    
    return [{"id": t[0], "name": t[1], "code": t[2], "is_admin": bool(t[3])} for t in teams]

def get_team_info(team_id):
    """Получение информации о команде"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.team_id, t.team_name, t.team_code, t.description, 
               t.created_at, u.user_id, u.username, u.first_name, u.last_name,
               (SELECT COUNT(*) FROM team_members WHERE team_id = ?) as member_count
        FROM teams t
        JOIN users u ON t.created_by = u.user_id
        WHERE t.team_id = ?
    ''', (team_id, team_id))
    
    team = cursor.fetchone()
    conn.close()
    
    if team:
        return {
            "id": team[0],
            "name": team[1],
            "code": team[2],
            "description": team[3],
            "created_at": team[4],
            "creator_id": team[5],
            "creator_username": team[6],
            "creator_first_name": team[7],
            "creator_last_name": team[8],
            "member_count": team[9]
        }
    return None

def get_team_members(team_id):
    """Получение участников команды"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.last_name, tm.is_team_admin, tm.joined_at
        FROM users u
        JOIN team_members tm ON u.user_id = tm.user_id
        WHERE tm.team_id = ?
        ORDER BY tm.is_team_admin DESC, tm.joined_at
    ''', (team_id,))
    
    members = cursor.fetchall()
    conn.close()
    
    return [{"id": m[0], "username": m[1], "first_name": m[2], 
             "last_name": m[3], "is_admin": bool(m[4]), "joined_at": m[5]} for m in members]

def get_team_tasks(team_id):
    """Получение задач команды"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.task_id, t.task_text, t.is_done, t.priority, t.deadline,
               t.created_at, u.user_id, u.username, u.first_name
        FROM tasks t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.team_id = ?
        ORDER BY t.priority DESC, t.created_at DESC
    ''', (team_id,))
    
    tasks = cursor.fetchall()
    conn.close()
    
    return tasks

def get_user_tasks(user_id, team_id=None):
    """Получение задач пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if team_id:
        cursor.execute('''
            SELECT task_id, task_text, is_done, priority, deadline, created_at
            FROM tasks 
            WHERE user_id = ? AND team_id = ?
            ORDER BY priority DESC, created_at DESC
        ''', (user_id, team_id))
    else:
        cursor.execute('''
            SELECT task_id, task_text, is_done, priority, deadline, created_at
            FROM tasks 
            WHERE user_id = ? AND team_id IS NULL
            ORDER BY priority DESC, created_at DESC
        ''', (user_id,))
    
    tasks = cursor.fetchall()
    conn.close()
    
    return [{"id": task[0], "text": task[1], "done": bool(task[2]), 
             "priority": task[3], "deadline": task[4], "created_at": task[5]} for task in tasks]

def add_task(user_id, task_text, team_id=None, priority=1, deadline=None):
    """Добавление задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO tasks (user_id, team_id, task_text, priority, deadline)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, team_id, task_text, priority, deadline))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return task_id

def update_task_status(task_id, is_done):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET is_done = ? WHERE task_id = ?', (is_done, task_id))
    conn.commit()
    conn.close()

def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    conn.commit()
    conn.close()

def add_team_admin(user_id, team_id, added_by):
    """Назначение пользователя админом команды"""
    if not is_team_creator(added_by, team_id):
        return False, "Только создатель команды может назначать админов"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, что пользователь состоит в команде
    cursor.execute('SELECT 1 FROM team_members WHERE user_id = ? AND team_id = ?', 
                   (user_id, team_id))
    if not cursor.fetchone():
        conn.close()
        return False, "Пользователь не состоит в команде"
    
    # Назначаем админом
    cursor.execute('''
        UPDATE team_members 
        SET is_team_admin = TRUE 
        WHERE user_id = ? AND team_id = ?
    ''', (user_id, team_id))
    
    conn.commit()
    conn.close()
    
    log_action(added_by, f"Назначил админом команды", f"User: {user_id}, Team: {team_id}")
    return True, "Пользователь назначен админом команды"

def remove_team_admin(user_id, team_id, removed_by):
    """Снятие прав админа команды"""
    if not is_team_creator(removed_by, team_id):
        return False, "Только создатель команды может снимать админов"
    
    # Нельзя снять права у создателя
    if is_team_creator(user_id, team_id):
        return False, "Нельзя снять права у создателя команды"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE team_members 
        SET is_team_admin = FALSE 
        WHERE user_id = ? AND team_id = ?
    ''', (user_id, team_id))
    
    conn.commit()
    conn.close()
    
    log_action(removed_by, f"Снял права админа", f"User: {user_id}, Team: {team_id}")
    return True, "Права админа сняты"

def remove_team_member(user_id, team_id, removed_by):
    """Удаление участника из команды"""
    if not is_team_admin(removed_by, team_id):
        return False, "Только админ команды может удалять участников"
    
    # Нельзя удалить создателя
    if is_team_creator(user_id, team_id):
        return False, "Нельзя удалить создателя команды"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM team_members WHERE user_id = ? AND team_id = ?', 
                   (user_id, team_id))
    
    conn.commit()
    conn.close()
    
    log_action(removed_by, f"Удалил участника из команды", f"User: {user_id}, Team: {team_id}")
    return True, "Участник удален из команды"

# Хранилище состояний пользователей
user_states = {}
user_data = {}

class UserState:
    IDLE = 0
    ADDING_TASK = 1
    ADDING_TEAM_TASK = 2
    CREATING_TEAM = 3
    JOINING_TEAM = 4
    ADDING_TEAM_DESCRIPTION = 5
    ADDING_TASK_PRIORITY = 6
    ADDING_TASK_DEADLINE = 7

# Меню
def main_menu(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    kb.add(types.InlineKeyboardButton("📋 Мои задачи", callback_data="my_tasks"))
    kb.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"))
    kb.add(types.InlineKeyboardButton("🏢 Мои команды", callback_data="my_teams"))
    kb.add(types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"))
    kb.add(types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team"))
    
    return kb

def teams_menu(user_id):
    teams = get_user_teams(user_id)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if teams:
        for team in teams:
            admin_tag = " 👑" if team["is_admin"] else ""
            kb.add(types.InlineKeyboardButton(
                f"🏢 {team['name']}{admin_tag}",
                callback_data=f"team_{team['id']}"
            ))
    else:
        kb.add(types.InlineKeyboardButton("📭 У вас нет команд", callback_data="no_teams"))
    
    kb.add(types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"))
    kb.add(types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team"))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    
    return kb

def team_menu(team_id, user_id):
    team_info = get_team_info(team_id)
    is_ta = is_team_admin(user_id, team_id)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    kb.add(types.InlineKeyboardButton("📋 Задачи команды", callback_data=f"team_tasks_{team_id}"))
    kb.add(types.InlineKeyboardButton("➕ Задачу команде", callback_data=f"add_team_task_{team_id}"))
    kb.add(types.InlineKeyboardButton("👥 Участники", callback_data=f"team_members_{team_id}"))
    
    if is_ta:
        kb.add(types.InlineKeyboardButton("⚙ Управление", callback_data=f"team_manage_{team_id}"))
    
    kb.add(types.InlineKeyboardButton("📋 Мои задачи в команде", callback_data=f"my_team_tasks_{team_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Назад к командам", callback_data="my_teams"))
    
    return kb

def team_management_menu(team_id, user_id):
    """Меню управления командой (для админов)"""
    if not is_team_admin(user_id, team_id):
        return None
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    kb.add(types.InlineKeyboardButton("👥 Управление участниками", callback_data=f"manage_members_{team_id}"))
    kb.add(types.InlineKeyboardButton("📊 Статистика команды", callback_data=f"team_stats_{team_id}"))
    
    if is_team_creator(user_id, team_id):
        kb.add(types.InlineKeyboardButton("🔑 Показать код команды", callback_data=f"show_code_{team_id}"))
    
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
    
    return kb

@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    first_name = msg.from_user.first_name
    last_name = msg.from_user.last_name
    
    ensure_user_exists(user_id, username, first_name, last_name)
    
    welcome_text = f"""
👋 Привет, {first_name or username or 'друг'}!

🚀 *Навигатор Задач* поможет тебе:
• 📋 Создавать личные и командные задачи
• 🏢 Работать в командах
• 👥 Сотрудничать с коллегами
• ✅ Отслеживать прогресс

Выбери действие из меню:
    """
    
    bot.send_message(
        msg.chat.id,
        welcome_text,
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@bot.message_handler(commands=["help"])
def help_command(msg):
    help_text = """
📚 *Доступные команды:*

/start - Запустить бота
/help - Показать эту справку
/join - Присоединиться к команде (требует код команды)
/teams - Показать мои команды
/tasks - Показать мои задачи
/stats - Показать статистику

🏢 *Работа с командами:*
1. Создайте команду через меню
2. Поделитесь кодом команды с участниками
3. Участники используют команду /join или кнопку "Присоединиться"
4. Работайте над общими задачами!

📋 *Задачи:*
• Личные задачи видны только вам
• Командные задачи видны всем участникам команды
    """
    
    bot.send_message(msg.chat.id, help_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "my_tasks")
def my_tasks_handler(call):
    user_id = call.from_user.id
    tasks = get_user_tasks(user_id)
    
    if not tasks:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        
        bot.edit_message_text(
            "📭 *У вас пока нет личных задач*\n\nНажмите 'Добавить задачу' чтобы создать первую!",
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
        return
    
    text = "📋 *Ваши личные задачи:*\n\n"
    for idx, task in enumerate(tasks[:10], 1):  # Показываем первые 10
        status = "✅" if task["done"] else "🔘"
        priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
        deadline = f" | 📅 {task['deadline']}" if task["deadline"] else ""
        text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}{deadline}\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for idx, task in enumerate(tasks[:6], 1):  # Кнопки для первых 6 задач
        status = "✅" if task["done"] else "🔘"
        btn_text = f"{status} Задача {idx}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"task_{task['id']}"))
    
    kb.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("task_"))
def task_detail_handler(call):
    try:
        task_id = int(call.data.split("_")[1])
        user_id = call.from_user.id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_text, is_done, priority, deadline, team_id 
            FROM tasks WHERE task_id = ?
        ''', (task_id,))
        task = cursor.fetchone()
        conn.close()
        
        if not task:
            bot.answer_callback_query(call.id, "Задача не найдена")
            return
        
        task_text, is_done, priority, deadline, team_id = task
        status = "✅ Выполнена" if is_done else "🔘 В процессе"
        priority_text = ["Высокий", "Средний", "Низкий"][priority - 1] if 1 <= priority <= 3 else "Обычный"
        
        text = f"""
📋 *Задача #{task_id}*

{task_text}

*Статус:* {status}
*Приоритет:* {priority_text}
*Дедлайн:* {deadline or "Не установлен"}
        """
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        if not is_done:
            kb.add(types.InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"))
        
        kb.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{task_id}"))
        
        if team_id:
            kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_tasks_{team_id}"))
        else:
            kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="my_tasks"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("complete_"))
def complete_task_handler(call):
    task_id = int(call.data.split("_")[1])
    update_task_status(task_id, True)
    bot.answer_callback_query(call.id, "✅ Задача выполнена!")
    
    # Возвращаемся к списку задач
    my_tasks_handler(call)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delete_"))
def delete_task_handler(call):
    task_id = int(call.data.split("_")[1])
    delete_task(task_id)
    bot.answer_callback_query(call.id, "🗑 Задача удалена!")
    
    # Возвращаемся к списку задач
    my_tasks_handler(call)

@bot.callback_query_handler(func=lambda c: c.data == "my_teams")
def my_teams_handler(call):
    teams = get_user_teams(call.from_user.id)
    
    if not teams:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"))
        kb.add(types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        
        bot.edit_message_text(
            "🏢 *Ваши команды*\n\n📭 У вас пока нет команд. Вы можете создать новую или присоединиться к существующей.",
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
        return
    
    text = "🏢 *Ваши команды:*\n\n"
    for team in teams:
        admin_tag = " 👑" if team["is_admin"] else ""
        text += f"• *{team['name']}*{admin_tag}\n"
        text += f"  Код: `{team['code']}`\n\n"
    
    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        parse_mode="Markdown",
        reply_markup=teams_menu(call.from_user.id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("team_"))
def team_handler(call):
    try:
        if call.data.startswith("team_"):
            team_id = int(call.data.split("_")[1])
            
            team_info = get_team_info(team_id)
            if not team_info:
                bot.answer_callback_query(call.id, "Команда не найдена")
                return
            
            text = f"""
🏢 *{team_info['name']}*

📝 {team_info['description'] or 'Нет описания'}

👤 Создатель: {team_info['creator_first_name'] or team_info['creator_username'] or f"ID: {team_info['creator_id']}"}
👥 Участников: {team_info['member_count']}
📅 Создана: {team_info['created_at'][:10]}
            """
            
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                parse_mode="Markdown",
                reply_markup=team_menu(team_id, call.from_user.id)
            )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == "create_team")
def create_team_handler(call):
    user_states[call.from_user.id] = UserState.CREATING_TEAM
    bot.send_message(
        call.message.chat.id,
        "🏗 *Создание новой команды*\n\nВведите название для команды (от 3 до 50 символов):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.CREATING_TEAM)
def process_team_name(msg):
    user_id = msg.from_user.id
    team_name = msg.text.strip()
    
    if len(team_name) < 3 or len(team_name) > 50:
        bot.send_message(msg.chat.id, "❌ Название команды должно быть от 3 до 50 символов")
        return
    
    user_data[user_id] = {"team_name": team_name}
    user_states[user_id] = UserState.ADDING_TEAM_DESCRIPTION
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Пропустить"))
    
    bot.send_message(
        msg.chat.id,
        "📝 Введите описание команды (или нажмите 'Пропустить'):",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TEAM_DESCRIPTION)
def process_team_description(msg):
    user_id = msg.from_user.id
    
    if msg.text == "Пропустить":
        description = ""
    else:
        description = msg.text.strip()
        if len(description) > 200:
            bot.send_message(msg.chat.id, "❌ Описание слишком длинное (макс. 200 символов)")
            return
    
    team_name = user_data[user_id]["team_name"]
    team_id, team_code = create_team(team_name, user_id, description)
    
    del user_states[user_id]
    del user_data[user_id]
    
    text = f"""
🎉 *Команда создана!*

🏢 *Название:* {team_name}
📝 *Описание:* {description or 'Нет описания'}
🔑 *Код команды:* `{team_code}`

📢 *Чтобы добавить участников:*\nПоделитесь кодом команды: `{team_code}`

Участники могут присоединиться:
1. Через команду /join
2. Через кнопку "Присоединиться" в меню
3. Введя код: `{team_code}`
    """
    
    bot.send_message(
        msg.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Показываем меню команды
    team_info = get_team_info(team_id)
    if team_info:
        text = f"""
🏢 *{team_info['name']}*

📝 {team_info['description'] or 'Нет описания'}

👤 Создатель: вы
👥 Участников: {team_info['member_count']}
        """
        
        bot.send_message(
            msg.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=team_menu(team_id, user_id)
        )

@bot.callback_query_handler(func=lambda c: c.data == "join_team")
def join_team_handler(call):
    user_states[call.from_user.id] = UserState.JOINING_TEAM
    bot.send_message(
        call.message.chat.id,
        "🔗 *Присоединение к команде*\n\nВведите код команды:",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.JOINING_TEAM)
def process_join_team(msg):
    user_id = msg.from_user.id
    team_code = msg.text.strip().upper()
    
    success, message = join_team(user_id, team_code)
    
    del user_states[user_id]
    
    if success:
        bot.send_message(
            msg.chat.id,
            f"✅ {message}\n\nТеперь вы можете работать с задачами команды.",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        bot.send_message(
            msg.chat.id,
            f"❌ {message}\n\nПроверьте код команды и попробуйте еще раз.",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda c: c.data == "add_task")
def add_task_handler(call):
    user_states[call.from_user.id] = UserState.ADDING_TASK
    bot.send_message(
        call.message.chat.id,
        "➕ *Добавление личной задачи*\n\nВведите текст задачи:",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TASK)
def process_personal_task(msg):
    user_id = msg.from_user.id
    task_text = msg.text.strip()
    
    if not task_text:
        bot.send_message(msg.chat.id, "❌ Текст задачи не может быть пустым")
        return
    
    if len(task_text) > 500:
        bot.send_message(msg.chat.id, "❌ Текст задачи слишком длинный (макс. 500 символов)")
        return
    
    add_task(user_id, task_text)
    del user_states[user_id]
    
    bot.send_message(
        msg.chat.id,
        f"✅ *Задача добавлена!*\n\n`{task_text}`",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_team_task_"))
def add_team_task_handler(call):
    try:
        team_id = int(call.data.split("_")[3])
        user_states[call.from_user.id] = UserState.ADDING_TEAM_TASK
        user_data[call.from_user.id] = {"team_id": team_id}
        
        bot.send_message(
            call.message.chat.id,
            f"➕ *Добавление задачи для команды*\n\nВведите текст задачи:",
            parse_mode="Markdown"
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TEAM_TASK)
def process_team_task(msg):
    user_id = msg.from_user.id
    task_text = msg.text.strip()
    team_id = user_data[user_id].get("team_id")
    
    if not task_text:
        bot.send_message(msg.chat.id, "❌ Текст задачи не может быть пустым")
        return
    
    if len(task_text) > 500:
        bot.send_message(msg.chat.id, "❌ Текст задачи слишком длинный (макс. 500 символов)")
        return
    
    if team_id:
        add_task(user_id, task_text, team_id)
        del user_states[user_id]
        del user_data[user_id]
        
        bot.send_message(
            msg.chat.id,
            f"✅ *Командная задача добавлена!*\n\n`{task_text}`",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )

@bot.callback_query_handler(func=lambda c: c.data.startswith("team_tasks_"))
def team_tasks_handler(call):
    try:
        team_id = int(call.data.split("_")[2])
        tasks = get_team_tasks(team_id)
        
        team_info = get_team_info(team_id)
        if not team_info:
            bot.answer_callback_query(call.id, "Команда не найдена")
            return
        
        if not tasks:
            text = f"🏢 *{team_info['name']}*\n\n📭 В команде пока нет задач"
        else:
            text = f"🏢 *{team_info['name']}*\n\n📋 *Задачи команды:*\n\n"
            for idx, task in enumerate(tasks[:15], 1):  # Показываем первые 15
                status = "✅" if task[2] else "🔘"
                priority_emoji = ["🔴", "🟡", "🟢"][task[3] - 1] if 1 <= task[3] <= 3 else "⚪"
                author = f"(@{task[7]})" if task[7] else f"({task[8]})"
                deadline = f" | 📅 {task[4]}" if task[4] else ""
                text += f"{idx}. {status} {priority_emoji} {task[1][:40]} {author}{deadline}\n"
            
            if len(tasks) > 15:
                text += f"\n... и еще {len(tasks) - 15} задач"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data=f"add_team_task_{team_id}"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка загрузки задач")

@bot.callback_query_handler(func=lambda c: c.data.startswith("team_members_"))
def team_members_handler(call):
    try:
        team_id = int(call.data.split("_")[2])
        members = get_team_members(team_id)
        
        team_info = get_team_info(team_id)
        if not team_info:
            bot.answer_callback_query(call.id, "Команда не найдена")
            return
        
        text = f"🏢 *{team_info['name']}*\n\n👥 *Участники команды:*\n\n"
        
        for member in members:
            role = "👑 Админ" if member["is_admin"] else "👤 Участник"
            name = member["username"] or f"{member['first_name']} {member['last_name']}".strip() or f"ID: {member['id']}"
            joined = member["joined_at"][:10] if member["joined_at"] else ""
            text += f"• {role}: {name}\n"
            if joined:
                text += f"  📅 Присоединился: {joined}\n"
            text += "\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка загрузки участников")

@bot.callback_query_handler(func=lambda c: c.data.startswith("team_manage_"))
def team_manage_handler(call):
    try:
        team_id = int(call.data.split("_")[2])
        user_id = call.from_user.id
        
        if not is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав для управления командой")
            return
        
        team_info = get_team_info(team_id)
        if not team_info:
            bot.answer_callback_query(call.id, "Команда не найдена")
            return
        
        text = f"""
⚙ *Управление командой*

🏢 *{team_info['name']}*

👤 Создатель: {team_info['creator_first_name'] or team_info['creator_username'] or f"ID: {team_info['creator_id']}"}
👥 Участников: {team_info['member_count']}

Выберите действие:
        """
        
        kb = team_management_menu(team_id, user_id)
        if kb:
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                parse_mode="Markdown",
                reply_markup=kb
            )
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("manage_members_"))
def manage_members_handler(call):
    try:
        team_id = int(call.data.split("_")[2])
        user_id = call.from_user.id
        
        if not is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав")
            return
        
        members = get_team_members(team_id)
        team_info = get_team_info(team_id)
        
        text = f"""
👥 *Управление участниками*

🏢 {team_info['name']}

Выберите участника для управления:
        """
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        for member in members:
            # Не показываем себя в списке для управления
            if member["id"] == user_id:
                continue
                
            role = "👑" if member["is_admin"] else "👤"
            name = member["username"] or f"{member['first_name']} {member['last_name']}".strip() or f"ID: {member['id']}"
            display_name = f"{name[:15]}..." if len(name) > 15 else name
            btn_text = f"{role} {display_name}"
            
            kb.add(types.InlineKeyboardButton(
                btn_text, 
                callback_data=f"member_{team_id}_{member['id']}"
            ))
        
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_manage_{team_id}"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("member_"))
def member_actions_handler(call):
    try:
        parts = call.data.split("_")
        team_id = int(parts[1])
        member_id = int(parts[2])
        user_id = call.from_user.id
        
        if not is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав")
            return
        
        # Получаем информацию об участнике
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.username, u.first_name, u.last_name, tm.is_team_admin
            FROM users u
            JOIN team_members tm ON u.user_id = tm.user_id
            WHERE u.user_id = ? AND tm.team_id = ?
        ''', (member_id, team_id))
        
        member = cursor.fetchone()
        conn.close()
        
        if not member:
            bot.answer_callback_query(call.id, "Участник не найден")
            return
        
        username, first_name, last_name, is_admin = member
        member_name = username or f"{first_name} {last_name}".strip() or f"ID: {member_id}"
        
        text = f"""
👤 *Управление участником*

Имя: {member_name}
Роль: {'👑 Админ команды' if is_admin else '👤 Участник'}

Выберите действие:
        """
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        if is_admin:
            # Если участник админ, можно снять права (если не создатель)
            if not is_team_creator(member_id, team_id):
                kb.add(types.InlineKeyboardButton(
                    "⬇ Снять админа", 
                    callback_data=f"demote_{team_id}_{member_id}"
                ))
        else:
            # Если участник не админ, можно назначить админом
            kb.add(types.InlineKeyboardButton(
                "⬆ Назначить админом", 
                callback_data=f"promote_{team_id}_{member_id}"
            ))
        
        # Удалить из команды (кроме создателя)
        if not is_team_creator(member_id, team_id):
            kb.add(types.InlineKeyboardButton(
                "🗑 Удалить из команды", 
                callback_data=f"remove_{team_id}_{member_id}"
            ))
        
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"manage_members_{team_id}"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("promote_"))
def promote_member_handler(call):
    try:
        parts = call.data.split("_")
        team_id = int(parts[1])
        member_id = int(parts[2])
        user_id = call.from_user.id
        
        success, message = add_team_admin(member_id, team_id, user_id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ Участник назначен админом")
            # Возвращаемся к управлению участниками
            manage_members_handler(call)
        else:
            bot.answer_callback_query(call.id, f"❌ {message}")
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("demote_"))
def demote_member_handler(call):
    try:
        parts = call.data.split("_")
        team_id = int(parts[1])
        member_id = int(parts[2])
        user_id = call.from_user.id
        
        success, message = remove_team_admin(member_id, team_id, user_id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ Права админа сняты")
            manage_members_handler(call)
        else:
            bot.answer_callback_query(call.id, f"❌ {message}")
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
def remove_member_handler(call):
    try:
        parts = call.data.split("_")
        team_id = int(parts[1])
        member_id = int(parts[2])
        user_id = call.from_user.id
        
        success, message = remove_team_member(member_id, team_id, user_id)
        
        if success:
            bot.answer_callback_query(call.id, "✅ Участник удален")
            manage_members_handler(call)
        else:
            bot.answer_callback_query(call.id, f"❌ {message}")
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("show_code_"))
def show_code_handler(call):
    try:
        team_id = int(call.data.split("_")[2])
        user_id = call.from_user.id
        
        if not is_team_creator(user_id, team_id):
            bot.answer_callback_query(call.id, "Только создатель может видеть код команды")
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT team_code FROM teams WHERE team_id = ?', (team_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            bot.answer_callback_query(call.id, f"Код команды: {result[0]}")
        else:
            bot.answer_callback_query(call.id, "Ошибка")
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("my_team_tasks_"))
def my_team_tasks_handler(call):
    try:
        team_id = int(call.data.split("_")[3])
        user_id = call.from_user.id
        
        tasks = get_user_tasks(user_id, team_id)
        team_info = get_team_info(team_id)
        
        if not tasks:
            text = f"🏢 *{team_info['name']}*\n\n📭 У вас нет задач в этой команде"
        else:
            text = f"🏢 *{team_info['name']}*\n\n📋 *Ваши задачи в команде:*\n\n"
            for idx, task in enumerate(tasks, 1):
                status = "✅" if task["done"] else "🔘"
                priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
                deadline = f" | 📅 {task['deadline']}" if task["deadline"] else ""
                text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}{deadline}\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data=f"add_team_task_{team_id}"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except:
        bot.answer_callback_query(call.id, "Ошибка")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main_handler(call):
    bot.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите действие:",
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        parse_mode="Markdown",
        reply_markup=main_menu(call.from_user.id)
    )

@bot.callback_query_handler(func=lambda c: c.data == "no_teams")
def no_teams_handler(call):
    bot.answer_callback_query(call.id, "У вас пока нет команд")

@bot.message_handler(commands=["join"])
def join_command(msg):
    user_states[msg.from_user.id] = UserState.JOINING_TEAM
    bot.send_message(
        msg.chat.id,
        "🔗 *Присоединение к команде*\n\nВведите код команды:",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["teams"])
def teams_command(msg):
    user_id = msg.from_user.id
    teams = get_user_teams(user_id)
    
    if not teams:
        bot.send_message(
            msg.chat.id,
            "📭 У вас пока нет команд. Используйте меню чтобы создать или присоединиться к команде.",
            reply_markup=main_menu(user_id)
        )
        return
    
    text = "🏢 *Ваши команды:*\n\n"
    for team in teams:
        admin_tag = " 👑" if team["is_admin"] else ""
        text += f"• *{team['name']}*{admin_tag}\n"
    
    bot.send_message(
        msg.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=teams_menu(user_id)
    )

@bot.message_handler(commands=["tasks"])
def tasks_command(msg):
    user_id = msg.from_user.id
    tasks = get_user_tasks(user_id)
    
    if not tasks:
        bot.send_message(
            msg.chat.id,
            "📭 У вас пока нет личных задач. Используйте меню чтобы добавить задачу.",
            reply_markup=main_menu(user_id)
        )
        return
    
    text = "📋 *Ваши личные задачи:*\n\n"
    for idx, task in enumerate(tasks[:10], 1):
        status = "✅" if task["done"] else "🔘"
        priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
        text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}\n"
    
    bot.send_message(
        msg.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Неизвестная команда. Используйте /help для списка команд")
        return
    
    ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
    # Если пользователь в каком-то состоянии, обрабатываем
    state = user_states.get(user_id)
    if state == UserState.JOINING_TEAM:
        process_join_team(message)
        return
    elif state == UserState.CREATING_TEAM:
        process_team_name(message)
        return
    elif state == UserState.ADDING_TEAM_DESCRIPTION:
        process_team_description(message)
        return
    elif state == UserState.ADDING_TASK:
        process_personal_task(message)
        return
    elif state == UserState.ADDING_TEAM_TASK:
        process_team_task(message)
        return
    
    bot.send_message(
        message.chat.id,
        "🤖 Используйте меню для навигации или команду /help для справки",
        reply_markup=main_menu(user_id)
    )

if __name__ == "__main__":
    init_db()
    logger.info("База данных инициализирована")
    print("🤖 Бот запущен...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
