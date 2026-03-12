# bot.py
import telebot
from telebot import types
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import time
from functools import wraps

# Импортируем database модуль
import database as db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
bot.remove_webhook()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Декоратор для обработки ошибок
def handle_errors(func):
    @wraps(func)
    def wrapper(message_or_call, *args, **kwargs):
        try:
            return func(message_or_call, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
            bot.send_message(chat_id, f"❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
    return wrapper

def log_action(user_id, action, details=""):
    logger.info(f"User {user_id}: {action}. {details}")

def ensure_user_exists(user_id, username=None, first_name=None, last_name=None):
    """Создает запись пользователя если не существует"""
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
        (user_id, username, first_name, last_name)
    )
    
    conn.commit()
    conn.close()

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
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("📋 Мои задачи", callback_data="my_tasks"),
        types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"),
        types.InlineKeyboardButton("🏢 Мои команды", callback_data="my_teams"),
        types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"),
        types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team"),
        types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    ]
    
    kb.add(*buttons)
    return kb

def teams_menu(user_id):
    teams = db.get_user_teams(user_id)
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    if teams:
        for team in teams:
            admin_tag = " 👑" if team["is_admin"] else ""
            kb.add(types.InlineKeyboardButton(
                f"🏢 {team['name']}{admin_tag}",
                callback_data=f"team_{team['id']}"
            ))
    
    kb.row(
        types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"),
        types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team")
    )
    kb.row(types.InlineKeyboardButton("⬅ Назад в меню", callback_data="back_main"))
    
    return kb

def team_menu(team_id, user_id):
    team_info = db.get_team_info(team_id)
    is_admin = db.is_team_admin(user_id, team_id)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("📋 Задачи команды", callback_data=f"team_tasks_{team_id}"),
        types.InlineKeyboardButton("➕ Добавить задачу", callback_data=f"add_team_task_{team_id}"),
        types.InlineKeyboardButton("👥 Участники", callback_data=f"team_members_{team_id}"),
        types.InlineKeyboardButton("📋 Мои задачи", callback_data=f"my_team_tasks_{team_id}")
    ]
    
    if is_admin:
        buttons.append(types.InlineKeyboardButton("⚙ Управление", callback_data=f"team_manage_{team_id}"))
    
    kb.add(*buttons)
    kb.row(types.InlineKeyboardButton("⬅ Назад к командам", callback_data="my_teams"))
    
    return kb

def team_management_menu(team_id, user_id):
    """Меню управления командой (для админов)"""
    if not db.is_team_admin(user_id, team_id):
        return None
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("👥 Управление участниками", callback_data=f"manage_members_{team_id}")
    ]
    
    if db.is_team_creator(user_id, team_id):
        buttons.append(types.InlineKeyboardButton("🔑 Показать код", callback_data=f"show_code_{team_id}"))
    
    kb.add(*buttons)
    kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
    
    return kb

# Команды
@bot.message_handler(commands=["start"])
@handle_errors
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    first_name = msg.from_user.first_name
    last_name = msg.from_user.last_name
    
    ensure_user_exists(user_id, username, first_name, last_name)
    
    welcome_text = f"""
👋 <b>Привет, {first_name or username or 'друг'}!</b>

🚀 <b>Навигатор Задач</b> поможет тебе:
• 📋 Создавать личные и командные задачи
• 🏢 Работать в командах
• 👥 Сотрудничать с коллегами
• ✅ Отслеживать прогресс

Выбери действие из меню:
    """
    
    bot.send_message(
        msg.chat.id,
        welcome_text,
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["help"])
@handle_errors
def help_command(msg):
    help_text = """
📚 <b>Доступные команды:</b>

/start - Запустить бота
/help - Показать эту справку
/menu - Показать главное меню
/join - Присоединиться к команде
/teams - Показать мои команды
/tasks - Показать мои задачи

🏢 <b>Работа с командами:</b>
1. Создайте команду через меню
2. Поделитесь кодом команды с участниками
3. Участники используют команду /join
4. Работайте над общими задачами!

📋 <b>Задачи:</b>
• Личные задачи видны только вам
• Командные задачи видны всем участникам
    """
    
    bot.send_message(msg.chat.id, help_text)

