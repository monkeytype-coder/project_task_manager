# database.py
import sqlite3
import random
import string
from datetime import datetime

DB_NAME = "tasks_bot.db"

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
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
    
    # Участники команд
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

# Статистика для админ-панели
def get_total_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_teams():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM teams WHERE is_active = TRUE')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tasks')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_completed_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tasks WHERE is_done = TRUE')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_users_stats():
    """Детальная статистика по пользователям"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.created_at,
            COUNT(DISTINCT tm.team_id) as teams_count,
            COUNT(DISTINCT t.task_id) as tasks_count,
            SUM(CASE WHEN t.is_done = TRUE THEN 1 ELSE 0 END) as completed_tasks
        FROM users u
        LEFT JOIN team_members tm ON u.user_id = tm.user_id
        LEFT JOIN tasks t ON u.user_id = t.user_id
        GROUP BY u.user_id
        ORDER BY u.created_at DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    return [{
        'user_id': u[0],
        'username': u[1],
        'first_name': u[2],
        'last_name': u[3],
        'created_at': u[4],
        'teams_count': u[5] or 0,
        'tasks_count': u[6] or 0,
        'completed_tasks': u[7] or 0
    } for u in users]

def get_teams_stats():
    """Детальная статистика по командам"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            t.team_id,
            t.team_name,
            t.team_code,
            t.description,
            t.created_at,
            u.username as creator_username,
            u.first_name as creator_first_name,
            COUNT(DISTINCT tm.user_id) as members_count,
            COUNT(DISTINCT tk.task_id) as tasks_count,
            SUM(CASE WHEN tk.is_done = TRUE THEN 1 ELSE 0 END) as completed_tasks
        FROM teams t
        JOIN users u ON t.created_by = u.user_id
        LEFT JOIN team_members tm ON t.team_id = tm.team_id
        LEFT JOIN tasks tk ON t.team_id = tk.team_id
        WHERE t.is_active = TRUE
        GROUP BY t.team_id
        ORDER BY t.created_at DESC
    ''')
    
    teams = cursor.fetchall()
    conn.close()
    
    return [{
        'team_id': tm[0],
        'team_name': tm[1],
        'team_code': tm[2],
        'description': tm[3],
        'created_at': tm[4],
        'creator': tm[5] or tm[6] or f"ID: {tm[0]}",
        'members_count': tm[7] or 0,
        'tasks_count': tm[8] or 0,
        'completed_tasks': tm[9] or 0
    } for tm in teams]

def get_recent_activity(limit=20):
    """Получение недавней активности"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            'task_created' as type,
            u.username,
            t.task_text,
            t.created_at,
            tm.team_name
        FROM tasks t
        JOIN users u ON t.user_id = u.user_id
        LEFT JOIN teams tm ON t.team_id = tm.team_id
        UNION ALL
        SELECT 
            'user_joined' as type,
            u.username,
            'Присоединился к системе' as task_text,
            u.created_at,
            NULL as team_name
        FROM users u
        UNION ALL
        SELECT 
            'team_created' as type,
            cr.username,
            tm.team_name as task_text,
            tm.created_at,
            NULL as team_name
        FROM teams tm
        JOIN users cr ON tm.created_by = cr.user_id
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))
    
    activities = cursor.fetchall()
    conn.close()
    
    return [{
        'type': a[0],
        'username': a[1],
        'text': a[2],
        'time': a[3],
        'team_name': a[4]
    } for a in activities]


def get_user_tasks(user_id, team_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if team_id:
        cursor.execute(
            "SELECT task_id, task_text, is_done, priority, deadline FROM tasks WHERE user_id=? AND team_id=? ORDER BY created_at DESC",
            (user_id, team_id)
        )
    else:
        cursor.execute(
            "SELECT task_id, task_text, is_done, priority, deadline FROM tasks WHERE user_id=? AND team_id IS NULL ORDER BY created_at DESC",
            (user_id,)
        )

    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for r in rows:
        tasks.append({
            "id": r[0],
            "text": r[1],
            "done": bool(r[2]),
            "priority": r[3],
            "deadline": r[4]
        })

    return tasks

def get_team_tasks(team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT t.task_id, t.task_text, t.is_done, t.priority, t.deadline,
               u.user_id, u.username, u.first_name
        FROM tasks t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.team_id=?
        ORDER BY t.created_at DESC
    """, (team_id,))

    rows = cursor.fetchall()
    conn.close()

    return rows

def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
    conn.commit()
    conn.close()

def update_task_status(task_id, done=True):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE tasks SET is_done=? WHERE task_id=?",
        (done, task_id)
    )

    conn.commit()
    conn.close()

def add_task(user_id, text, team_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (user_id, team_id, task_text) VALUES (?, ?, ?)",
        (user_id, team_id, text)
    )

    conn.commit()
    conn.close()

def get_team_info(team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT team_id, team_name, description, created_by, created_at
        FROM teams WHERE team_id=?
    """, (team_id,))

    team = cursor.fetchone()

    if not team:
        conn.close()
        return None

    cursor.execute("SELECT COUNT(*) FROM team_members WHERE team_id=?", (team_id,))
    member_count = cursor.fetchone()[0]

    cursor.execute("SELECT username, first_name FROM users WHERE user_id=?", (team[3],))
    creator = cursor.fetchone()

    conn.close()

    return {
        "id": team[0],
        "name": team[1],
        "description": team[2],
        "creator_id": team[3],
        "creator_username": creator[0] if creator else None,
        "creator_first_name": creator[1] if creator else None,
        "member_count": member_count,
        "created_at": team[4]
    }


def get_daily_stats(days=7):
    """Статистика по дням"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as count
        FROM users
        WHERE created_at >= DATE('now', ?)
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (f'-{days} days',))
    
    users_daily = cursor.fetchall()
    
    cursor.execute('''
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as count
        FROM tasks
        WHERE created_at >= DATE('now', ?)
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (f'-{days} days',))
    
    tasks_daily = cursor.fetchall()
    conn.close()
    
