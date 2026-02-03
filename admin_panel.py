import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLineEdit, QMessageBox, QTabWidget,
    QLabel, QFrame, QListWidgetItem, QDialog, QDialogButtonBox,
    QComboBox, QTextEdit, QStackedWidget, QSplitter, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QDateEdit, QTimeEdit, QDateTimeEdit, QCheckBox, QSpinBox,
    QToolButton, QMenu, QInputDialog, QSystemTrayIcon, QScrollArea,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDateTime, QSize, QDate
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QColor, QPalette, QLinearGradient,
    QRadialGradient, QConicalGradient, QAction, QPainter, QBrush,
    QPen, QPainterPath
)
from PyQt6.QtWidgets import QStyleFactory
from datetime import datetime, timedelta

DB_NAME = "tasks_bot.db"

class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 180, 255, 0.7),
                    stop:1 rgba(0, 100, 200, 0.7));
                border: 2px solid #00aaff;
                border-radius: 8px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 200, 255, 0.8),
                    stop:1 rgba(0, 120, 220, 0.8));
                border: 2px solid #00ccff;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 160, 230, 0.7),
                    stop:1 rgba(0, 80, 180, 0.7));
            }
        """)

class DatabaseManager:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Таблицы уже созданы ботом
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(DB_NAME)
    
    def execute_query(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.commit()
        conn.close()
        return result
    
    def get_all_teams(self):
        return self.execute_query('''
            SELECT t.team_id, t.team_name, t.team_code, t.description,
                   u.username, u.first_name, u.last_name,
                   (SELECT COUNT(*) FROM team_members WHERE team_id = t.team_id) as member_count,
                   (SELECT COUNT(*) FROM tasks WHERE team_id = t.team_id AND is_done = FALSE) as active_tasks
            FROM teams t
            JOIN users u ON t.created_by = u.user_id
            WHERE t.is_active = TRUE
            ORDER BY t.created_at DESC
        ''')
    
    def get_team_members(self, team_id):
        return self.execute_query('''
            SELECT u.user_id, u.username, u.first_name, u.last_name, tm.is_team_admin, tm.joined_at
            FROM users u
            JOIN team_members tm ON u.user_id = tm.user_id
            WHERE tm.team_id = ?
            ORDER BY tm.is_team_admin DESC, tm.joined_at
        ''', (team_id,))
    
    def get_team_tasks(self, team_id):
        return self.execute_query('''
            SELECT t.task_id, t.task_text, t.is_done, t.priority, t.deadline,
                   t.created_at, u.user_id, u.username, u.first_name
            FROM tasks t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.team_id = ?
            ORDER BY t.priority DESC, t.created_at DESC
        ''', (team_id,))
    
    def get_user_tasks(self, user_id, team_id=None):
        if team_id:
            return self.execute_query('''
                SELECT task_id, task_text, is_done, priority, deadline, created_at
                FROM tasks 
                WHERE user_id = ? AND team_id = ?
                ORDER BY priority DESC, created_at DESC
            ''', (user_id, team_id))
        else:
            return self.execute_query('''
                SELECT task_id, task_text, is_done, priority, deadline, created_at
                FROM tasks 
                WHERE user_id = ? AND team_id IS NULL
                ORDER BY priority DESC, created_at DESC
            ''', (user_id,))
    
    def get_team_info(self, team_id):
        result = self.execute_query('''
            SELECT t.team_id, t.team_name, t.team_code, t.description, 
                   t.created_at, u.user_id, u.username, u.first_name, u.last_name,
                   (SELECT COUNT(*) FROM team_members WHERE team_id = ?) as member_count
            FROM teams t
            JOIN users u ON t.created_by = u.user_id
            WHERE t.team_id = ?
        ''', (team_id, team_id))
        
        if result:
            team = result[0]
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
    
    def is_team_admin(self, user_id, team_id):
        result = self.execute_query('''
            SELECT is_team_admin FROM team_members 
            WHERE user_id = ? AND team_id = ?
        ''', (user_id, team_id))
        
        return result and bool(result[0][0])
    
    def is_team_creator(self, user_id, team_id):
        result = self.execute_query('SELECT created_by FROM teams WHERE team_id = ?', (team_id,))
        return result and result[0][0] == user_id
    
    def add_task(self, user_id, text, team_id=None, priority=1, deadline=None):
        self.execute_query('''
            INSERT INTO tasks (user_id, team_id, task_text, priority, deadline)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, team_id, text, priority, deadline))
    
    def update_task_status(self, task_id, is_done):
        self.execute_query('UPDATE tasks SET is_done = ? WHERE task_id = ?', (is_done, task_id))
    
    def delete_task(self, task_id):
        self.execute_query('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    
    def promote_to_admin(self, user_id, team_id, promoter_id):
        """Назначить участника админом команды"""
        if not self.is_team_creator(promoter_id, team_id):
            return False, "Только создатель команды может назначать админов"
        
        # Проверяем, что пользователь состоит в команде
        members = self.get_team_members(team_id)
        member_ids = [m[0] for m in members]
        
        if user_id not in member_ids:
            return False, "Пользователь не состоит в команде"
        
        self.execute_query('''
            UPDATE team_members 
            SET is_team_admin = TRUE 
            WHERE user_id = ? AND team_id = ?
        ''', (user_id, team_id))
        
        return True, "Пользователь назначен админом"
    
    def demote_admin(self, user_id, team_id, demoter_id):
        """Снять права админа"""
        if not self.is_team_creator(demoter_id, team_id):
            return False, "Только создатель команды может снимать админов"
        
        if self.is_team_creator(user_id, team_id):
            return False, "Нельзя снять права у создателя команды"
        
        self.execute_query('''
            UPDATE team_members 
            SET is_team_admin = FALSE 
            WHERE user_id = ? AND team_id = ?
        ''', (user_id, team_id))
        
        return True, "Права админа сняты"
    
    def remove_member(self, user_id, team_id, remover_id):
        """Удалить участника из команды"""
        if not self.is_team_admin(remover_id, team_id):
            return False, "Только админ команды может удалять участников"
        
        if self.is_team_creator(user_id, team_id):
            return False, "Нельзя удалить создателя команды"
        
        self.execute_query('DELETE FROM team_members WHERE user_id = ? AND team_id = ?', 
                          (user_id, team_id))
        
        return True, "Участник удален из команды"
    
    def create_team(self, name, description, creator_id):
        """Создать новую команду"""
        import random
        import string
        
        # Генерируем код команды
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        self.execute_query(
            'INSERT INTO teams (team_name, team_code, description, created_by) VALUES (?, ?, ?, ?)',
            (name, code, description, creator_id)
        )
        
        # Получаем ID созданной команды
        result = self.execute_query('SELECT last_insert_rowid()')
        team_id = result[0][0]
        
        # Добавляем создателя как админа
        self.execute_query(
            'INSERT INTO team_members (user_id, team_id, is_team_admin) VALUES (?, ?, ?)',
            (creator_id, team_id, True)
        )
        
        return team_id, code
    
    def get_stats(self):
        """Получение статистики"""
        stats = {}
        
        # Статистика команд
        result = self.execute_query('SELECT COUNT(*) FROM teams WHERE is_active = TRUE')
        stats['total_teams'] = result[0][0] if result else 0
        
        # Статистика задач
        result = self.execute_query('SELECT COUNT(*) FROM tasks')
        stats['total_tasks'] = result[0][0] if result else 0
        
        result = self.execute_query('SELECT COUNT(*) FROM tasks WHERE is_done = TRUE')
        stats['completed_tasks'] = result[0][0] if result else 0
        
        # Статистика пользователей
        result = self.execute_query('SELECT COUNT(*) FROM users')
        stats['total_users'] = result[0][0] if result else 0
        
        return stats

class TaskItemWidget(QWidget):
    task_toggled = pyqtSignal(int, bool)
    task_deleted = pyqtSignal(int)
    
    def __init__(self, task_data):
        super().__init__()
        self.task_id = task_data[0]
        self.is_done = bool(task_data[2])
        self.setup_ui(task_data)
    
    def setup_ui(self, task_data):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Чекбокс
        self.toggle_btn = QPushButton("✓" if self.is_done else "○")
        self.toggle_btn.setFixedSize(30, 30)
        self.update_toggle_style()
        self.toggle_btn.clicked.connect(self.toggle_task)
        
        # Текст задачи
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_label = QLabel(task_data[1])
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(f"""
            QLabel {{
                text-decoration: {'line-through' if self.is_done else 'none'};
                color: {'#888' if self.is_done else '#e0e0e0'};
                font-size: 13px;
            }}
        """)
        
        # Дополнительная информация
        info_text = ""
        if task_data[3]:  # priority
            priority_text = ["Высокий", "Средний", "Низкий"][task_data[3] - 1] if 1 <= task_data[3] <= 3 else "Обычный"
            info_text += f"Приоритет: {priority_text} | "
        
        if task_data[4]:  # deadline
            info_text += f"Дедлайн: {task_data[4]} | "
        
        info_text += f"Создано: {task_data[5][:16]}"
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #888; font-size: 10px;")
        
        text_layout.addWidget(self.text_label)
        text_layout.addWidget(info_label)
        
        # Кнопка удаления
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(30, 30)
        delete_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                color: #ff4444;
                border: 1px solid #ff4444;
                border-radius: 15px;
                background: rgba(255, 68, 68, 0.1);
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.2);
            }
        """)
        delete_btn.clicked.connect(self.delete_task)
        
        layout.addWidget(self.toggle_btn)
        layout.addWidget(text_widget, 1)
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)
        
        # Стиль
        self.setStyleSheet("""
            QWidget { 
                background: rgba(40, 45, 60, 0.6);
                border: 1px solid rgba(100, 100, 120, 0.4);
                border-radius: 8px;
            }
            QWidget:hover {
                background: rgba(50, 55, 70, 0.7);
                border: 1px solid rgba(120, 120, 150, 0.5);
            }
        """)
    
    def update_toggle_style(self):
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px;
                font-weight: bold;
                border: 2px solid {'#00ff88' if self.is_done else '#666'};
                border-radius: 15px;
                background: {'rgba(0, 255, 136, 0.2)' if self.is_done else 'rgba(100, 100, 100, 0.1)'};
                color: {'#00ff88' if self.is_done else '#888'};
            }}
        """)
    
    def toggle_task(self):
        self.is_done = not self.is_done
        self.toggle_btn.setText("✓" if self.is_done else "○")
        self.update_toggle_style()
        self.text_label.setStyleSheet(f"""
            QLabel {{
                text-decoration: {'line-through' if self.is_done else 'none'};
                color: {'#888' if self.is_done else '#e0e0e0'};
                font-size: 13px;
            }}
        """)
        self.task_toggled.emit(self.task_id, self.is_done)
    
    def delete_task(self):
        reply = QMessageBox.question(
            self, 
            "Удаление задачи", 
            "Вы уверены, что хотите удалить эту задачу?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.task_deleted.emit(self.task_id)

class TeamCard(QWidget):
    clicked = pyqtSignal(int)
    
    def __init__(self, team_data):
        super().__init__()
        self.team_id = team_data[0]
        self.setup_ui(team_data)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def setup_ui(self, team_data):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Название команды
        name_label = QLabel(f"🏢 {team_data[1]}")
        name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #00ccff;")
        
        # Код команды
        code_label = QLabel(f"🔑 Код: {team_data[2]}")
        code_label.setFont(QFont("Arial", 9))
        code_label.setStyleSheet("color: #aaa;")
        
        layout.addWidget(name_label)
        layout.addWidget(code_label)
        
        # Описание (если есть)
        if team_data[3]:
            desc_label = QLabel(team_data[3][:60] + ("..." if len(team_data[3]) > 60 else ""))
            desc_label.setFont(QFont("Arial", 9))
            desc_label.setStyleSheet("color: #888;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Создатель
        creator_text = f"👑 Создатель: "
        if team_data[4]:  # username
            creator_text += f"@{team_data[4]}"
        elif team_data[5] or team_data[6]:  # first_name or last_name
            creator_text += f"{team_data[5]} {team_data[6]}".strip()
        
        creator_label = QLabel(creator_text)
        creator_label.setFont(QFont("Arial", 8))
        creator_label.setStyleSheet("color: #666;")
        
        # Статистика
        stats_text = f"👥 Участников: {team_data[7]} | 📋 Задач: {team_data[8]}"
        stats_label = QLabel(stats_text)
        stats_label.setFont(QFont("Arial", 8))
        stats_label.setStyleSheet("color: #666;")
        
        layout.addWidget(creator_label)
        layout.addWidget(stats_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Стиль
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 35, 50, 0.8),
                    stop:1 rgba(20, 25, 40, 0.8));
                border: 2px solid #00aaff;
                border-radius: 10px;
            }
            QWidget:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40, 45, 60, 0.9),
                    stop:1 rgba(30, 35, 50, 0.9));
                border: 2px solid #00ccff;
            }
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.team_id)

class MemberItemWidget(QWidget):
    def __init__(self, member_data, current_user_id, team_id, db):
        super().__init__()
        self.member_id = member_data[0]
        self.current_user_id = current_user_id
        self.team_id = team_id
        self.db = db
        self.setup_ui(member_data)
    
    def setup_ui(self, member_data):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Иконка роли
        role_label = QLabel("👑" if member_data[4] else "👤")
        role_label.setFont(QFont("Arial", 14))
        
        # Информация об участнике
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Имя
        name = member_data[1] or f"{member_data[2]} {member_data[3]}".strip() or f"ID: {member_data[0]}"
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        
        # Роль и дата присоединения
        role_text = "Админ команды" if member_data[4] else "Участник"
        if member_data[5]:
            joined = member_data[5][:10]
            role_text += f" | Присоединился: {joined}"
        
        role_label_text = QLabel(role_text)
        role_label_text.setStyleSheet("color: #888; font-size: 10px;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(role_label_text)
        
        # Кнопки управления (только для админов команды и не для себя)
        if (self.db.is_team_admin(self.current_user_id, self.team_id) and 
            self.member_id != self.current_user_id):
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setSpacing(5)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            if member_data[4]:  # Если участник админ
                if not self.db.is_team_creator(self.member_id, self.team_id):
                    demote_btn = QPushButton("⬇ Снять")
                    demote_btn.setFixedSize(60, 25)
                    demote_btn.setStyleSheet("""
                        QPushButton {
                            font-size: 10px;
                            color: #ffaa00;
                            border: 1px solid #ffaa00;
                            border-radius: 4px;
                            background: rgba(255, 170, 0, 0.1);
                        }
                        QPushButton:hover {
                            background: rgba(255, 170, 0, 0.2);
                        }
                    """)
                    demote_btn.clicked.connect(lambda: self.demote_member())
                    btn_layout.addWidget(demote_btn)
            else:  # Если участник не админ
                promote_btn = QPushButton("⬆ Назначить")
                promote_btn.setFixedSize(80, 25)
                promote_btn.setStyleSheet("""
                    QPushButton {
                        font-size: 10px;
                        color: #00ff88;
                        border: 1px solid #00ff88;
                        border-radius: 4px;
                        background: rgba(0, 255, 136, 0.1);
                    }
                    QPushButton:hover {
                        background: rgba(0, 255, 136, 0.2);
                    }
                """)
                promote_btn.clicked.connect(lambda: self.promote_member())
                btn_layout.addWidget(promote_btn)
            
            # Кнопка удаления (кроме создателя)
            if not self.db.is_team_creator(self.member_id, self.team_id):
                remove_btn = QPushButton("🗑 Удалить")
                remove_btn.setFixedSize(60, 25)
                remove_btn.setStyleSheet("""
                    QPushButton {
                        font-size: 10px;
                        color: #ff4444;
                        border: 1px solid #ff4444;
                        border-radius: 4px;
                        background: rgba(255, 68, 68, 0.1);
                    }
                    QPushButton:hover {
                        background: rgba(255, 68, 68, 0.2);
                    }
                """)
                remove_btn.clicked.connect(lambda: self.remove_member())
                btn_layout.addWidget(remove_btn)
            
            info_layout.addWidget(btn_widget)
        
        layout.addWidget(role_label)
        layout.addWidget(info_widget, 1)
        
        self.setLayout(layout)
        
        # Стиль
        self.setStyleSheet("""
            QWidget { 
                background: rgba(40, 45, 60, 0.5);
                border: 1px solid rgba(100, 100, 120, 0.3);
                border-radius: 6px;
            }
        """)
    
    def promote_member(self):
        reply = QMessageBox.question(
            self, 
            "Назначение админом", 
            f"Назначить этого участника админом команды?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.db.promote_to_admin(
                self.member_id, self.team_id, self.current_user_id
            )
            if success:
                QMessageBox.information(self, "Успех", message)
                # Обновляем список участников
                self.parent().parent().parent().load_team_members()
            else:
                QMessageBox.warning(self, "Ошибка", message)
    
    def demote_member(self):
        reply = QMessageBox.question(
            self, 
            "Снятие прав админа", 
            f"Снять права админа у этого участника?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.db.demote_admin(
                self.member_id, self.team_id, self.current_user_id
            )
            if success:
                QMessageBox.information(self, "Успех", message)
                self.parent().parent().parent().load_team_members()
            else:
                QMessageBox.warning(self, "Ошибка", message)
    
    def remove_member(self):
        reply = QMessageBox.question(
            self, 
            "Удаление участника", 
            f"Удалить этого участника из команды?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.db.remove_member(
                self.member_id, self.team_id, self.current_user_id
            )
            if success:
                QMessageBox.information(self, "Успех", message)
                self.parent().parent().parent().load_team_members()
            else:
                QMessageBox.warning(self, "Ошибка", message)

class CreateTeamDialog(QDialog):
    def __init__(self, db, current_user_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user_id = current_user_id
        self.setWindowTitle("Создание команды")
        self.setFixedSize(500, 350)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Заголовок
        title = QLabel("🏗 СОЗДАНИЕ НОВОЙ КОМАНДЫ")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #00ff88;
                padding: 12px;
                background: rgba(20, 40, 20, 0.3);
                border: 2px solid #00ff88;
                border-radius: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Название команды
        name_layout = QHBoxLayout()
        name_label = QLabel("Название:")
        name_label.setFont(QFont("Arial", 11))
        name_label.setStyleSheet("color: #00ccff;")
        name_label.setFixedWidth(100)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Введите название команды...")
        
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        
        # Описание
        desc_label = QLabel("Описание:")
        desc_label.setFont(QFont("Arial", 11))
        desc_label.setStyleSheet("color: #00ccff;")
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Введите описание команды (необязательно)...")
        self.desc_input.setMaximumHeight(80)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addLayout(name_layout)
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
        # Стиль
        self.setStyleSheet("""
            QDialog {
                background: rgba(25, 30, 40, 0.95);
                border: 2px solid #00ccff;
                border-radius: 12px;
            }
            QLineEdit, QTextEdit {
                background: rgba(30, 35, 45, 0.7);
                border: 1px solid #666;
                border-radius: 6px;
                padding: 8px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #00ccff;
            }
        """)
    
    def get_team_data(self):
        return {
            "name": self.name_input.text().strip(),
            "description": self.desc_input.toPlainText().strip()
        }
    
    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название команды")
            return
        
        if len(name) < 3:
            QMessageBox.warning(self, "Ошибка", "Название должно быть не менее 3 символов")
            return
        
        super().accept()

class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_user_id = 1  # Для демонстрации
        self.current_team_id = None
        
        self.setWindowTitle("Task Manager - Управление командами")
        self.setGeometry(100, 100, 1100, 700)
        
        self.setup_ui()
        self.load_data()
        
        # Таймер для автообновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_data)
        self.timer.start(15000)  # Обновление каждые 15 секунд
    
    def setup_ui(self):
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Верхняя панель
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0066cc,
                    stop:1 #0099ff);
                border-bottom: 2px solid #00ccff;
            }
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # Логотип и заголовок
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setSpacing(10)
        
        icon_label = QLabel("🏢")
        icon_label.setFont(QFont("Arial", 20))
        
        title = QLabel("УПРАВЛЕНИЕ КОМАНДАМИ")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # Кнопка обновления
        self.refresh_btn = ModernButton("🔄 Обновить")
        self.refresh_btn.setFixedWidth(120)
        self.refresh_btn.clicked.connect(self.load_data)
        
        header_layout.addWidget(title_widget)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addWidget(header)
        
        # Основное содержание
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Левая панель - список команд
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(300)
        self.sidebar.setStyleSheet("""
            QWidget {
                background: rgba(20, 25, 35, 0.9);
                border-right: 1px solid rgba(0, 204, 255, 0.2);
            }
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(10)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        
        # Заголовок левой панели
        sidebar_title = QLabel("🏢 ВАШИ КОМАНДЫ")
        sidebar_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        sidebar_title.setStyleSheet("color: #00ccff; padding: 5px;")
        sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Кнопка создания команды
        self.create_team_btn = ModernButton("➕ Создать команду")
        self.create_team_btn.clicked.connect(self.create_team)
        
        # Список команд
        self.teams_list = QListWidget()
        self.teams_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px;
                border-radius: 5px;
                background: rgba(30, 35, 45, 0.5);
            }
            QListWidget::item:hover {
                background: rgba(40, 45, 55, 0.7);
            }
            QListWidget::item:selected {
                background: rgba(0, 180, 255, 0.3);
                border: 1px solid rgba(0, 180, 255, 0.5);
            }
        """)
        self.teams_list.itemClicked.connect(self.on_team_selected)
        
        # Статистика
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: rgba(30, 35, 45, 0.5);
                border: 1px solid rgba(0, 204, 255, 0.2);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        stats_layout = QVBoxLayout(stats_frame)
        
        self.stats_label = QLabel("Загрузка статистики...")
        self.stats_label.setStyleSheet("color: #aaa; font-size: 11px;")
        
        stats_layout.addWidget(QLabel("📊 Статистика:"))
        stats_layout.addWidget(self.stats_label)
        
        sidebar_layout.addWidget(sidebar_title)
        sidebar_layout.addWidget(self.create_team_btn)
        sidebar_layout.addWidget(self.teams_list, 1)
        sidebar_layout.addWidget(stats_frame)
        
        # Правая панель - детали команды
        self.details_panel = QStackedWidget()
        self.details_panel.setStyleSheet("""
            QStackedWidget {
                background: rgba(25, 30, 40, 0.9);
            }
        """)
        
        # Страница "Выберите команду"
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_label = QLabel("👈 Выберите команду из списка\nили создайте новую")
        empty_label.setFont(QFont("Arial", 14))
        empty_label.setStyleSheet("color: #888;")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_layout.addWidget(empty_label)
        
        # Страница деталей команды
        self.team_details_page = QWidget()
        team_details_layout = QVBoxLayout(self.team_details_page)
        team_details_layout.setSpacing(15)
        
        # Заголовок команды
        self.team_header = QLabel()
        self.team_header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.team_header.setStyleSheet("color: #00ccff; padding: 10px;")
        
        # Вкладки
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background: transparent;
                border: none;
            }
            QTabBar::tab {
                background: rgba(40, 45, 55, 0.7);
                border: 1px solid #444;
                padding: 8px 16px;
                margin-right: 3px;
                color: #aaa;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: rgba(0, 180, 255, 0.3);
                border: 1px solid #00aaff;
                color: #00ccff;
            }
        """)
        
        # Вкладка "Задачи"
        self.tasks_tab = QWidget()
        self.setup_tasks_tab()
        
        # Вкладка "Участники"
        self.members_tab = QWidget()
        self.setup_members_tab()
        
        # Вкладка "Управление"
        self.management_tab = QWidget()
        self.setup_management_tab()
        
        self.tabs.addTab(self.tasks_tab, "📋 Задачи")
        self.tabs.addTab(self.members_tab, "👥 Участники")
        self.tabs.addTab(self.management_tab, "⚙ Управление")
        
        team_details_layout.addWidget(self.team_header)
        team_details_layout.addWidget(self.tabs, 1)
        
        self.details_panel.addWidget(self.empty_page)
        self.details_panel.addWidget(self.team_details_page)
        
        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.details_panel, 1)
        
        main_layout.addWidget(content_widget, 1)
        
        # Статус бар
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: rgba(20, 25, 35, 0.9);
                color: #00ff88;
                border-top: 1px solid rgba(0, 204, 255, 0.3);
            }
        """)
        
        # Устанавливаем темную палитру
        self.set_dark_palette()
    
    def set_dark_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(15, 20, 30))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 30, 40))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 40, 50))
        palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Button, QColor(40, 45, 55))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 180, 255, 100))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)
    
    def setup_tasks_tab(self):
        layout = QVBoxLayout(self.tasks_tab)
        layout.setSpacing(10)
        
        # Панель управления задачами
        task_controls = QWidget()
        controls_layout = QHBoxLayout(task_controls)
        
        self.add_task_btn = ModernButton("➕ Добавить задачу")
        self.add_task_btn.clicked.connect(self.add_task)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все задачи", "Активные", "Завершенные"])
        self.filter_combo.setFixedWidth(150)
        
        controls_layout.addWidget(self.add_task_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Фильтр:"))
        controls_layout.addWidget(self.filter_combo)
        
        # Список задач
        self.tasks_list = QListWidget()
        self.tasks_list.setStyleSheet("""
            QListWidget {
                background: rgba(30, 35, 45, 0.5);
                border: 1px solid rgba(0, 204, 255, 0.2);
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                border: none;
                padding: 0px;
                margin: 4px;
            }
        """)
        
        layout.addWidget(task_controls)
        layout.addWidget(self.tasks_list, 1)
    
    def setup_members_tab(self):
        layout = QVBoxLayout(self.members_tab)
        layout.setSpacing(10)
        
        # Информация о команде
        self.members_info = QLabel()
        self.members_info.setStyleSheet("color: #aaa; padding: 5px;")
        
        # Список участников
        self.members_list = QListWidget()
        self.members_list.setStyleSheet("""
            QListWidget {
                background: rgba(30, 35, 45, 0.5);
                border: 1px solid rgba(0, 204, 255, 0.2);
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                border: none;
                padding: 0px;
                margin: 4px;
            }
        """)
        
        layout.addWidget(self.members_info)
        layout.addWidget(self.members_list, 1)
    
    def setup_management_tab(self):
        layout = QVBoxLayout(self.management_tab)
        layout.setSpacing(15)
        
        # Проверка прав доступа
        self.access_label = QLabel("Загрузка...")
        self.access_label.setStyleSheet("color: #ff4444; padding: 10px;")
        self.access_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Кнопки управления (будут показаны только админам)
        self.management_widget = QWidget()
        management_layout = QVBoxLayout(self.management_widget)
        management_layout.setSpacing(10)
        
        # Код команды
        code_frame = QFrame()
        code_frame.setStyleSheet("""
            QFrame {
                background: rgba(40, 35, 60, 0.5);
                border: 1px solid rgba(255, 0, 255, 0.3);
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        code_layout = QVBoxLayout(code_frame)
        
        code_title = QLabel("🔑 КОД КОМАНДЫ")
        code_title.setStyleSheet("color: #ff00ff; font-weight: bold;")
        
        self.code_label = QLabel("Загрузка...")
        self.code_label.setStyleSheet("color: #ff66ff; font-size: 18px; font-weight: bold;")
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        code_hint = QLabel("Поделитесь этим кодом, чтобы пригласить участников")
        code_hint.setStyleSheet("color: #aaa; font-size: 11px;")
        code_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        code_layout.addWidget(code_title)
        code_layout.addWidget(self.code_label)
        code_layout.addWidget(code_hint)
        
        # Действия
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background: rgba(40, 45, 60, 0.5);
                border: 1px solid rgba(0, 204, 255, 0.3);
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        actions_layout = QVBoxLayout(actions_frame)
        
        actions_title = QLabel("⚙ ДЕЙСТВИЯ")
        actions_title.setStyleSheet("color: #00ccff; font-weight: bold;")
        
        self.show_code_btn = ModernButton("🔑 Показать код команды")
        self.show_code_btn.clicked.connect(self.show_team_code)
        
        self.refresh_code_btn = ModernButton("🔄 Обновить код")
        self.refresh_code_btn.clicked.connect(self.refresh_team_code)
        
        self.delete_team_btn = ModernButton("🗑 Удалить команду")
        self.delete_team_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 68, 68, 0.3);
                border: 2px solid #ff4444;
                color: #ff4444;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.4);
            }
        """)
        self.delete_team_btn.clicked.connect(self.delete_team)
        
        actions_layout.addWidget(actions_title)
        actions_layout.addWidget(self.show_code_btn)
        actions_layout.addWidget(self.refresh_code_btn)
        actions_layout.addWidget(self.delete_team_btn)
        
        management_layout.addWidget(code_frame)
        management_layout.addWidget(actions_frame)
        management_layout.addStretch()
        
        layout.addWidget(self.access_label)
        layout.addWidget(self.management_widget)
        self.management_widget.hide()
    
    def load_data(self):
        self.load_teams()
        self.load_stats()
        
        if self.current_team_id:
            self.load_team_details(self.current_team_id)
    
    def load_teams(self):
        teams = self.db.get_all_teams()
        
        # Фильтруем только команды, в которых состоит пользователь
        user_teams = []
        for team in teams:
            team_id = team[0]
            members = self.db.get_team_members(team_id)
            member_ids = [m[0] for m in members]
            
            if self.current_user_id in member_ids:
                user_teams.append(team)
        
        self.teams_list.clear()
        
        for team in user_teams:
            team_id = team[0]
            team_name = team[1]
            is_admin = self.db.is_team_admin(self.current_user_id, team_id)
            admin_tag = " 👑" if is_admin else ""
            
            item_text = f"{team_name}{admin_tag}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, team_id)
            
            # Разный цвет для админов
            if is_admin:
                item.setForeground(QColor("#00ff88"))
            
            self.teams_list.addItem(item)
        
        # Выбираем первую команду, если ничего не выбрано
        if self.teams_list.count() > 0 and not self.current_team_id:
            self.teams_list.setCurrentRow(0)
            self.on_team_selected(self.teams_list.item(0))
    
    def load_stats(self):
        stats = self.db.get_stats()
        
        stats_text = f"""
        Всего команд: {stats.get('total_teams', 0)}
        Всего задач: {stats.get('total_tasks', 0)}
        Выполнено: {stats.get('completed_tasks', 0)}
        Пользователей: {stats.get('total_users', 0)}
        """
        
        self.stats_label.setText(stats_text)
    
    def on_team_selected(self, item):
        if not item:
            return
        
        # ОШИБКА ЗДЕСЬ: item.data(Qt.ItemDataRole.UserRole) может возвращать None или некорректное значение
        team_id = item.data(Qt.ItemDataRole.UserRole)
        
        # Добавляем проверку
        try:
            self.current_team_id = int(team_id) if team_id is not None else None
        except (TypeError, ValueError):
            print(f"Ошибка преобразования team_id: {team_id}")
            self.current_team_id = None
            return
        
        if not self.current_team_id:
            return
        
        # Переключаемся на страницу деталей
        self.details_panel.setCurrentIndex(1)
        
        # Загружаем детали команды
        self.load_team_details(self.current_team_id)
        
    def load_team_details(self, team_id):
        team_info = self.db.get_team_info(team_id)
        if not team_info:
            return
        
        # Обновляем заголовок
        is_admin = self.db.is_team_admin(self.current_user_id, team_id)
        admin_tag = " 👑" if is_admin else ""
        self.team_header.setText(f"🏢 {team_info['name']}{admin_tag}")
        
        # Загружаем задачи
        self.load_team_tasks(team_id)
        
        # Загружаем участников
        self.load_team_members()
        
        # Настраиваем вкладку управления
        self.setup_management_tab_for_team(team_id, team_info)
    
    def load_team_tasks(self, team_id):
        tasks = self.db.get_team_tasks(team_id)
        
        self.tasks_list.clear()
        
        for task in tasks:
            task_widget = TaskItemWidget(task)
            task_widget.task_toggled.connect(
                lambda task_id, is_done: self.db.update_task_status(task_id, is_done)
            )
            task_widget.task_deleted.connect(
                lambda task_id: self.on_task_deleted(task_id, team_id)
            )
            
            item = QListWidgetItem()
            item.setSizeHint(task_widget.sizeHint())
            
            self.tasks_list.addItem(item)
            self.tasks_list.setItemWidget(item, task_widget)
    
    def load_team_members(self):
        if not self.current_team_id:
            return
        
        members = self.db.get_team_members(self.current_team_id)
        team_info = self.db.get_team_info(self.current_team_id)
        
        # Обновляем информацию
        self.members_info.setText(
            f"👥 Участников: {len(members)} | "
            f"👑 Админов: {sum(1 for m in members if m[4])} | "
            f"🏢 Создатель: {team_info['creator_first_name'] or team_info['creator_username'] or 'Неизвестно'}"
        )
        
        self.members_list.clear()
        
        for member in members:
            member_widget = MemberItemWidget(
                member, self.current_user_id, self.current_team_id, self.db
            )
            
            item = QListWidgetItem()
            item.setSizeHint(member_widget.sizeHint())
            
            self.members_list.addItem(item)
            self.members_list.setItemWidget(item, member_widget)
    
    def setup_management_tab_for_team(self, team_id, team_info):
        is_admin = self.db.is_team_admin(self.current_user_id, team_id)
        is_creator = self.db.is_team_creator(self.current_user_id, team_id)
        
        if is_admin:
            self.access_label.hide()
            self.management_widget.show()
            
            # Показываем код команды
            self.code_label.setText(team_info['code'])
            
            # Настраиваем кнопки
            if is_creator:
                self.show_code_btn.show()
                self.refresh_code_btn.show()
                self.delete_team_btn.show()
            else:
                # Не создатель, только просмотр кода
                self.show_code_btn.hide()
                self.refresh_code_btn.hide()
                self.delete_team_btn.hide()
        else:
            self.access_label.setText("❌ У вас нет прав для управления этой командой")
            self.access_label.show()
            self.management_widget.hide()
    
    def create_team(self):
        dialog = CreateTeamDialog(self.db, self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            team_data = dialog.get_team_data()
            
            team_id, team_code = self.db.create_team(
                team_data["name"],
                team_data["description"],
                self.current_user_id
            )
            
            QMessageBox.information(
                self,
                "Команда создана",
                f"Команда '{team_data['name']}' успешно создана!\n\n"
                f"Код команды: {team_code}\n\n"
                f"Поделитесь этим кодом с участниками."
            )
            
            # Обновляем список команд
            self.load_data()
            
            # Выбираем новую команду
            for i in range(self.teams_list.count()):
                item = self.teams_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == team_id:
                    self.teams_list.setCurrentRow(i)
                    self.on_team_selected(item)
                    break
    
    def add_task(self):
        if not self.current_team_id:
            QMessageBox.warning(self, "Ошибка", "Выберите команду")
            return
        
        text, ok = QInputDialog.getText(
            self, 
            "Добавить задачу", 
            "Введите текст задачи:",
            QLineEdit.EchoMode.Normal
        )
        
        if ok and text:
            self.db.add_task(self.current_user_id, text, self.current_team_id)
            self.load_team_tasks(self.current_team_id)
    
    def on_task_deleted(self, task_id, team_id):
        self.db.delete_task(task_id)
        self.load_team_tasks(team_id)
    
    def show_team_code(self):
        if not self.current_team_id:
            return
        
        team_info = self.db.get_team_info(self.current_team_id)
        if team_info:
            QMessageBox.information(
                self,
                "Код команды",
                f"Код команды '{team_info['name']}':\n\n{team_info['code']}\n\n"
                f"Поделитесь этим кодом с участниками."
            )
    
    def refresh_team_code(self):
        # Обновление кода команды (требует реализации в DatabaseManager)
        QMessageBox.information(
            self,
            "Обновление кода",
            "Функция обновления кода команды будет реализована в будущем."
        )
    
    def delete_team(self):
        if not self.current_team_id:
            return
        
        reply = QMessageBox.question(
            self,
            "Удаление команды",
            "Вы уверены, что хотите удалить эту команду?\n\n"
            "Это действие удалит все задачи команды и отпишет всех участников.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Удаление команды (требует реализации в DatabaseManager)
            QMessageBox.information(
                self,
                "Удаление команды",
                "Функция удаления команды будет реализована в будущем."
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = TaskManager()
    window.show()
    
    sys.exit(app.exec())