@bot.message_handler(commands=["menu"])
@handle_errors
def menu_command(msg):
    user_id = msg.from_user.id
    ensure_user_exists(user_id, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
    
    bot.send_message(
        msg.chat.id,
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["join"])
@handle_errors
def join_command(msg):
    user_states[msg.from_user.id] = UserState.JOINING_TEAM
    bot.send_message(
        msg.chat.id,
        "🔗 <b>Присоединение к команде</b>\n\nВведите код команды:"
    )

@bot.message_handler(commands=["teams"])
@handle_errors
def teams_command(msg):
    user_id = msg.from_user.id
    teams = db.get_user_teams(user_id)
    
    if not teams:
        bot.send_message(
            msg.chat.id,
            "📭 У вас пока нет команд. Используйте меню чтобы создать или присоединиться к команде.",
            reply_markup=main_menu()
        )
        return
    
    text = "🏢 <b>Ваши команды:</b>\n\n"
    for team in teams:
        admin_tag = " 👑" if team["is_admin"] else ""
        text += f"• <b>{team['name']}</b>{admin_tag}\n"
    
    bot.send_message(
        msg.chat.id,
        text,
        reply_markup=teams_menu(user_id)
    )

@bot.message_handler(commands=["tasks"])
@handle_errors
def tasks_command(msg):
    user_id = msg.from_user.id
    tasks = db.get_user_tasks(user_id)
    
    if not tasks:
        bot.send_message(
            msg.chat.id,
            "📭 У вас пока нет личных задач. Используйте меню чтобы добавить задачу.",
            reply_markup=main_menu()
        )
        return
    
    text = "📋 <b>Ваши личные задачи:</b>\n\n"
    for idx, task in enumerate(tasks[:10], 1):
        status = "✅" if task["done"] else "🔘"
        priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
        text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}\n"
    
    bot.send_message(
        msg.chat.id,
        text,
        reply_markup=main_menu()
    )

