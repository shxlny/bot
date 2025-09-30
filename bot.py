import os
import telebot
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from db_manager import (
    init_db,
    get_user_university,
    set_user_university,
    get_schedule_from_db,
    get_personal_modifications,
    save_permanent_modification
)
from db_manager import get_call_schedule_for_university
from keyboards import (
    create_main_keyboard,
    create_university_keyboard,
    create_settings_keyboard,
    create_modify_keyboard,
    create_day_of_week_keyboard
)
from keyboards import create_call_time_keyboard
from keyboards import create_type_choice_keyboard, create_edit_choice_keyboard
from utils import translate_day_to_russian

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN = os.getenv("TG_BOT_TOKEN")
print("Токен загружен:", bool(TOKEN))

bot = telebot.TeleBot(TOKEN)
init_db()

user_states = {}


def normalize_type_input(ltype: str) -> str:
    if not ltype:
        return ''
    s = ltype.strip().lower()
    if s in ('лекция', 'лек', 'lec', 'l'):
        return 'lec'
    if s in ('практика', 'прак', 'prac', 'p'):
        return 'prac'
    if s.startswith('лек'):
        return 'lec'
    if s.startswith('прак') or s.startswith('пр'):
        return 'prac'
    return s

universities = {
    'ДВФУ': 'schedule',
    'СФУ': 'sheldue_2'
}

base_date = datetime(2025, 9, 29)
base_week_is_even = False



def send_schedule_message(chat_id, day_name_from_button):
    uni_name = get_user_university(chat_id)
    
    if not uni_name:
        bot.send_message(chat_id, "Пожалуйста, сначала выберите ВУЗ в Настройках.", 
                         reply_markup=create_university_keyboard(universities)) 
        return
        
    table_name = universities[uni_name]

    if day_name_from_button == 'Сегодня':
        target_date = datetime.now()
        day_text = "Расписание на сегодня:\n"
    elif day_name_from_button == 'Завтра':
        target_date = datetime.now() + timedelta(days=1)
        day_text = "Расписание на завтра:\n"
    elif day_name_from_button == 'Вся неделя':
        target_date = datetime.now()
        day_text = "" 
    
    delta_days = (target_date - base_date).days
    delta_weeks = delta_days // 7
    
    is_odd_week = delta_weeks % 2 == 0 if not base_week_is_even else delta_weeks % 2 != 0
        
    week_type = "odd" if is_odd_week else "even"
    week_type_ru = 'нечетную' if week_type == 'odd' else 'четную'

    if day_name_from_button == 'Вся неделя':
        all_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        full_schedule_text = f"Расписание на {week_type_ru} неделю:\n\n"
        start_of_week = target_date - timedelta(days=target_date.weekday())
        for i, day in enumerate(all_days):
            date_obj = start_of_week + timedelta(days=i)
            date_str = date_obj.strftime('%Y-%m-%d')
            lessons = get_schedule_from_db(table_name, week_type, day)
            day_ru = translate_day_to_russian(day)
            personal_permanent = get_personal_modifications(chat_id, day_ru, week_type)
            personal_oneoffs = get_personal_modifications(chat_id, date_str, 'single')
            personal_lessons = personal_permanent + personal_oneoffs

            merged = {}
            def time_key(t):
                import re
                m = re.search(r"(\d{1,2}:\d{2})", t)
                if m:
                    hh, mm = m.group(1).split(":")
                    return int(hh) * 60 + int(mm)
                return None

            for row in lessons:
                if len(row) >= 3:
                    t, subj, ltype = row[0], row[1], row[2]
                else:
                    t, subj, ltype = row[0], row[1], ''
                k = time_key(t)
                if k is None:
                    k = t
                merged[k] = (t, subj, ltype)

            for row in personal_lessons:
                if len(row) >= 3:
                    t, subj, ltype = row[0], row[1], row[2]
                else:
                    t, subj, ltype = row[0], row[1], ''
                k = time_key(t)
                if k is None:
                    k = t
                merged[k] = (t, subj, ltype)

            try:
                sorted_items = sorted(merged.items(), key=lambda kv: (not isinstance(kv[0], int), kv[0]))
            except Exception:
                sorted_items = merged.items()

            full_schedule_text += f"**{day_ru}**:\n"
            if sorted_items:
                def fmt(entry):
                    t, subj, ltype = entry
                    type_map = {'lec': 'лекция', 'prac': 'практика'}
                    if ltype:
                        label = type_map.get(ltype.lower(), ltype)
                        return f"{t} — {subj} ({label})"
                    return f"{t} — {subj}"
                full_schedule_text += "\n".join([fmt(item) for _, item in sorted_items]) + "\n\n"
            else:
                full_schedule_text += "Пар нет 🎉\n\n"
        
        bot.send_message(chat_id, full_schedule_text, parse_mode='Markdown')
        return

    day_to_query_db = target_date.strftime('%A').lower()

    lessons = get_schedule_from_db(table_name, week_type, day_to_query_db)
    day_ru = translate_day_to_russian(day_to_query_db)
    personal_permanent = get_personal_modifications(chat_id, day_ru, week_type)
    personal_oneoffs = get_personal_modifications(chat_id, target_date.strftime('%Y-%m-%d'), 'single')
    personal_lessons = personal_permanent + personal_oneoffs

    merged = {}
    import re
    def time_key(t):
        m = re.search(r"(\d{1,2}:\d{2})", t)
        if m:
            hh, mm = m.group(1).split(":")
            return int(hh) * 60 + int(mm)
        return None

    for row in lessons:
        if len(row) >= 3:
            t, subj, ltype = row[0], row[1], row[2]
        else:
            t, subj, ltype = row[0], row[1], ''
        k = time_key(t)
        if k is None:
            k = t
        merged[k] = (t, subj, ltype)

    for row in personal_lessons:
        if len(row) >= 3:
            t, subj, ltype = row[0], row[1], row[2]
        else:
            t, subj, ltype = row[0], row[1], ''
        k = time_key(t)
        if k is None:
            k = t
        merged[k] = (t, subj, ltype)

    try:
        sorted_items = sorted(merged.items(), key=lambda kv: (not isinstance(kv[0], int), kv[0]))
    except Exception:
        sorted_items = merged.items()

    if sorted_items:
        def fmt(entry):
            t, subj, ltype = entry
            type_map = {'lec': 'лекция', 'prac': 'практика'}
            if ltype:
                label = type_map.get(ltype.lower(), ltype)
                return f"{t} — {subj} ({label})"
            return f"{t} — {subj}"
        schedule_text = "\n".join([fmt(item) for _, item in sorted_items])
        bot.send_message(chat_id, day_text + schedule_text)
    else:
        bot.send_message(chat_id, day_text + "Пар нет 🎉")



