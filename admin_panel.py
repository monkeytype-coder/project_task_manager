# admin_panel.py
import sys
import sqlite3
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QHeaderView, QMessageBox, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QSplitter, QTextEdit, QComboBox, QLineEdit,
    QDateEdit, QSpinBox, QCheckBox, QMenuBar, QMenu, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette, QAction, QLinearGradient, QBrush, QPainter
import database as db

# Современная цветовая схема
COLORS = {
    'primary': '#4361ee',
    'secondary': '#3f37c9',
    'success': '#4cc9f0',
    'danger': '#f72585',
    'warning': '#f8961e',
    'info': '#4895ef',
    'light': '#f8f9fa',
    'dark': '#212529',
    'white': '#ffffff',
    'gray-100': '#f8f9fa',
    'gray-200': '#e9ecef',
    'gray-300': '#dee2e6',
    'gray-600': '#6c757d',
    'gray-700': '#495057',
    'gray-800': '#343a40',
    'gradient-start': '#4361ee',
    'gradient-end': '#4cc9f0'
}

class GradientWidget(QWidget):
    """Виджет с градиентным фоном"""
    def __init__(self, color_start, color_end, parent=None):
        super().__init__(parent)
        self.color_start = color_start
        self.color_end = color_end
        
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(self.color_start))
        gradient.setColorAt(1, QColor(self.color_end))
        painter.fillRect(self.rect(), gradient)

class ModernCard(QFrame):
    """Современная карточка с анимацией"""
    def __init__(self, title, value, icon="📊", color=COLORS['primary'], parent=None):
        super().__init__(parent)
        self.setObjectName("modernCard")
        self.setStyleSheet(f"""
            #modernCard {{
                background-color: white;
                border-radius: 20px;
                border: 1px solid {COLORS['gray-200']};
            }}
            #modernCard:hover {{
                border: 2px solid {color};
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        
        # Добавляем анимацию при наведении
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Верхняя часть с иконкой и заголовком
        top_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 24))
        icon_label.setStyleSheet(f"color: {color};")
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 12))
        title_label.setStyleSheet(f"color: {COLORS['gray-600']}; font-weight: 500;")
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # Значение
        value_label = QLabel(str(value))
        value_label.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        # Нижняя подпись
        change_label = QLabel("+12.5% с прошлого месяца")
        change_label.setFont(QFont("Segoe UI", 10))
        change_label.setStyleSheet(f"color: {COLORS['success']};")
        change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(change_label)
        
        self.setLayout(layout)
        self.setMinimumWidth(220)
        self.setMaximumHeight(160)
        
    def enterEvent(self, event):
        self.animation.setEndValue(self.geometry().adjusted(-5, -5, 5, 5))
        self.animation.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.animation.setEndValue(self.geometry().adjusted(5, 5, -5, -5))
        self.animation.start()
        super().leaveEvent(event)

class ModernTable(QTableWidget):
    """Современная таблица с стилизацией"""
    def __init__(self):
        super().__init__()
        self.setup_style()
        
    def setup_style(self):
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                alternate-background-color: {COLORS['gray-100']};
                gridline-color: {COLORS['gray-200']};
                border: 1px solid {COLORS['gray-200']};
                border-radius: 10px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {COLORS['gray-200']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary']}20;
                color: {COLORS['dark']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['gray-100']};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {COLORS['primary']};
                font-weight: bold;
                font-size: 12px;
                color: {COLORS['gray-700']};
            }}
            QHeaderView::section:horizontal {{
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['gray-100']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['gray-300']};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['gray-600']};
            }}
        """)
        
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)

class SearchBar(QWidget):
    """Современная поисковая строка"""
    def __init__(self, placeholder="Поиск..."):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(placeholder)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {COLORS['gray-200']};
                border-radius: 25px;
                padding: 10px 20px;
                font-size: 13px;
                background-color: white;
                selection-background-color: {COLORS['primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
                box-shadow: 0 0 10px {COLORS['primary']}40;
            }}
        """)
        
        layout.addWidget(self.search_input)
        self.setLayout(layout)
        
    def text(self):
        return self.search_input.text()
        
    def textChanged(self, callback):
        self.search_input.textChanged.connect(callback)

class ModernButton(QPushButton):
    """Современная кнопка с анимацией"""
    def __init__(self, text, icon="", color=COLORS['primary']):
        super().__init__(text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
                transform: translateY(-2px);
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.2)};
                transform: translateY(0px);
            }}
        """)
        
    def darken_color(self, color, amount=0.1):
        # Упрощенная функция затемнения цвета
        return color