# Callback handlers
@bot.callback_query_handler(func=lambda call: True)
@handle_errors
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    # Главное меню
    if data == "back_main":
        bot.edit_message_text(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=main_menu()
        )
        return
    
    if data == "help":
        help_text = """
📚 <b>Помощь по боту</b>

<b>Основные возможности:</b>
• Личные задачи
• Командные задачи
• Создание команд
• Управление участниками

<b>Команды:</b>
/start - Запустить бота
/help - Показать справку
/menu - Главное меню
        """
        bot.edit_message_text(
            help_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=main_menu()
        )
        return
    
    # Мои задачи
    if data == "my_tasks":
        tasks = db.get_user_tasks(user_id)
        
        if not tasks:
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"))
            kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
            
            bot.edit_message_text(
                "📭 <b>У вас пока нет личных задач</b>\n\nНажмите 'Добавить задачу' чтобы создать первую!",
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                reply_markup=kb
            )
            return
        
        text = "📋 <b>Ваши личные задачи:</b>\n\n"
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        for idx, task in enumerate(tasks[:8], 1):
            status = "✅" if task["done"] else "🔘"
            priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
            deadline = f" | 📅 {task['deadline']}" if task["deadline"] else ""
            text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}{deadline}\n"
            
            btn_text = f"{status} Задача {idx}"
            kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"task_{task['id']}"))
        
        kb.row(
            types.InlineKeyboardButton("➕ Добавить", callback_data="add_task"),
            types.InlineKeyboardButton("⬅ Назад", callback_data="back_main")
        )
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=kb
        )
        return
    
    # Детали задачи
    if data.startswith("task_"):
        try:
            task_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT task_text, is_done, priority, deadline, team_id FROM tasks WHERE task_id = ?', (task_id,))
        task = cursor.fetchone()
        conn.close()
        
        if not task:
            bot.answer_callback_query(call.id, "Задача не найдена")
            return
        
        task_text, is_done, priority, deadline, team_id = task
        status = "✅ Выполнена" if is_done else "🔘 В процессе"
        priority_text = ["🔴 Высокий", "🟡 Средний", "🟢 Низкий"][priority - 1] if 1 <= priority <= 3 else "⚪ Обычный"
        
        text = f"📋 <b>Задача #{task_id}</b>\n\n{task_text}\n\n<b>Статус:</b> {status}\n<b>Приоритет:</b> {priority_text}\n<b>Дедлайн:</b> {deadline or 'Не установлен'}"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        if not is_done:
            kb.add(types.InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"))
        kb.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{task_id}"))
        
        back_cb = f"team_tasks_{team_id}" if team_id else "my_tasks"
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=back_cb))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)
        return
    
    # Выполнить задачу
    if data.startswith("complete_"):
        try:
            task_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        db.update_task_status(task_id, True)
        bot.answer_callback_query(call.id, "✅ Задача выполнена!")
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT team_id FROM tasks WHERE task_id = ?', (task_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            # Это командная задача - обновляем список задач команды
            team_id = result[0]
            team_tasks_handler(call, team_id)
        else:
            # Личная задача
            my_tasks_handler(call)
        return
    
    # Удалить задачу
    if data.startswith("delete_"):
        try:
            task_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT team_id FROM tasks WHERE task_id = ?', (task_id,))
        result = cursor.fetchone()
        conn.close()
        
        db.delete_task(task_id)
        bot.answer_callback_query(call.id, "🗑 Задача удалена!")
        
        if result and result[0]:
            team_id = result[0]
            team_tasks_handler(call, team_id)
        else:
            my_tasks_handler(call)
        return
    
    # Мои команды
    if data == "my_teams":
        teams = db.get_user_teams(user_id)
        
        if not teams:
            kb = types.InlineKeyboardMarkup()
            kb.row(
                types.InlineKeyboardButton("🏗 Создать команду", callback_data="create_team"),
                types.InlineKeyboardButton("🔗 Присоединиться", callback_data="join_team")
            )
            kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
            
            bot.edit_message_text(
                "🏢 <b>Ваши команды</b>\n\n📭 У вас пока нет команд. Вы можете создать новую или присоединиться к существующей.",
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                reply_markup=kb
            )
            return
        
        text = "🏢 <b>Ваши команды:</b>\n\n"
        for team in teams:
            admin_tag = " 👑" if team["is_admin"] else ""
            text += f"• <b>{team['name']}</b>{admin_tag}\n"
            text += f"  Код: <code>{team['code']}</code>\n\n"
        
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=teams_menu(user_id)
        )
        return
    
    # Команда
    if data.startswith("team_"):
        try:
            # Проверяем, что это не team_tasks_ и не другие подстроки
            if data.startswith("team_tasks_") or data.startswith("team_members_") or data.startswith("team_manage_"):
                # Эти случаи обрабатываются отдельно
                pass
            else:
                team_id = int(data.split("_")[1])
                
                team_info = db.get_team_info(team_id)
                if not team_info:
                    bot.answer_callback_query(call.id, "Команда не найдена")
                    return
                
                creator_name = team_info['creator_first_name'] or team_info['creator_username'] or f"ID: {team_info['creator_id']}"
                
                text = f"""
🏢 <b>{team_info['name']}</b>

📝 {team_info['description'] or 'Нет описания'}

👤 Создатель: {creator_name}
👥 Участников: {team_info['member_count']}
📅 Создана: {team_info['created_at'][:10]}
                """
                
                bot.edit_message_text(
                    text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.id,
                    reply_markup=team_menu(team_id, user_id)
                )
                return
        except (ValueError, IndexError):
            # Продолжаем выполнение для других случаев
            pass
    
    # Задачи команды
    if data.startswith("team_tasks_"):
        try:
            # Разные форматы: team_tasks_1 или team_tasks_1_extra
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        team_tasks_handler(call, team_id)
        return
    
    # Мои задачи в команде
    if data.startswith("my_team_tasks_"):
        try:
            parts = data.split("_")
            if len(parts) >= 4:
                team_id = int(parts[3])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        tasks = db.get_user_tasks(user_id, team_id)
        team_info = db.get_team_info(team_id)
        
        if not tasks:
            text = f"🏢 <b>{team_info['name']}</b>\n\n📭 У вас нет задач в этой команде"
        else:
            text = f"🏢 <b>{team_info['name']}</b>\n\n📋 <b>Ваши задачи в команде:</b>\n\n"
            for idx, task in enumerate(tasks, 1):
                status = "✅" if task["done"] else "🔘"
                priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
                deadline = f" | 📅 {task['deadline']}" if task["deadline"] else ""
                text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}{deadline}\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("➕ Добавить задачу", callback_data=f"add_team_task_{team_id}"))
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)
        return
    
    # Участники команды
    if data.startswith("team_members_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        members = db.get_team_members(team_id)
        team_info = db.get_team_info(team_id)
        
        text = f"🏢 <b>{team_info['name']}</b>\n\n👥 <b>Участники команды:</b>\n\n"
        
        for member in members:
            role = "👑 Админ" if member["is_admin"] else "👤 Участник"
            name = member["username"] or f"{member['first_name']} {member['last_name']}".strip() or f"ID: {member['id']}"
            text += f"• {role}: {name}\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)
        return
    
    # Управление командой
    if data.startswith("team_manage_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        if not db.is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав для управления")
            return
        
        team_info = db.get_team_info(team_id)
        text = f"⚙ <b>Управление командой</b>\n\n🏢 <b>{team_info['name']}</b>\n\nВыберите действие:"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=team_management_menu(team_id, user_id))
        return
    
    # Управление участниками
    if data.startswith("manage_members_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        if not db.is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав")
            return
        
        members = db.get_team_members(team_id)
        team_info = db.get_team_info(team_id)
        
        text = f"""
👥 <b>Управление участниками</b>

🏢 {team_info['name']}

Выберите участника для управления:
        """
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        for member in members:
            if member["id"] == user_id:
                continue
                
            role = "👑" if member["is_admin"] else "👤"
            name = member["username"] or f"{member['first_name']} {member['last_name']}".strip() or f"ID: {member['id']}"
            display_name = f"{name[:20]}" if len(name) > 20 else name
            btn_text = f"{role} {display_name}"
            
            kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"member_{team_id}_{member['id']}"))
        
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_manage_{team_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)
        return
    
    # Действия с участником
    if data.startswith("member_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[1])
                member_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        if not db.is_team_admin(user_id, team_id):
            bot.answer_callback_query(call.id, "Нет прав")
            return
        
        member = db.get_member_info(member_id, team_id)
        
        text = f"👤 <b>Управление участником</b>\n\nИмя: {member['name']}\nРоль: {member['role_text']}"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        if member['is_admin']:
            if not db.is_team_creator(member_id, team_id):
                kb.add(types.InlineKeyboardButton("⬇ Снять админа", callback_data=f"demote_{team_id}_{member_id}"))
        else:
            kb.add(types.InlineKeyboardButton("⬆ Назначить админом", callback_data=f"promote_{team_id}_{member_id}"))
        
        if not db.is_team_creator(member_id, team_id):
            kb.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"remove_{team_id}_{member_id}"))
        
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"manage_members_{team_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)
        return
    
    # Назначить админом
    if data.startswith("promote_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[1])
                member_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        success, message = db.add_team_admin(member_id, team_id, user_id)
        bot.answer_callback_query(call.id, message)
        
        if success:
            # Обновляем список участников
            manage_members_handler(call, team_id)
        return
    
    # Снять админа
    if data.startswith("demote_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[1])
                member_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        success, message = db.remove_team_admin(member_id, team_id, user_id)
        bot.answer_callback_query(call.id, message)
        
        if success:
            manage_members_handler(call, team_id)
        return
    
    # Удалить участника
    if data.startswith("remove_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[1])
                member_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        success, message = db.remove_team_member(member_id, team_id, user_id)
        bot.answer_callback_query(call.id, message)
        
        if success:
            manage_members_handler(call, team_id)
        return
    
    # Показать код команды
    if data.startswith("show_code_"):
        try:
            parts = data.split("_")
            if len(parts) >= 3:
                team_id = int(parts[2])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        if not db.is_team_creator(user_id, team_id):
            bot.answer_callback_query(call.id, "Только создатель может видеть код команды")
            return
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT team_code FROM teams WHERE team_id = ?', (team_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            bot.answer_callback_query(call.id, f"Код команды: {result[0]}")
        else:
            bot.answer_callback_query(call.id, "Ошибка")
        return
    
    # Создать команду
    if data == "create_team":
        user_states[user_id] = UserState.CREATING_TEAM
        bot.send_message(
            call.message.chat.id,
            "🏗 <b>Создание новой команды</b>\n\nВведите название для команды (от 3 до 50 символов):"
        )
        return
    
    # Присоединиться к команде
    if data == "join_team":
        user_states[user_id] = UserState.JOINING_TEAM
        bot.send_message(
            call.message.chat.id,
            "🔗 <b>Присоединение к команде</b>\n\nВведите код команды:"
        )
        return
    
    # Добавить личную задачу
    if data == "add_task":
        user_states[user_id] = UserState.ADDING_TASK
        bot.send_message(
            call.message.chat.id,
            "➕ <b>Добавление личной задачи</b>\n\nВведите текст задачи:"
        )
        return
    
    # Добавить командную задачу
    if data.startswith("add_team_task_"):
        try:
            parts = data.split("_")
            if len(parts) >= 4:
                team_id = int(parts[3])
            else:
                bot.answer_callback_query(call.id, "Ошибка формата данных")
                return
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "Ошибка формата данных")
            return
        
        user_states[user_id] = UserState.ADDING_TEAM_TASK
        user_data[user_id] = {"team_id": team_id}
        
        bot.send_message(
            call.message.chat.id,
            f"➕ <b>Добавление задачи для команды</b>\n\nВведите текст задачи:"
        )
        return

def team_tasks_handler(call, team_id):
    """Отдельный обработчик для задач команды"""
    tasks = db.get_team_tasks(team_id)
    team_info = db.get_team_info(team_id)
    
    text = f"🏢 <b>{team_info['name']}</b>\n\n📋 <b>Задачи команды:</b>\n\n"
    
    if not tasks:
        text += "📭 В команде пока нет задач"
    else:
        for idx, task in enumerate(tasks[:15], 1):
            status = "✅" if task[2] else "🔘"
            user_name = task[8] or task[7] or f"ID: {task[6]}"
            text += f"{idx}. {status} {task[1][:40]} — <i>{user_name}</i>\n"
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Добавить задачу", callback_data=f"add_team_task_{team_id}"))
    kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_{team_id}"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)

def my_tasks_handler(call):
    """Отдельный обработчик для личных задач"""
    user_id = call.from_user.id
    tasks = db.get_user_tasks(user_id)
    
    if not tasks:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task"))
        kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        
        bot.edit_message_text(
            "📭 <b>У вас пока нет личных задач</b>\n\nНажмите 'Добавить задачу' чтобы создать первую!",
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            reply_markup=kb
        )
        return
    
    text = "📋 <b>Ваши личные задачи:</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for idx, task in enumerate(tasks[:8], 1):
        status = "✅" if task["done"] else "🔘"
        priority_emoji = ["🔴", "🟡", "🟢"][task["priority"] - 1] if 1 <= task["priority"] <= 3 else "⚪"
        deadline = f" | 📅 {task['deadline']}" if task["deadline"] else ""
        text += f"{idx}. {status} {priority_emoji} {task['text'][:40]}{deadline}\n"
        
        btn_text = f"{status} Задача {idx}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"task_{task['id']}"))
    
    kb.row(
        types.InlineKeyboardButton("➕ Добавить", callback_data="add_task"),
        types.InlineKeyboardButton("⬅ Назад", callback_data="back_main")
    )
    
    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        reply_markup=kb
    )

def manage_members_handler(call, team_id):
    """Отдельный обработчик для управления участниками"""
    user_id = call.from_user.id
    
    if not db.is_team_admin(user_id, team_id):
        bot.answer_callback_query(call.id, "Нет прав")
        return
    
    members = db.get_team_members(team_id)
    team_info = db.get_team_info(team_id)
    
    text = f"""
👥 <b>Управление участниками</b>

🏢 {team_info['name']}

Выберите участника для управления:
    """
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for member in members:
        if member["id"] == user_id:
            continue
            
        role = "👑" if member["is_admin"] else "👤"
        name = member["username"] or f"{member['first_name']} {member['last_name']}".strip() or f"ID: {member['id']}"
        display_name = f"{name[:20]}" if len(name) > 20 else name
        btn_text = f"{role} {display_name}"
        
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"member_{team_id}_{member['id']}"))
    
    kb.row(types.InlineKeyboardButton("⬅ Назад", callback_data=f"team_manage_{team_id}"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb)

# Обработчики состояний
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.CREATING_TEAM)
@handle_errors
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
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TEAM_DESCRIPTION)
@handle_errors
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
    team_id, team_code = db.create_team(team_name, user_id, description)
    
    user_states.pop(user_id, None)
    user_data.pop(user_id, None)
    
    text = f"""
🎉 <b>Команда создана!</b>

🏢 <b>Название:</b> {team_name}
📝 <b>Описание:</b> {description or 'Нет описания'}
🔑 <b>Код команды:</b> <code>{team_code}</code>

📢 <b>Чтобы добавить участников:</b>
Поделитесь кодом команды: <code>{team_code}</code>

Участники могут присоединиться:
1. Через команду /join
2. Через кнопку "Присоединиться" в меню
    """
    
    bot.send_message(
        msg.chat.id,
        text,
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Показываем меню команды
    team_info = db.get_team_info(team_id)
    if team_info:
        creator_name = team_info['creator_first_name'] or team_info['creator_username'] or f"ID: {team_info['creator_id']}"
        
        text = f"""
🏢 <b>{team_info['name']}</b>

📝 {team_info['description'] or 'Нет описания'}

👤 Создатель: {creator_name}
👥 Участников: {team_info['member_count']}
        """
        
        bot.send_message(
            msg.chat.id,
            text,
            reply_markup=team_menu(team_id, user_id)
        )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.JOINING_TEAM)