@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = create_main_keyboard()
    bot.send_message(message.chat.id, "Привет! Пожалуйста, выбери свой ВУЗ в настройках.", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in ["Сегодня", "Завтра", "Вся неделя"])
def handle_day_button(message):
    send_schedule_message(message.chat.id, message.text)

@bot.message_handler(func=lambda message: message.text == "Настройки")
def handle_settings(message):
    keyboard = create_settings_keyboard()
    bot.send_message(message.chat.id, "Выберите опцию:", reply_markup=keyboard)
    
@bot.message_handler(func=lambda message: message.text == "Изменить ВУЗ")
def handle_change_uni_button(message):
    keyboard = create_university_keyboard(universities)
    bot.send_message(message.chat.id, "Выберите ВУЗ:", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in universities.keys())
def handle_university_selection(message):
    chat_id = message.chat.id
    selected_uni_name = message.text
    
    set_user_university(chat_id, selected_uni_name)
    
    keyboard = create_main_keyboard()
    bot.send_message(chat_id, f"Выбран ВУЗ: {selected_uni_name}. Теперь вы можете смотреть расписание.", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == "Назад")
def handle_back_button(message):
    if message.chat.id in user_states:
        del user_states[message.chat.id]
        
    keyboard = create_main_keyboard()
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=keyboard)
    
