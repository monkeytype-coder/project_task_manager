import sys
import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QPushButton, QLineEdit, 
                             QMessageBox, QTabWidget, QLabel, QFrame, QListWidgetItem,
                             QDialog, QDialogButtonBox, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap

DB_NAME = "tasks_bot.db"

class DatabaseManager:
    """Класс для работы с базой данных"""
    
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
    
    def get_connection(self):
        return sqlite3.connect(DB_NAME)
    
    def ensure_user_exists(self, user_id, username=None, first_name=None, last_name=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
            (user_id, username, first_name, last_name)
        )
        conn.commit()
        conn.close()
    
    def get_user_tasks(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT task_id, task_text, is_done FROM tasks WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        )
        tasks = cursor.fetchall()
        conn.close()
        return [{"id": task[0], "text": task[1], "done": bool(task[2])} for task in tasks]
    
    def add_task(self, user_id, task_text):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO tasks (user_id, task_text) VALUES (?, ?)',
            (user_id, task_text)
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def update_task_status(self, task_id, is_done):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tasks SET is_done = ? WHERE task_id = ?',
            (is_done, task_id)
        )
        conn.commit()
        conn.close()
    
    def delete_task(self, task_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name FROM users')
        users = cursor.fetchall()
        conn.close()
        return [{"id": user[0], "username": user[1], "first_name": user[2], "last_name": user[3]} for user in users]
    
    def is_admin(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def add_admin(self, user_id, added_by=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO admins (user_id, added_by) VALUES (?, ?)',
            (user_id, added_by)
        )
        conn.commit()
        conn.close()


class TaskItemWidget(QWidget):
    """Виджет для отображения отдельной задачи"""
    
    task_toggled = pyqtSignal(int, bool)  # task_id, is_done
    task_deleted = pyqtSignal(int)  # task_id
    
    def __init__(self, task_id, text, is_done):
        super().__init__()
        self.task_id = task_id
        self.is_done = is_done
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Чекбокс выполнения
        self.toggle_btn = QPushButton("✓" if is_done else "○")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; border: 2px solid {'#4CAF50' if is_done else '#ccc'}; "
            f"background-color: {'#E8F5E8' if is_done else 'white'}; }}"
        )
        self.toggle_btn.clicked.connect(self.toggle_task)
        
        # Текст задачи
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(
            f"QLabel {{ text-decoration: {'line-through' if is_done else 'none'}; "
            f"color: {'#888' if is_done else 'black'}; font-size: 14px; }}"
        )
        
        # Кнопка удаления
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(30, 30)
        delete_btn.setStyleSheet("QPushButton { font-size: 14px; color: #ff4444; }")
        delete_btn.clicked.connect(self.delete_task)
        
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)
        self.setStyleSheet("QWidget { border: 1px solid #eee; border-radius: 5px; margin: 2px; }")
    
    def toggle_task(self):
        self.is_done = not self.is_done
        self.toggle_btn.setText("✓" if self.is_done else "○")
        self.toggle_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; border: 2px solid {'#4CAF50' if self.is_done else '#ccc'}; "
            f"background-color: {'#E8F5E8' if self.is_done else 'white'}; }}"
        )
        self.text_label.setStyleSheet(
            f"QLabel {{ text-decoration: {'line-through' if self.is_done else 'none'}; "
            f"color: {'#888' if self.is_done else 'black'}; font-size: 14px; }}"
        )
        self.task_toggled.emit(self.task_id, self.is_done)
    
    def delete_task(self):
        reply = QMessageBox.question(self, "Удаление задачи", "Вы уверены, что хотите удалить эту задачу?")
        if reply == QMessageBox.StandardButton.Yes:
            self.task_deleted.emit(self.task_id)


