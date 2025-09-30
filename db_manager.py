# db_manager.py

import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_NAME = "base.db"


def init_db():
    """Создает необходимые таблицы при первом запуске."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица для хранения ВУЗа пользователя
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_university (
            user_id INTEGER PRIMARY KEY,
            uni_name TEXT NOT NULL
        )
    """)
    
    # Таблица для хранения персональных модификаций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_modifications (
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            week_type TEXT NOT NULL,
            time TEXT NOT NULL,
            subject TEXT NOT NULL,
            action TEXT NOT NULL,
            PRIMARY KEY (user_id, day, week_type, time)
        )
    """)
    
    # ПРИМЕЧАНИЕ: Здесь должны быть CREATE TABLE для fefu_schedule, sfu_schedule и т.д.
    
    conn.commit()
    conn.close()


# --- Функции для работы с ВУЗами ---

def get_user_university(user_id):
    """Получает сохраненное название ВУЗа для данного пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT uni_name FROM user_university WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_user_university(user_id, uni_name):
    """Сохраняет выбранное название ВУЗа для пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_university (user_id, uni_name) VALUES (?, ?)", 
        (user_id, uni_name)
    )
    conn.commit()
    conn.close()
    
# --- Функции для получения расписания ---

def get_schedule_from_db(table_name, week_type, day):
    """Получает базовое расписание для ВУЗа."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = f"""
        SELECT time, subject 
        FROM {table_name} 
        WHERE week_type = ? AND day = ?
        ORDER BY time
    """
    
    cursor.execute(query, (week_type, day))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_personal_modifications(user_id, day_ru, week_type):
    """Получает персональные модификации расписания пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    personal_query = "SELECT time, subject FROM user_modifications WHERE user_id = ? AND day = ? AND week_type = ? ORDER BY time"
    cursor.execute(personal_query, (user_id, day_ru, week_type))
    personal_lessons = cursor.fetchall()
    conn.close()
    return personal_lessons

# --- Функции для сохранения/удаления модификаций ---

def save_permanent_modification(user_id, day, week_type, time, subject):
    """Сохраняет постоянное изменение расписания."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    action = 'add'

    # 1. Удаляем старую запись
    delete_query = "DELETE FROM user_modifications WHERE user_id = ? AND day = ? AND week_type = ? AND time = ?"
    cursor.execute(delete_query, (user_id, day, week_type, time))
    
    # 2. Добавляем новую, если это не удаление
    if subject.lower() != "удалить":
        insert_query = """
            INSERT INTO user_modifications (user_id, day, week_type, time, subject, action)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (user_id, day, week_type, time, subject, action))
    
    conn.commit()
    conn.close()