@bot.message_handler(func=lambda message: message.text == "Изменить расписание")
def handle_modify_schedule(message):
    uni_name = get_user_university(message.chat.id)
    if not uni_name:
        bot.send_message(message.chat.id, "Сначала выберите ВУЗ в Настройках.", reply_markup=create_settings_keyboard())
        return
        
    user_states[message.chat.id] = {'step': 'awaiting_type', 'uni_name': uni_name}
    keyboard = create_modify_keyboard()
    bot.send_message(message.chat.id, "Как вы хотите изменить расписание?", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in ["Единоразово", "Навсегда"] and message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_type')
def handle_change_type(message):
    chat_id = message.chat.id
    user_states[chat_id]['change_type'] = message.text

    if message.text == "Навсегда":
        user_states[chat_id]['step'] = 'awaiting_day_and_week'
        keyboard = create_day_of_week_keyboard()
        bot.send_message(chat_id, "Хорошо. Теперь выберите день недели, а затем укажите тип недели (четная/нечетная).", reply_markup=keyboard)
    elif message.text == "Единоразово":
        user_states[chat_id]['step'] = 'awaiting_date'
        bot.send_message(chat_id, "Отлично! Теперь введите дату в формате ГГГГ-ММ-ДД. Например, 2025-09-29")


@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_date')
def handle_single_date_input(message):
    chat_id = message.chat.id
    text = message.text.strip()
    from datetime import datetime
    try:
        date_obj = datetime.strptime(text, '%Y-%m-%d')
    except Exception:
        bot.send_message(chat_id, "Неверный формат даты. Введите в формате ГГГГ-ММ-ДД, например: 2025-09-29")
        return

    date_str = date_obj.strftime('%Y-%m-%d')
    user_states[chat_id]['day'] = date_str
    user_states[chat_id]['date_obj'] = date_obj
    user_states[chat_id]['single'] = True

    delta_days = (date_obj - base_date).days
    delta_weeks = delta_days // 7
    is_odd_week = delta_weeks % 2 == 0 if not base_week_is_even else delta_weeks % 2 != 0
    week_type_for_base = "odd" if is_odd_week else "even"

    uni_name = user_states[chat_id].get('uni_name')
    table_name = universities.get(uni_name)

    base_lessons = get_schedule_from_db(table_name, week_type_for_base, date_obj.strftime('%A').lower())
    personal_permanent = get_personal_modifications(chat_id, translate_day_to_russian(date_obj.strftime('%A').lower()), week_type_for_base)
    personal_oneoffs = get_personal_modifications(chat_id, date_str, 'single')

    existing_map = {}
    import re
    def extract_start(t):
        m = re.search(r"(\d{1,2}:\d{2})", t)
        return m.group(1) if m else t

    for row in base_lessons:
        if len(row) >= 3:
            t0, subj0, type0 = row[0], row[1], row[2]
        else:
            t0, subj0, type0 = row[0], row[1], ''
        existing_map[extract_start(t0)] = (subj0, type0)
    for row in personal_permanent:
        if len(row) >= 3:
            t0, subj0, type0 = row[0], row[1], row[2]
        else:
            t0, subj0, type0 = row[0], row[1], ''
        existing_map[extract_start(t0)] = (subj0, type0)
    for row in personal_oneoffs:
        if len(row) >= 3:
            t0, subj0, type0 = row[0], row[1], row[2]
        else:
            t0, subj0, type0 = row[0], row[1], ''
        existing_map[extract_start(t0)] = (subj0, type0)

    call_rows = get_call_schedule_for_university(uni_name)
    call_buttons = []
    for lesson_number, start_time, end_time in call_rows:
        start = extract_start(start_time)
        if start in existing_map:
            subj, ltype = existing_map[start]
            if ltype:
                type_map = {'lec': 'лекция', 'prac': 'практика'}
                label_type = type_map.get(ltype.lower(), ltype)
                label = f"{lesson_number}) {start} — {subj} ({label_type})"
            else:
                label = f"{lesson_number}) {start} — {subj}"
        else:
            label = f"{lesson_number}) {start}-{end_time}"
        call_buttons.append(label)

    user_states[chat_id]['step'] = 'awaiting_time_selection'
    keyboard = create_call_time_keyboard(call_buttons)
    bot.send_message(chat_id, "Выберите время пары (или 'Ручной ввод'):", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"] and message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_day_and_week')
def handle_permanent_day_selection(message):
    chat_id = message.chat.id
    user_states[chat_id]['day'] = message.text
    user_states[chat_id]['step'] = 'awaiting_week_type'
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Четная"), KeyboardButton("Нечетная"))
    bot.send_message(chat_id, "Теперь выберите тип недели:", reply_markup=keyboard)
    
@bot.message_handler(func=lambda message: message.text in ["Четная", "Нечетная"] and message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_week_type')
def handle_permanent_week_type(message):
    chat_id = message.chat.id
    user_states[chat_id]['week_type'] = "even" if message.text == "Четная" else "odd"

    uni_name = user_states[chat_id].get('uni_name')
    call_rows = get_call_schedule_for_university(uni_name)
    if user_states[chat_id].get('single'):
        day = user_states[chat_id].get('day')  
        week_type = 'single'
    else:
        day = user_states[chat_id].get('day')
        week_type = user_states[chat_id].get('week_type')
    table_name = universities.get(uni_name)
    base_lessons = get_schedule_from_db(table_name, week_type, day.lower())
    personal_lessons = get_personal_modifications(chat_id, day, week_type)

    existing_map = {}
    import re
    def extract_start(t):
        m = re.search(r"(\d{1,2}:\d{2})", t)
        return m.group(1) if m else t

    for row in base_lessons:
        if len(row) >= 3:
            t0, subj0, type0 = row[0], row[1], row[2]
        else:
            t0, subj0, type0 = row[0], row[1], ''
        existing_map[extract_start(t0)] = (subj0, type0)
    for row in personal_lessons:
        if len(row) >= 3:
            t0, subj0, type0 = row[0], row[1], row[2]
        else:
            t0, subj0, type0 = row[0], row[1], ''
        existing_map[extract_start(t0)] = (subj0, type0)

    call_buttons = []
    for lesson_number, start_time, end_time in call_rows:
        start = extract_start(start_time)
        if start in existing_map:
            subj, ltype = existing_map[start]
            if ltype:
                type_map = {'lec': 'лекция', 'prac': 'практика'}
                label_type = type_map.get(ltype.lower(), ltype)
                label = f"{lesson_number}) {start} — {subj} ({label_type})"
            else:
                label = f"{lesson_number}) {start} — {subj}"
        else:
            label = f"{lesson_number}) {start}-{end_time}"
        call_buttons.append(label)

    if not call_buttons:
        user_states[chat_id]['step'] = 'awaiting_time_and_subject'
        bot.send_message(chat_id, "В базе нет времени звонков для вашего ВУЗа. Введите время и название пары через запятую.\nНапример: 10:00, Математика")
        return

    user_states[chat_id]['step'] = 'awaiting_time_selection'
    keyboard = create_call_time_keyboard(call_buttons)
    bot.send_message(chat_id, "Выберите время пары (или 'Ручной ввод'):", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_time_selection')
def handle_time_selection(message):
    chat_id = message.chat.id
    text = message.text
    if text == 'Ручной ввод':
        user_states[chat_id]['step'] = 'awaiting_time_and_subject'
        bot.send_message(chat_id, "Хорошо. Введите время и название пары через запятую.\nПример: 10:00, Математика")
        return

    if ')' in text:
        try:
            import re
            m = re.search(r"(\d{1,2}:\d{2})", text)
            time = m.group(1) if m else text.split(')', 1)[1].strip().split('-')[0].strip()
            user_states[chat_id]['selected_time'] = time
            uni_name = user_states[chat_id].get('uni_name')
            table_name = universities.get(uni_name)

            if user_states[chat_id].get('single'):
                date_obj = user_states[chat_id].get('date_obj')
                date_str = user_states[chat_id].get('day')
                delta_days = (date_obj - base_date).days
                delta_weeks = delta_days // 7
                is_odd_week = delta_weeks % 2 == 0 if not base_week_is_even else delta_weeks % 2 != 0
                week_type_for_base = "odd" if is_odd_week else "even"
                day_en = date_obj.strftime('%A').lower()

                base_lessons = get_schedule_from_db(table_name, week_type_for_base, day_en)
                personal_permanent = get_personal_modifications(chat_id, translate_day_to_russian(day_en), week_type_for_base)
                personal_oneoffs = get_personal_modifications(chat_id, date_str, 'single')
                personal_lessons = personal_permanent + personal_oneoffs
                day = date_str
                week_type = 'single'
            else:
                day = user_states[chat_id].get('day')
                week_type = user_states[chat_id].get('week_type')
                base_lessons = get_schedule_from_db(table_name, week_type, day.lower())
                personal_lessons = get_personal_modifications(chat_id, day, week_type)
            def extract_start(t):
                mm = re.search(r"(\d{1,2}:\d{2})", t)
                return mm.group(1) if mm else t

            exists = False
            for row in base_lessons + personal_lessons:
                t0 = row[0]
                if extract_start(t0) == time:
                    exists = True
                    break

            if exists:
                user_states[chat_id]['step'] = 'awaiting_edit_choice'
                keyboard = create_edit_choice_keyboard()
                bot.send_message(chat_id, "Пара уже есть на этом времени. Что вы хотите сделать?", reply_markup=keyboard)
            else:
                user_states[chat_id]['step'] = 'awaiting_type_choice'
                keyboard = create_type_choice_keyboard()
                bot.send_message(chat_id, "Выберите тип пары:", reply_markup=keyboard)
            return
        except Exception:
            bot.send_message(chat_id, "Не удалось распознать выбранную кнопку. Попробуйте 'Ручной ввод' или выберите время снова.")
            return

    bot.send_message(chat_id, "Пожалуйста, используйте кнопки для выбора времени или нажмите 'Ручной ввод'.")


@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_subject_only')
def handle_subject_only(message):
    chat_id = message.chat.id
    parts = [p.strip() for p in message.text.split(',', 1)]
    subject = parts[0]
    ltype = parts[1] if len(parts) > 1 else ''
    time = user_states[chat_id].get('selected_time')
    if user_states[chat_id].get('single'):
        day = user_states[chat_id].get('day')
        week_type = 'single'
    else:
        day = user_states[chat_id].get('day')
        week_type = user_states[chat_id].get('week_type')

    pending = user_states[chat_id].get('pending_type', '')
    final_type = normalize_type_input(ltype) or pending or ''

    logging.info(f"Получены данные (button): user_id={chat_id}, day={day}, week_type={week_type}, time={time}, subject={subject}")
    save_permanent_modification(chat_id, day, week_type, time, subject if subject else '', final_type)

    bot.send_message(chat_id, f"Изменение для {day} ({week_type}) в {time} успешно сохранено!")
    keyboard = create_main_keyboard()
    bot.send_message(chat_id, "Главное меню:", reply_markup=keyboard)
    user_states[chat_id].pop('pending_type', None)
    del user_states[chat_id]


@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_type_choice')
def handle_type_choice(message):
    chat_id = message.chat.id
    text = message.text
    if text == 'Лекция':
        user_states[chat_id]['pending_type'] = 'lec'
    elif text == 'Практика':
        user_states[chat_id]['pending_type'] = 'prac'
    elif text == 'Ручной ввод':
        user_states[chat_id]['step'] = 'awaiting_time_and_subject'
        bot.send_message(chat_id, "Введите время и название пары через запятую.\nПример: 10:00, Математика, lec")
        return
    else:
        bot.send_message(chat_id, "Выберите один из вариантов.")
        return

    user_states[chat_id]['step'] = 'awaiting_subject_only'
    bot.send_message(chat_id, "Введите название пары (только предмет), например: Математика")


@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_edit_choice')
def handle_edit_choice(message):
    chat_id = message.chat.id
    text = message.text
    if text.startswith('Изменить'):
        if 'Лекция' in text:
            user_states[chat_id]['pending_type'] = 'lec'
        elif 'Практика' in text:
            user_states[chat_id]['pending_type'] = 'prac'
        user_states[chat_id]['step'] = 'awaiting_subject_only'
        bot.send_message(chat_id, "Введите новое название пары (только предмет) или 'Удалить' чтобы удалить:")
        return
    if text == 'Удалить':
        if user_states[chat_id].get('single'):
            day = user_states[chat_id].get('day')
            week_type = 'single'
        else:
            day = user_states[chat_id].get('day')
            week_type = user_states[chat_id].get('week_type')
        time = user_states[chat_id].get('selected_time')
        save_permanent_modification(chat_id, day, week_type, time, 'удалить')
        bot.send_message(chat_id, f"Пара в {time} удалена.")
        keyboard = create_main_keyboard()
        bot.send_message(chat_id, "Главное меню:", reply_markup=keyboard)
        del user_states[chat_id]
        return
    if text == 'Ручной ввод':
        user_states[chat_id]['step'] = 'awaiting_time_and_subject'
        bot.send_message(chat_id, "Введите время и название пары через запятую.\nПример: 10:00, Математика, lec")
        return

    bot.send_message(chat_id, "Неизвестная опция. Пожалуйста, выберите действие.")


@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_time_and_subject')
def handle_permanent_change_input(message):
    chat_id = message.chat.id
    try:
        if ',' not in message.text:
            raise ValueError("Нет запятой в сообщении.")

        parts = [p.strip() for p in message.text.split(',', 2)]
        time = parts[0]
        subject = parts[1] if len(parts) > 1 else ''
        ltype = parts[2] if len(parts) > 2 else ''

        day = user_states[chat_id].get('day')
        week_type = user_states[chat_id].get('week_type')

        logging.info(f"Получены данные (manual): user_id={chat_id}, day={day}, week_type={week_type}, time={time}, subject={subject}")
        save_permanent_modification(chat_id, day, week_type, time, subject if subject else '', normalize_type_input(ltype))

        bot.send_message(chat_id, f"Изменение для {day} ({week_type}) в {time} успешно сохранено!")
        keyboard = create_main_keyboard()
        bot.send_message(chat_id, "Главное меню:", reply_markup=keyboard)
        del user_states[chat_id]

    except ValueError as e:
        logging.error(f"Ошибка ввода: {e}")
        bot.send_message(chat_id, "Неверный формат. Пожалуйста, введите время и название пары через запятую. Например: 10:00, Математика")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}", exc_info=True)
        bot.send_message(chat_id, "Произошла непредвиденная ошибка. Пожалуйста, попробуйте снова.")


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    bot.reply_to(message, "Прости, я не понимаю эту команду. Пожалуйста, используй кнопки.")

bot.polling(none_stop=True)