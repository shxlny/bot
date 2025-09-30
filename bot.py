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
from keyboards import (
    create_main_keyboard,
    create_university_keyboard,
    create_settings_keyboard,
    create_modify_keyboard,
    create_day_of_week_keyboard
)
from utils import translate_day_to_russian

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN = os.getenv("TG_BOT_TOKEN")
print("Токен загружен:", bool(TOKEN))

bot = telebot.TeleBot(TOKEN)
init_db()

user_states = {}

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
        
        for day in all_days:
            lessons = get_schedule_from_db(table_name, week_type, day)
            day_ru = translate_day_to_russian(day)
            personal_lessons = get_personal_modifications(chat_id, day_ru, week_type)
            
            all_lessons = list(lessons) + list(personal_lessons)
            all_lessons.sort() 
            
            full_schedule_text += f"**{day_ru}**:\n"
            if all_lessons:
                full_schedule_text += "\n".join([f"{time} — {subject}" for time, subject in all_lessons]) + "\n\n"
            else:
                full_schedule_text += "Пар нет 🎉\n\n"
        
        bot.send_message(chat_id, full_schedule_text, parse_mode='Markdown')
        return

    day_to_query_db = target_date.strftime('%A').lower()

    lessons = get_schedule_from_db(table_name, week_type, day_to_query_db)
    day_ru = translate_day_to_russian(day_to_query_db)
    personal_lessons = get_personal_modifications(chat_id, day_ru, week_type)

    all_lessons = list(lessons) + list(personal_lessons)
    all_lessons.sort()
    
    if all_lessons:
        schedule_text = "\n".join([f"{time} — {subject}" for time, subject in all_lessons])
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
    
    user_states[chat_id]['step'] = 'awaiting_time_and_subject'
    bot.send_message(chat_id, "Отлично! Теперь введите время и название пары через запятую.\nНапример: 10:00, Математика")

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'awaiting_time_and_subject')
def handle_permanent_change_input(message):
    chat_id = message.chat.id
    try:
        if ',' not in message.text:
            raise ValueError("Нет запятой в сообщении.")
            
        time, subject = message.text.split(',', 1)
        time = time.strip()
        subject = subject.strip()

        day = user_states[chat_id].get('day')
        week_type = user_states[chat_id].get('week_type')

        logging.info(f"Получены данные: user_id={chat_id}, day={day}, week_type={week_type}, time={time}, subject={subject}")

        save_permanent_modification(chat_id, day, week_type, time, subject)
        
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