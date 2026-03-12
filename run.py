# run.py
import subprocess
import sys
import os
import database as db

def main():
    # Инициализируем БД
    print("Инициализация базы данных...")
    db.init_db()
    
    # Запускаем бота в отдельном процессе
    print("Запуск Telegram бота...")
    bot_process = subprocess.Popen([sys.executable, "bot.py"])
    
    # Запускаем админ-панель
    print("Запуск админ-панели...")
    admin_process = subprocess.Popen([sys.executable, "admin_panel.py"])
    
    try:
        # Ждем завершения процессов
        bot_process.wait()
        admin_process.wait()
    except KeyboardInterrupt:
        print("\nОстановка процессов...")
        bot_process.terminate()
        admin_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