@handle_errors
def process_join_team(msg):
    user_id = msg.from_user.id
    team_code = msg.text.strip().upper()
    
    success, message = db.join_team(user_id, team_code)
    
    user_states.pop(user_id, None)
    
    if success:
        bot.send_message(
            msg.chat.id,
            f"✅ {message}\n\nТеперь вы можете работать с задачами команды.",
            reply_markup=main_menu()
        )
    else:
        bot.send_message(
            msg.chat.id,
            f"❌ {message}\n\nПроверьте код команды и попробуйте еще раз."
        )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TASK)
@handle_errors
def process_personal_task(msg):
    user_id = msg.from_user.id
    task_text = msg.text.strip()
    
    if not task_text:
        bot.send_message(msg.chat.id, "❌ Текст задачи не может быть пустым")
        return
    
    if len(task_text) > 500:
        bot.send_message(msg.chat.id, "❌ Текст задачи слишком длинный (макс. 500 символов)")
        return
    
    db.add_task(user_id, task_text)
    user_states.pop(user_id, None)
    
    bot.send_message(
        msg.chat.id,
        f"✅ <b>Задача добавлена!</b>\n\n{task_text}",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == UserState.ADDING_TEAM_TASK)
@handle_errors
def process_team_task(msg):
    user_id = msg.from_user.id
    task_text = msg.text.strip()
    team_id = user_data.get(user_id, {}).get("team_id")
    
    if not task_text:
        bot.send_message(msg.chat.id, "❌ Текст задачи не может быть пустым")
        return
    
    if len(task_text) > 500:
        bot.send_message(msg.chat.id, "❌ Текст задачи слишком длинный (макс. 500 символов)")
        return
    
    if team_id:
        db.add_task(user_id, task_text, team_id)
        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        
        bot.send_message(
            msg.chat.id,
            f"✅ <b>Командная задача добавлена!</b>\n\n{task_text}",
            reply_markup=main_menu()
        )