class ActivityTimeline(QWidget):
    """Временная шкала активности"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(10)
        self.items_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['gray-100']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['gray-300']};
                border-radius: 4px;
            }}
        """)
        
        content = QWidget()
        content.setLayout(self.items_layout)
        scroll.setWidget(content)
        
        layout.addWidget(scroll)
        self.setLayout(layout)
        
    def add_activity(self, activity):
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 10px;
                border: 1px solid {COLORS['gray-200']};
                padding: 5px;
            }}
            QFrame:hover {{
                border-color: {COLORS['primary']};
                background-color: {COLORS['gray-100']};
            }}
        """)
        
        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(15, 10, 15, 10)
        
        # Иконка
        icon_label = QLabel(activity['icon'])
        icon_label.setFont(QFont("Segoe UI", 16))
        icon_label.setStyleSheet(f"color: {activity['color']};")
        item_layout.addWidget(icon_label)
        
        # Текст
        text_layout = QVBoxLayout()
        
        time_label = QLabel(activity['time'])
        time_label.setFont(QFont("Segoe UI", 10))
        time_label.setStyleSheet(f"color: {COLORS['gray-600']};")
        text_layout.addWidget(time_label)
        
        desc_label = QLabel(activity['description'])
        desc_label.setFont(QFont("Segoe UI", 12))
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        item_layout.addLayout(text_layout)
        item_layout.addStretch()
        
        item.setLayout(item_layout)
        self.items_layout.insertWidget(self.items_layout.count() - 1, item)

class AdminPanel(QMainWindow):
    """Главное окно админ-панели"""
    
    refresh_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("НАВИГАТОР ЗАДАЧ - Админ панель")
        self.setGeometry(100, 100, 1400, 800)
        
        # Применяем общий стиль
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['gray-100']};
            }}
            QWidget {{
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                background-color: transparent;
                padding: 10px 20px;
                margin-right: 5px;
                border: none;
                font-size: 13px;
                font-weight: 500;
                color: {COLORS['gray-600']};
            }}
            QTabBar::tab:selected {{
                color: {COLORS['primary']};
                border-bottom: 3px solid {COLORS['primary']};
            }}
            QTabBar::tab:hover {{
                color: {COLORS['primary']};
                background-color: {COLORS['primary']}10;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {COLORS['gray-200']};
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Верхняя панель с заголовком
        self.create_header(main_layout)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: white;
                border-top: 1px solid {COLORS['gray-200']};
                padding: 5px;
            }}
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("✅ Система готова к работе")
        
        # Меню
        self.create_menu()
        
        # Панель статистики
        self.stats_widget = QWidget()
        stats_layout = QHBoxLayout(self.stats_widget)
        stats_layout.setSpacing(20)
        self.stats_cards = []
        main_layout.addWidget(self.stats_widget)
        
        # Табы
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 10))
        
        # Вкладка "Обзор"
        self.overview_tab = self.create_overview_tab()
        self.tabs.addTab(self.overview_tab, "🏠 Обзор")
        
        # Вкладка "Пользователи"
        self.users_tab = self.create_users_tab()
        self.tabs.addTab(self.users_tab, "👥 Пользователи")
        
        # Вкладка "Команды"
        self.teams_tab = self.create_teams_tab()
        self.tabs.addTab(self.teams_tab, "🏢 Команды")
        
        # Вкладка "Задачи"
        self.tasks_tab = self.create_tasks_tab()
        self.tabs.addTab(self.tasks_tab, "📋 Задачи")
        
        # Вкладка "Статистика"
        self.stats_tab = self.create_stats_tab()
        self.tabs.addTab(self.stats_tab, "📊 Статистика")
        
        main_layout.addWidget(self.tabs)
        
        # Нижняя панель с кнопкой обновления
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.refresh_btn = ModernButton("🔄 Обновить данные", color=COLORS['primary'])
        self.refresh_btn.clicked.connect(self.refresh_data)
        bottom_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(bottom_layout)
        
        # Таймер автообновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)  # Обновление каждые 30 секунд
        
        # Первоначальная загрузка данных
        self.refresh_data()
        
    def create_header(self, layout):
        """Создание красивого заголовка"""
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['gradient-start']}, stop:1 {COLORS['gradient-end']});
                border-radius: 15px;
                padding: 20px;
            }}
        """)
        
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📊 Административная панель НАВИГАТОР ЗАДАЧ")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        date_label = QLabel(datetime.now().strftime("%d %B %Y"))
        date_label.setFont(QFont("Segoe UI", 12))
        date_label.setStyleSheet("color: white; opacity: 0.9;")
        header_layout.addWidget(date_label)
        
        header.setLayout(header_layout)
        layout.addWidget(header)
        
    def create_menu(self):
        """Создание красивого меню"""
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: white;
                border-bottom: 1px solid {COLORS['gray-200']};
                padding: 5px;
            }}
            QMenuBar::item {{
                padding: 8px 15px;
                border-radius: 5px;
            }}
            QMenuBar::item:selected {{
                background-color: {COLORS['primary']}20;
            }}
            QMenu {{
                background-color: white;
                border: 1px solid {COLORS['gray-200']};
                border-radius: 10px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 30px 8px 20px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['primary']}20;
            }}
        """)
        
        # Файл
        file_menu = menubar.addMenu("📁 Файл")
        
        refresh_action = QAction("🔄 Обновить", self)
        refresh_action.triggered.connect(self.refresh_data)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("🚪 Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Инструменты
        tools_menu = menubar.addMenu("🔧 Инструменты")
        
        backup_action = QAction("💾 Создать бэкап", self)
        backup_action.triggered.connect(self.backup_database)
        tools_menu.addAction(backup_action)
        
        # Справка
        help_menu = menubar.addMenu("❓ Справка")
        
        about_action = QAction("ℹ️ О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_overview_tab(self):
        """Вкладка обзора"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Статистика будет добавлена позже в refresh_data
        
        # Активность
        activity_group = QGroupBox("📋 Последние действия")
        activity_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 15px;
                border: 1px solid {COLORS['gray-200']};
                margin-top: 10px;
                padding-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: {COLORS['gray-700']};
            }}
        """)
        
        activity_layout = QVBoxLayout()
        self.activity_timeline = ActivityTimeline()
        activity_layout.addWidget(self.activity_timeline)
        activity_group.setLayout(activity_layout)
        
        layout.addWidget(activity_group)
        
        # Быстрые действия
        actions_group = QGroupBox("⚡ Быстрые действия")
        actions_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 15px;
                border: 1px solid {COLORS['gray-200']};
                margin-top: 10px;
                padding-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: {COLORS['gray-700']};
            }}
        """)
        
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        btn1 = ModernButton("👥 Все пользователи", color=COLORS['info'])
        btn1.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        actions_layout.addWidget(btn1)
        
        btn2 = ModernButton("🏢 Все команды", color=COLORS['success'])
        btn2.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        actions_layout.addWidget(btn2)
        
        btn3 = ModernButton("📊 Детальная статистика", color=COLORS['warning'])
        btn3.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        actions_layout.addWidget(btn3)
        
        btn4 = ModernButton("📥 Экспорт данных", color=COLORS['primary'])
        btn4.clicked.connect(self.export_all)
        actions_layout.addWidget(btn4)
        
        actions_layout.addStretch()
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        return tab
        
    def create_users_tab(self):
        """Вкладка пользователей"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Верхняя панель с поиском
        top_panel = QFrame()
        top_panel.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 15px;
                padding: 15px;
            }}
        """)
        
        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(10, 10, 10, 10)
        
        # Поиск
        search_label = QLabel("🔍")
        search_label.setFont(QFont("Segoe UI", 14))
        top_layout.addWidget(search_label)
        
        self.user_search = QLineEdit()
        self.user_search.setPlaceholderText("Поиск по имени или username...")
        self.user_search.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {COLORS['gray-200']};
                border-radius: 25px;
                padding: 10px 20px;
                font-size: 13px;
                min-width: 300px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.user_search.textChanged.connect(self.filter_users)
        top_layout.addWidget(self.user_search)
        
        top_layout.addStretch()
        
        # Статистика пользователей
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        total_label = QLabel("Всего: 0")
        total_label.setStyleSheet(f"color: {COLORS['primary']}; font-weight: bold;")
        stats_layout.addWidget(total_label)
        
        active_label = QLabel("Активных: 0")
        active_label.setStyleSheet(f"color: {COLORS['success']};")
        stats_layout.addWidget(active_label)
        
        top_layout.addLayout(stats_layout)
        
        export_btn = ModernButton("📥 Экспорт", color=COLORS['success'])
        export_btn.clicked.connect(self.export_users)
        top_layout.addWidget(export_btn)
        
        layout.addWidget(top_panel)
        
        # Таблица пользователей
        self.users_table = ModernTable()
        self.users_table.setColumnCount(8)
        self.users_table.setHorizontalHeaderLabels(
            ["ID", "Username", "Имя", "Фамилия", "Дата регистрации", "Команд", "Задач", "Выполнено"]
        )
        layout.addWidget(self.users_table)
        
        return tab
        
    def create_teams_tab(self):
        """Вкладка команд"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Верхняя панель
        top_panel = QFrame()
        top_panel.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 15px;
                padding: 15px;
            }}
        """)
        
        top_layout = QHBoxLayout(top_panel)
        
        search_label = QLabel("🔍")
        search_label.setFont(QFont("Segoe UI", 14))
        top_layout.addWidget(search_label)
        
        self.team_search = QLineEdit()
        self.team_search.setPlaceholderText("Поиск по названию команды...")
        self.team_search.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {COLORS['gray-200']};
                border-radius: 25px;
                padding: 10px 20px;
                font-size: 13px;
                min-width: 300px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.team_search.textChanged.connect(self.filter_teams)
        top_layout.addWidget(self.team_search)
        
        top_layout.addStretch()
        
        export_btn = ModernButton("📥 Экспорт", color=COLORS['success'])
        export_btn.clicked.connect(self.export_teams)
        top_layout.addWidget(export_btn)
        
        layout.addWidget(top_panel)
        
        # Таблица команд
        self.teams_table = ModernTable()
        self.teams_table.setColumnCount(8)
        self.teams_table.setHorizontalHeaderLabels(
            ["ID", "Название", "Код", "Создатель", "Дата создания", "Участников", "Задач", "Выполнено"]
        )
        layout.addWidget(self.teams_table)
        
        return tab
        
    def create_tasks_tab(self):
        """Вкладка задач"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Панель фильтров
        filter_panel = QFrame()
        filter_panel.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 15px;
                padding: 15px;
            }}
        """)
        
        filter_layout = QHBoxLayout(filter_panel)
        
        filter_layout.addWidget(QLabel("📌 Статус:"))
        self.task_status = QComboBox()
        self.task_status.addItems(["Все", "Активные", "Выполненные"])
        self.task_status.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid {COLORS['gray-200']};
                border-radius: 8px;
                padding: 8px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {COLORS['gray-600']};
                margin-right: 5px;
            }}
        """)
        self.task_status.currentTextChanged.connect(self.filter_tasks)
        filter_layout.addWidget(self.task_status)
        
        filter_layout.addWidget(QLabel("⚡ Приоритет:"))
        self.task_priority = QComboBox()
        self.task_priority.addItems(["Все", "Высокий", "Средний", "Низкий"])
        self.task_priority.setStyleSheet(self.task_status.styleSheet())
        self.task_priority.currentTextChanged.connect(self.filter_tasks)
        filter_layout.addWidget(self.task_priority)
        
        filter_layout.addStretch()
        
        layout.addWidget(filter_panel)
        
        # Таблица задач
        self.tasks_table = ModernTable()
        self.tasks_table.setColumnCount(7)
        self.tasks_table.setHorizontalHeaderLabels(
            ["ID", "Задача", "Автор", "Команда", "Приоритет", "Статус", "Создана"]
        )
        layout.addWidget(self.tasks_table)
        
        return tab
        
    def create_stats_tab(self):
        """Вкладка статистики"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # График активности (упрощенный)
        stats_group = QGroupBox("📈 Статистика активности")
        stats_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 15px;
                border: 1px solid {COLORS['gray-200']};
                margin-top: 10px;
                padding-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: {COLORS['gray-700']};
            }}
        """)
        
        stats_layout = QVBoxLayout()
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet(f"""
            QTextEdit {{
                border: 2px solid {COLORS['gray-200']};
                border-radius: 10px;
                padding: 15px;
                font-family: 'Segoe UI';
                font-size: 12px;
                line-height: 1.6;
                background-color: {COLORS['gray-100']};
            }}
        """)
        stats_layout.addWidget(self.stats_text)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        return tab
        
    def refresh_data(self):
        """Обновление всех данных"""
        try:
            # Общая статистика
            total_users = db.get_total_users()
            total_teams = db.get_total_teams()
            total_tasks = db.get_total_tasks()
            completed_tasks = db.get_completed_tasks()
            
            # Обновляем карточки статистики
            self.update_stats_cards(total_users, total_teams, total_tasks, completed_tasks)
            
            # Детальные данные
            users = db.get_users_stats()
            teams = db.get_teams_stats()
            activities = db.get_recent_activity()
            
            # Обновляем таблицы
            self.users_table.setRowCount(len(users))
            self.update_users_table(users)
            self.teams_table.setRowCount(len(teams))
            self.update_teams_table(teams)
            self.update_tasks_table()
            self.update_activity_timeline(activities)
            
            # Статистика по дням
            daily = db.get_daily_stats()
            self.update_daily_stats(daily)
            
            self.status_bar.showMessage(f"✅ Данные обновлены: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить данные: {str(e)}")
            
    def update_stats_cards(self, users, teams, tasks, completed):
        """Обновление карточек статистики"""
        # Очищаем старые карточки
        for card in self.stats_cards:
            card.deleteLater()
        self.stats_cards.clear()
        
        # Создаем новые карточки
        layout = self.stats_widget.layout()
        
        cards_data = [
            ("Всего пользователей", users, "👥", COLORS['info']),
            ("Всего команд", teams, "🏢", COLORS['success']),
            ("Всего задач", tasks, "📋", COLORS['warning']),
            ("Выполнено задач", completed, "✅", COLORS['primary']),
        ]
        
        for title, value, icon, color in cards_data:
            card = ModernCard(title, value, icon, color)
            layout.addWidget(card)
            self.stats_cards.append(card)
            
    def update_users_table(self, users):
        """Обновление таблицы пользователей"""
        for row, user in enumerate(users):
            self.users_table.setItem(row, 0, QTableWidgetItem(str(user['user_id'])))
            self.users_table.setItem(row, 1, QTableWidgetItem(user['username'] or '-'))
            self.users_table.setItem(row, 2, QTableWidgetItem(user['first_name'] or '-'))
            self.users_table.setItem(row, 3, QTableWidgetItem(user['last_name'] or '-'))
            self.users_table.setItem(row, 4, QTableWidgetItem(user['created_at'][:10] if user['created_at'] else '-'))
            self.users_table.setItem(row, 5, QTableWidgetItem(str(user['teams_count'])))
            self.users_table.setItem(row, 6, QTableWidgetItem(str(user['tasks_count'])))
            self.users_table.setItem(row, 7, QTableWidgetItem(str(user['completed_tasks'])))
            
    def update_teams_table(self, teams):
        """Обновление таблицы команд"""
        for row, team in enumerate(teams):
            self.teams_table.setItem(row, 0, QTableWidgetItem(str(team['team_id'])))
            self.teams_table.setItem(row, 1, QTableWidgetItem(team['team_name']))
            self.teams_table.setItem(row, 2, QTableWidgetItem(team['team_code']))
            self.teams_table.setItem(row, 3, QTableWidgetItem(team['creator']))
            self.teams_table.setItem(row, 4, QTableWidgetItem(team['created_at'][:10] if team['created_at'] else '-'))
            self.teams_table.setItem(row, 5, QTableWidgetItem(str(team['members_count'])))
            self.teams_table.setItem(row, 6, QTableWidgetItem(str(team['tasks_count'])))
            self.teams_table.setItem(row, 7, QTableWidgetItem(str(team['completed_tasks'])))
            
    def update_tasks_table(self):
        """Обновление таблицы задач"""
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                t.task_id,
                t.task_text,
                u.username,
                tm.team_name,
                t.priority,
                t.is_done,
                t.created_at
            FROM tasks t
            JOIN users u ON t.user_id = u.user_id
            LEFT JOIN teams tm ON t.team_id = tm.team_id
            ORDER BY t.created_at DESC
            LIMIT 100
        ''')
        
        tasks = cursor.fetchall()
        conn.close()
        
        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self.tasks_table.setItem(row, 0, QTableWidgetItem(str(task[0])))
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task[1][:50] + "..."))
            self.tasks_table.setItem(row, 2, QTableWidgetItem(task[2] or "-"))
            self.tasks_table.setItem(row, 3, QTableWidgetItem(task[3] or "Личная"))
            
            priority = task[4] if task[4] else 2
            priority_colors = {1: COLORS['danger'], 2: COLORS['warning'], 3: COLORS['success']}
            priority_item = QTableWidgetItem(["Высокий", "Средний", "Низкий"][priority-1])
            priority_item.setForeground(QColor(priority_colors.get(priority, COLORS['gray-600'])))
            self.tasks_table.setItem(row, 4, priority_item)
            
            status_item = QTableWidgetItem("✅ Выполнено" if task[5] else "⏳ В процессе")
            status_item.setForeground(QColor(COLORS['success'] if task[5] else COLORS['warning']))
            self.tasks_table.setItem(row, 5, status_item)
            
            self.tasks_table.setItem(row, 6, QTableWidgetItem(task[6][:10] if task[6] else "-"))
            
    def update_activity_timeline(self, activities):
        """Обновление временной шкалы активности"""
        # Очищаем текущие элементы
        for i in reversed(range(self.activity_timeline.items_layout.count())):
            item = self.activity_timeline.items_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # Добавляем новые активности
        for act in activities[:10]:  # Показываем последние 10 действий
            time_str = act['time'][:16] if act['time'] else ''
            
            if act['type'] == 'user_joined':
                activity = {
                    'icon': '🆕',
                    'color': COLORS['success'],
                    'time': time_str,
                    'description': f"Пользователь @{act['username']} присоединился к боту"
                }
            elif act['type'] == 'team_created':
                activity = {
                    'icon': '🏢',
                    'color': COLORS['info'],
                    'time': time_str,
                    'description': f"@{act['username']} создал команду '{act['text']}'"
                }
            elif act['type'] == 'task_created':
                team = f" в команде {act['team_name']}" if act['team_name'] else ""
                activity = {
                    'icon': '📝',
                    'color': COLORS['warning'],
                    'time': time_str,
                    'description': f"@{act['username']} создал задачу{team}: {act['text'][:50]}..."
                }
            else:
                activity = {
                    'icon': '❓',
                    'color': COLORS['gray-600'],
                    'time': time_str,
                    'description': act['text']
                }
            
            self.activity_timeline.add_activity(activity)
            
    def update_daily_stats(self, daily):
        """Обновление дневной статистики"""
        text = "📊 Статистика за последние 7 дней:\n\n"
        
        text += "📈 Новые пользователи:\n"
        for date, count in daily['users']:
            bar = "█" * count
            text += f"  {date}: {bar} {count}\n"
            
        text += "\n📋 Новые задачи:\n"
        for date, count in daily['tasks']:
            bar = "█" * count
            text += f"  {date}: {bar} {count}\n"
            
        text += f"\n📊 Всего пользователей: {daily.get('total_users', 0)}\n"
        text += f"🏢 Всего команд: {daily.get('total_teams', 0)}\n"
        text += f"📝 Всего задач: {daily.get('total_tasks', 0)}\n"
        text += f"✅ Выполнено задач: {daily.get('completed_tasks', 0)}\n"
        
        if daily.get('total_tasks', 0) > 0:
            completion_rate = (daily.get('completed_tasks', 0) / daily.get('total_tasks', 0)) * 100
            text += f"📈 Процент выполнения: {completion_rate:.1f}%\n"
            
        self.stats_text.setText(text)
        
    def filter_users(self):
        """Фильтрация пользователей"""
        search_text = self.user_search.text().lower()
        
        for row in range(self.users_table.rowCount()):
            show = False
            for col in [1, 2, 3]:  # username, first_name, last_name
                item = self.users_table.item(row, col)
                if item and search_text in item.text().lower():
                    show = True
                    break
            self.users_table.setRowHidden(row, not show)
            
    def filter_teams(self):
        """Фильтрация команд"""
        search_text = self.team_search.text().lower()
        
        for row in range(self.teams_table.rowCount()):
            item = self.teams_table.item(row, 1)  # team_name
            show = item and search_text in item.text().lower()
            self.teams_table.setRowHidden(row, not show)
            
    def filter_tasks(self):
        """Фильтрация задач"""
        status_filter = self.task_status.currentText()
        priority_filter = self.task_priority.currentText()
        
        for row in range(self.tasks_table.rowCount()):
            show = True
            
            if status_filter != "Все":
                status_item = self.tasks_table.item(row, 5)
                if status_filter == "Активные" and "✅" in status_item.text():
                    show = False
                elif status_filter == "Выполненные" and "✅" not in status_item.text():
                    show = False
                    
            if priority_filter != "Все" and show:
                priority_item = self.tasks_table.item(row, 4)
                if priority_filter not in priority_item.text():
                    show = False
                    
            self.tasks_table.setRowHidden(row, not show)
            
    def backup_database(self):
        """Создание бэкапа базы данных"""
        try:
            import shutil
            import os
            
            # Создаем папку для бэкапов если её нет
            if not os.path.exists('backups'):
                os.makedirs('backups')
            
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2("tasks_bot.db", f"backups/{backup_name}")
            
            QMessageBox.information(
                self, 
                "✅ Успех", 
                f"Бэкап успешно создан:\n{backup_name}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось создать бэкап: {str(e)}")
            
    def export_users(self):
        """Экспорт пользователей в CSV"""
        try:
            import csv
            
            with open('users_export.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Заголовки
                headers = []
                for col in range(self.users_table.columnCount()):
                    headers.append(self.users_table.horizontalHeaderItem(col).text())
                writer.writerow(headers)
                
                # Данные
                for row in range(self.users_table.rowCount()):
                    if not self.users_table.isRowHidden(row):
                        row_data = []
                        for col in range(self.users_table.columnCount()):
                            item = self.users_table.item(row, col)
                            row_data.append(item.text() if item else '')
                        writer.writerow(row_data)
                        
            QMessageBox.information(self, "✅ Успех", "Данные экспортированы в users_export.csv")
            
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось экспортировать: {str(e)}")
            
    def export_teams(self):
        """Экспорт команд в CSV"""
        try:
            import csv
            
            with open('teams_export.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Заголовки
                headers = []
                for col in range(self.teams_table.columnCount()):
                    headers.append(self.teams_table.horizontalHeaderItem(col).text())
                writer.writerow(headers)
                
                # Данные
                for row in range(self.teams_table.rowCount()):
                    if not self.teams_table.isRowHidden(row):
                        row_data = []
                        for col in range(self.teams_table.columnCount()):
                            item = self.teams_table.item(row, col)
                            row_data.append(item.text() if item else '')
                        writer.writerow(row_data)
                        
            QMessageBox.information(self, "✅ Успех", "Данные экспортированы в teams_export.csv")
            
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось экспортировать: {str(e)}")
            
    def export_all(self):
        """Экспорт всех данных"""
        reply = QMessageBox.question(
            self,
            "Экспорт данных",
            "Выберите, какие данные экспортировать:",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.export_users()
        elif reply == QMessageBox.StandardButton.No:
            self.export_teams()
            
    def show_about(self):
        """О программе"""
        QMessageBox.about(
            self,
            "ℹ️ О программе",
            f"""
            <div style='text-align: center;'>
                <h2 style='color: {COLORS['primary']};'>НАВИГАТОР ЗАДАЧ АДМИН ПАНЕЛЬ</h2>
                <p style='color: {COLORS['gray-600']};'>Версия 1.1.0</p>
                <hr>
                <p>Панель управления Telegram ботом НАВИГАТОР ЗАДАЧ</p>
                <br>
                <p><b>Разработчик:</b> Зборовский Артём 10'А'</p>
                <p><b>Год:</b> 2026</p>
                <br>
                <p style='color: {COLORS['gray-600']}; font-size: 11px;'>
                    Панель позволяет отслеживать активность пользователей,<br>
                    управлять командами и просматривать статистику в реальном времени.
                </p>
            </div>
            """
        )
        
    def closeEvent(self, event):
        """При закрытии окна"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы действительно хотите закрыть админ-панель?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.timer.stop()
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем современный шрифт по умолчанию
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Создаем папку для бэкапов
    import os
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    # Инициализируем БД
    db.init_db()
    
    # Запускаем админ-панель
    window = AdminPanel()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
