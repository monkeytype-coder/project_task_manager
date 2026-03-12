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
    
    return {
        'users': users_daily,
        'tasks': tasks_daily
    }