class AddTaskDialog(QDialog):
    """Диалог добавления новой задачи"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить задачу")
        self.setFixedSize(400, 150)
        
        layout = QVBoxLayout()
        
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Введите текст задачи...")
        self.task_input.setStyleSheet("QLineEdit { padding: 10px; font-size: 14px; }")
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(QLabel("Текст задачи:"))
        layout.addWidget(self.task_input)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_task_text(self):
        return self.task_input.text().strip()


class AddAdminDialog(QDialog):
    """Диалог добавления администратора"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить администратора")
        self.setFixedSize(400, 150)
        
        layout = QVBoxLayout()
        
        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("Введите ID пользователя...")
        self.user_id_input.setStyleSheet("QLineEdit { padding: 10px; font-size: 14px; }")
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(QLabel("ID пользователя:"))
        layout.addWidget(self.user_id_input)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_user_id(self):
        return self.user_id_input.text().strip()


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_user_id = 1  # По умолчанию
        self.is_admin_mode = False
        
        self.setWindowTitle("Менеджер задач - Админ Панель")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.setup_ui()
        self.load_users()
        self.load_tasks()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Заголовок
        title = QLabel("Админ Панель - Менеджер задач")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("padding: 20px; color: #333;")
        layout.addWidget(title)
        
        # Вкладки
        self.tabs = QTabWidget()
        
        # Вкладка задач
        self.tasks_tab = QWidget()
        self.setup_tasks_tab()
        self.tabs.addTab(self.tasks_tab, "📋 Задачи")
        
        # Вкладка пользователей
        self.users_tab = QWidget()
        self.setup_users_tab()
        self.tabs.addTab(self.users_tab, "👥 Пользователи")
        
        # Вкладка администрирования
        self.admin_tab = QWidget()
        self.setup_admin_tab()
        self.tabs.addTab(self.admin_tab, "⚙ Администрирование")
        
        layout.addWidget(self.tabs)
    
    def setup_tasks_tab(self):
        layout = QVBoxLayout()
        
        # Панель выбора пользователя
        user_panel = QHBoxLayout()
        user_panel.addWidget(QLabel("Пользователь:"))
        
        self.user_combo = QComboBox()
        self.user_combo.currentTextChanged.connect(self.on_user_changed)
        user_panel.addWidget(self.user_combo, 1)
        
        user_panel.addStretch()
        
        self.add_task_btn = QPushButton("➕ Добавить задачу")
        self.add_task_btn.clicked.connect(self.show_add_task_dialog)
        user_panel.addWidget(self.add_task_btn)
        
        layout.addLayout(user_panel)
        
        # Список задач
        self.tasks_list = QListWidget()
        self.tasks_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:last {
                border-bottom: none;
            }
        """)
        layout.addWidget(self.tasks_list)
        
        # Статистика
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("padding: 10px; color: #666;")
        layout.addWidget(self.stats_label)
        
        self.tasks_tab.setLayout(layout)
    
    def setup_users_tab(self):
        layout = QVBoxLayout()
        
        # Заголовок
        users_header = QLabel("Зарегистрированные пользователи")
        users_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(users_header)
        
        # Список пользователей
        self.users_list = QListWidget()
        self.users_list.itemDoubleClicked.connect(self.on_user_double_clicked)
        layout.addWidget(self.users_list)
        
        self.users_tab.setLayout(layout)
    
    def setup_admin_tab(self):
        layout = QVBoxLayout()
        
        # Секция добавления админа
        admin_section = QFrame()
        admin_section.setFrameStyle(QFrame.Shape.Box)
        admin_section.setStyleSheet("QFrame { padding: 15px; background-color: #f9f9f9; }")
        admin_layout = QVBoxLayout(admin_section)
        
        admin_title = QLabel("Управление администраторами")
        admin_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        admin_layout.addWidget(admin_title)
        
        self.add_admin_btn = QPushButton("👑 Добавить администратора")
        self.add_admin_btn.clicked.connect(self.show_add_admin_dialog)
        admin_layout.addWidget(self.add_admin_btn)
        
        # Список админов
        admin_layout.addWidget(QLabel("Текущие администраторы:"))
        self.admins_list = QListWidget()
        admin_layout.addWidget(self.admins_list)
        
        layout.addWidget(admin_section)
        layout.addStretch()
        
        self.admin_tab.setLayout(layout)
    
    def load_users(self):
        """Загрузка списка пользователей"""
        users = self.db.get_all_users()
        self.user_combo.clear()
        
        for user in users:
            display_name = self.get_user_display_name(user)
            self.user_combo.addItem(display_name, user['id'])
        
        self.update_users_list()
        self.update_admins_list()
    
    def load_tasks(self):
        """Загрузка задач текущего пользователя"""
        if hasattr(self, 'user_combo') and self.user_combo.currentData():
            user_id = self.user_combo.currentData()
            self.current_user_id = user_id
            tasks = self.db.get_user_tasks(user_id)
            
            self.tasks_list.clear()
            
            for task in tasks:
                self.add_task_to_list(task)
            
            self.update_stats()
    
    def add_task_to_list(self, task):
        """Добавление задачи в список"""
        task_widget = TaskItemWidget(task['id'], task['text'], task['done'])
        task_widget.task_toggled.connect(self.on_task_toggled)
        task_widget.task_deleted.connect(self.on_task_deleted)
        
        item = QListWidgetItem()
        item.setSizeHint(task_widget.sizeHint())
        
        self.tasks_list.addItem(item)
        self.tasks_list.setItemWidget(item, task_widget)
    
    def update_stats(self):
        """Обновление статистики"""
        tasks = self.db.get_user_tasks(self.current_user_id)
        total = len(tasks)
        completed = sum(1 for task in tasks if task['done'])
        
        self.stats_label.setText(
            f"Всего задач: {total} | Выполнено: {completed} | "
            f"Осталось: {total - completed} | "
            f"Прогресс: {completed}/{total} ({completed/total*100:.1f}%)" if total > 0 else "Прогресс: 0%"
        )
    
    def update_users_list(self):
        """Обновление списка пользователей"""
        users = self.db.get_all_users()
        self.users_list.clear()
        
        for user in users:
            display_name = self.get_user_display_name(user)
            task_count = len(self.db.get_user_tasks(user['id']))
            completed_count = sum(1 for task in self.db.get_user_tasks(user['id']) if task['done'])
            
            item_text = f"{display_name} | Задачи: {task_count} | Выполнено: {completed_count}"
            if self.db.is_admin(user['id']):
                item_text += " 👑"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, user['id'])
            self.users_list.addItem(item)
    
    def update_admins_list(self):
        """Обновление списка администраторов"""
        users = self.db.get_all_users()
        self.admins_list.clear()
        
        for user in users:
            if self.db.is_admin(user['id']):
                display_name = self.get_user_display_name(user)
                self.admins_list.addItem(display_name)
    
    def get_user_display_name(self, user):
        """Получение отображаемого имени пользователя"""
        if user['username']:
            return f"@{user['username']}"
        elif user['first_name'] or user['last_name']:
            return f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        else:
            return f"User {user['id']}"
    
    def on_user_changed(self):
        """Обработчик смены пользователя"""
        self.load_tasks()
    
    def on_user_double_clicked(self, item):
        """Обработчик двойного клика по пользователю"""
        user_id = item.data(Qt.ItemDataRole.UserRole)
        # Находим индекс пользователя в комбобоксе
        for i in range(self.user_combo.count()):
            if self.user_combo.itemData(i) == user_id:
                self.user_combo.setCurrentIndex(i)
                self.tabs.setCurrentIndex(0)  # Переключаемся на вкладку задач
                break
    
    def on_task_toggled(self, task_id, is_done):
        """Обработчик переключения статуса задачи"""
        self.db.update_task_status(task_id, is_done)
        self.update_stats()
        self.update_users_list()
    
    def on_task_deleted(self, task_id):
        """Обработчик удаления задачи"""
        self.db.delete_task(task_id)
        self.load_tasks()
        self.update_users_list()
    
    def show_add_task_dialog(self):
        """Показать диалог добавления задачи"""
        dialog = AddTaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task_text = dialog.get_task_text()
            if task_text:
                self.db.add_task(self.current_user_id, task_text)
                self.load_tasks()
                self.update_users_list()
    
    def show_add_admin_dialog(self):
        """Показать диалог добавления администратора"""
        dialog = AddAdminDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_id_text = dialog.get_user_id()
            if user_id_text:
                try:
                    user_id = int(user_id_text)
                    # Создаем пользователя если не существует
                    self.db.ensure_user_exists(user_id)
                    self.db.add_admin(user_id)
                    self.load_users()
                    QMessageBox.information(self, "Успех", f"Пользователь {user_id} назначен администратором")
                except ValueError:
                    QMessageBox.warning(self, "Ошибка", "ID пользователя должен быть числом")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Установка стиля приложения
    app.setStyle('Fusion')
    
    window = TaskManager()
    window.show()
    
    sys.exit(app.exec())