# Обработка всех остальных сообщений
@bot.message_handler(func=lambda message: True)
@handle_errors
def handle_other_messages(message):
    user_id = message.from_user.id
    
    if message.text and message.text.startswith('/'):
        # Показываем подсказку при вводе слеша
        help_text = """
❓ <b>Неизвестная команда</b>

📚 <b>Доступные команды:</b>
/start - Запустить бота
/help - Показать справку
/menu - Показать главное меню
/join - Присоединиться к команде
/teams - Показать мои команды
/tasks - Показать мои задачи
        """
        bot.send_message(message.chat.id, help_text)
        return
    
    ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
    # Если пользователь в каком-то состоянии, обрабатываем
    state = user_states.get(user_id)
    if state is not None:
        # Обработчики уже должны были сработать, но на всякий случай
        bot.send_message(
            message.chat.id,
            "Пожалуйста, завершите текущее действие или используйте меню."
        )
        return
    
    bot.send_message(
        message.chat.id,
        "🤖 Используйте меню для навигации или команду /help для справки",
        reply_markup=main_menu()
    )

if __name__ == "__main__":
    # Инициализируем базу данных
    db.init_db()
    logger.info("База данных инициализирована")
    print("🤖 Бот запущен...")
    print("📝 Для остановки нажмите Ctrl+C")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            time.sleep(5)