def get_user_teams(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            t.team_id,
            t.team_name,
            t.team_code,
            tm.is_team_admin
        FROM teams t
        JOIN team_members tm ON t.team_id = tm.team_id
        WHERE tm.user_id = ? AND t.is_active = TRUE
        ORDER BY t.created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    teams = []
    for row in rows:
        teams.append({
            "id": row[0],
            "name": row[1],
            "code": row[2],
            "is_admin": bool(row[3])
        })

    return teams

def generate_team_code(length=6):
    """Генерация кода команды"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def create_team(team_name, user_id, description=""):
    conn = get_db_connection()
    cursor = conn.cursor()

    # генерируем уникальный код команды
    team_code = generate_team_code()

    while True:
        cursor.execute("SELECT 1 FROM teams WHERE team_code=?", (team_code,))
        if cursor.fetchone() is None:
            break
        team_code = generate_team_code()

    # создаём команду
    cursor.execute(
        """
        INSERT INTO teams (team_name, team_code, created_by, description)
        VALUES (?, ?, ?, ?)
        """,
        (team_name, team_code, user_id, description)
    )

    team_id = cursor.lastrowid

    # добавляем создателя как участника и админа
    cursor.execute(
        """
        INSERT INTO team_members (user_id, team_id, is_team_admin)
        VALUES (?, ?, TRUE)
        """,
        (user_id, team_id)
    )

    conn.commit()
    conn.close()

    return team_id, team_code

def is_team_admin(user_id, team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT is_team_admin
        FROM team_members
        WHERE user_id=? AND team_id=?
        """,
        (user_id, team_id)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return False

    return bool(row[0])

def join_team(user_id, team_code):
    conn = get_db_connection()
    cursor = conn.cursor()

    # ищем команду по коду
    cursor.execute(
        "SELECT team_id FROM teams WHERE team_code=? AND is_active=TRUE",
        (team_code,)
    )

    team = cursor.fetchone()

    if not team:
        conn.close()
        return False, "Команда с таким кодом не найдена"

    team_id = team[0]

    # проверяем, не состоит ли пользователь уже в команде
    cursor.execute(
        "SELECT 1 FROM team_members WHERE user_id=? AND team_id=?",
        (user_id, team_id)
    )

    if cursor.fetchone():
        conn.close()
        return False, "Вы уже состоите в этой команде"

    # добавляем участника
    cursor.execute(
        """
        INSERT INTO team_members (user_id, team_id, is_team_admin)
        VALUES (?, ?, FALSE)
        """,
        (user_id, team_id)
    )

    conn.commit()
    conn.close()

    return True, "Вы успешно присоединились к команде"

def is_team_creator(user_id, team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT created_by
        FROM teams
        WHERE team_id=?
        """,
        (team_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return False

    return row[0] == user_id

def get_team_members(team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            tm.is_team_admin
        FROM team_members tm
        JOIN users u ON tm.user_id = u.user_id
        WHERE tm.team_id = ?
        ORDER BY tm.is_team_admin DESC
    """, (team_id,))

    rows = cursor.fetchall()
    conn.close()

    members = []

    for r in rows:
        members.append({
            "id": r[0],
            "username": r[1],
            "first_name": r[2],
            "last_name": r[3],
            "is_admin": bool(r[4])
        })

    return members

def get_member_info(user_id, team_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            tm.is_team_admin
        FROM team_members tm
        JOIN users u ON tm.user_id = u.user_id
        WHERE tm.user_id=? AND tm.team_id=?
    """, (user_id, team_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    name = row[1] or f"{row[2] or ''} {row[3] or ''}".strip() or f"ID: {row[0]}"

    return {
        "id": row[0],
        "name": name,
        "is_admin": bool(row[4]),
        "role_text": "Администратор" if row[4] else "Участник"
    }

def add_team_admin(member_id, team_id, requester_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT is_team_admin FROM team_members WHERE user_id=? AND team_id=?",
        (requester_id, team_id)
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return False, "Нет прав"

    cursor.execute(
        "UPDATE team_members SET is_team_admin=TRUE WHERE user_id=? AND team_id=?",
        (member_id, team_id)
    )

    conn.commit()
    conn.close()

    return True, "Пользователь назначен администратором"

def remove_team_admin(member_id, team_id, requester_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT is_team_admin FROM team_members WHERE user_id=? AND team_id=?",
        (requester_id, team_id)
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return False, "Нет прав"

    cursor.execute(
        "UPDATE team_members SET is_team_admin=FALSE WHERE user_id=? AND team_id=?",
        (member_id, team_id)
    )

    conn.commit()
    conn.close()

    return True, "Права администратора сняты"

def remove_team_member(member_id, team_id, requester_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT is_team_admin FROM team_members WHERE user_id=? AND team_id=?",
        (requester_id, team_id)
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return False, "Нет прав"

    cursor.execute(
        "DELETE FROM team_members WHERE user_id=? AND team_id=?",
        (member_id, team_id)
    )

    conn.commit()
    conn.close()

    return True, "Участник удалён из команды"



    return {
        'users': users_daily,
        'tasks': tasks_daily
    }
