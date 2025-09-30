import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_NAME = "base.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_university (
            user_id INTEGER PRIMARY KEY,
            uni_name TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_modifications (
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            week_type TEXT NOT NULL,
            time TEXT NOT NULL,
            subject TEXT NOT NULL,
            action TEXT NOT NULL,
            -- optional column for lesson type (lec/prac)
            type TEXT DEFAULT '',
            PRIMARY KEY (user_id, day, week_type, time)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_schedule (
            uni_name TEXT NOT NULL,
            lesson_number INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            PRIMARY KEY (uni_name, lesson_number)
        )
    """)
    
    
    conn.commit()
    conn.close()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(user_modifications)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'type' not in cols:
        try:
            cursor.execute("ALTER TABLE user_modifications ADD COLUMN type TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass
    conn.close()



def get_user_university(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT uni_name FROM user_university WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_user_university(user_id, uni_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_university (user_id, uni_name) VALUES (?, ?)", 
        (user_id, uni_name)
    )
    conn.commit()
    conn.close()
    

def get_schedule_from_db(table_name, week_type, day):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = f"""
        SELECT time, subject, COALESCE(type, '') as type
        FROM {table_name} 
        WHERE week_type = ? AND day = ?
        ORDER BY time
    """
    
    cursor.execute(query, (week_type, day))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_personal_modifications(user_id, day_ru, week_type):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT time, subject, COALESCE(type, '') as type, day, date, week_type, is_one_time FROM user_modifications WHERE user_id = ? ORDER BY time", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        time_val, subj_val, type_val = r[0], r[1], r[2]
        day_col = r[3] if len(r) > 3 else None
        date_col = r[4] if len(r) > 4 else None
        row_week_type = r[5] if len(r) > 5 else None

        matched = False
        if week_type == 'single':
            if date_col == day_ru:
                matched = True
            elif day_col == day_ru and (row_week_type == 'single' or row_week_type is None):
                matched = True
        else:
            if day_col == day_ru and (row_week_type == week_type or row_week_type is None):
                matched = True
            if date_col == day_ru:
                matched = True

        if matched:
            result.append((time_val, subj_val, type_val))

    return result


def get_call_schedule_for_university(uni_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT lesson_number, start_time, end_time FROM call_schedule WHERE uni_name = ? ORDER BY lesson_number", (uni_name,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def format_call_times_for_keyboard(call_rows):
    buttons = []
    for lesson_number, start_time, end_time in call_rows:
        buttons.append(f"{lesson_number}) {start_time}-{end_time}")
    return buttons


def save_permanent_modification(user_id, day, week_type, time, subject, ltype=''):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    action = 'add'

    import re
    m = re.search(r"(\d{1,2}:\d{2})", str(time))
    start_time = m.group(1) if m else str(time).strip()

    delete_query = "DELETE FROM user_modifications WHERE user_id = ? AND day = ? AND week_type = ? AND (time = ? OR time LIKE ? )"
    cursor.execute(delete_query, (user_id, day, week_type, start_time, start_time + '%'))

    if isinstance(subject, str) and subject.lower() != "удалить":
        insert_query = """
            INSERT INTO user_modifications (user_id, day, week_type, time, subject, action, type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (user_id, day, week_type, start_time, subject, action, ltype or ''))
    
    conn.commit()
    conn.close()