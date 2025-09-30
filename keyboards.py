from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def create_main_keyboard():
    """Создает основную клавиатуру для навигации."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton("Сегодня"), KeyboardButton("Завтра"))
    keyboard.add(KeyboardButton("Вся неделя"))
    keyboard.add(KeyboardButton("Настройки"))
    return keyboard

def create_university_keyboard(universities):
    """Создает клавиатуру для выбора ВУЗа (принимает словарь ВУЗов)."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    for uni_name in universities.keys():
        keyboard.add(KeyboardButton(uni_name))
    keyboard.add(KeyboardButton("Назад"))
    return keyboard

def create_settings_keyboard():
    """Создает клавиатуру для меню настроек."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton("Изменить ВУЗ"), KeyboardButton("Изменить расписание"))
    keyboard.add(KeyboardButton("Назад"))
    return keyboard

def create_modify_keyboard():
    """Создает клавиатуру для выбора типа изменения расписания."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton("Единоразово"), KeyboardButton("Навсегда"))
    keyboard.add(KeyboardButton("Назад"))
    return keyboard

def create_day_of_week_keyboard():
    """Создает клавиатуру для выбора дня недели при модификации расписания."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton("Понедельник"), KeyboardButton("Вторник"))
    keyboard.add(KeyboardButton("Среда"), KeyboardButton("Четверг"))
    keyboard.add(KeyboardButton("Пятница"), KeyboardButton("Суббота"))
    keyboard.add(KeyboardButton("Воскресенье"), KeyboardButton("Назад"))
    return keyboard