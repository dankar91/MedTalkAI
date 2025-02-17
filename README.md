# Medical English Practice Bot

## Описание проекта
Telegram-бот для практики медицинского английского языка через симуляцию консультаций с виртуальными пациентами. 

Бот позволяет пользователям (медицинским работникам) тренировать навыки общения с англоговорящими пациентами в безопасной среде.

### Основные возможности
- Различные уровни сложности (начальный, средний, продвинутый)
- Поддержка голосового и текстового режима общения
- Разнообразные медицинские сценарии
- Интерактивная постановка диагноза
- Подсказки для начинающих
- Оценка правильности диагноза
- Изучение медицинской терминологии

### Технические особенности
- Интеграция с OpenAI GPT-4 для генерации ответов
- Поддержка голосового ввода/вывода (Whisper API, TTS)
- База данных для хранения прогресса пользователей
- Адаптивные диалоги в зависимости от уровня пользователя

## Начало работы
1. Запустите [бота в Telegram](https://t.me/Medical_English_bot)
2. Выберите уровень сложности
3. Начните диалог с виртуальным пациентом
4. Задавайте вопросы и собирайте анамнез
5. Поставьте диагноз, когда будете готовы

Проект разработан для помощи медицинским работникам в улучшении навыков профессионального общения на английском языке.

## Основные файлы и директории

### Исходный код
- `main.py` - точка входа в приложение, инициализация бота
- `bot_handlers.py` - обработчики команд и сообщений Telegram бота
- `dialog_manager.py` - управление диалогами и сценариями
- `ai_integration.py` - интеграция с OpenAI (GPT-4, Whisper, TTS)
- `database.py` - работа с базой данных

### Данные
- `data/medical_scenarios.json` - медицинские сценарии для практики
- `instance/medical_bot.db` - файл базы данных

### Конфигурация
- `requirements.txt` - зависимости Python

## Описание компонентов

### AI Integration (`ai_integration.py`)
- Обработка голосовых сообщений (Whisper API)
- Генерация ответов (GPT-4)
- Синтез речи (TTS API)

### Database (`database.py`)
- Модели данных (User, Session)
- Управление подключением к БД
- Функции работы с пользовательским прогрессом

### Dialog Manager (`dialog_manager.py`)
- Управление активными диалогами
- Загрузка и выбор сценариев
- Отслеживание прогресса диалога

### Bot Handlers (`bot_handlers.py`)
- Обработка команд (/start)
- Управление голосовыми/текстовыми сообщениями
- Интерактивные кнопки и меню

## Потоки данных
1. Пользователь -> Telegram -> bot_handlers.py
2. bot_handlers.py -> dialog_manager.py -> medical_scenarios.json
3. bot_handlers.py -> ai_integration.py -> OpenAI API
4. dialog_manager.py -> database.py -> PostgreSQL

## Технологии
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_GPT-4-412991?style=for-the-badge&logo=openai&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_Whisper-412991?style=for-the-badge&logo=openai&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_TTS-412991?style=for-the-badge&logo=openai&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-3776AB?style=for-the-badge&logo=python&logoColor=white)

## Структура
```

Medical-English-Bot/
├── data/
│   └── medical_scenarios.json     # Сценарии диалогов
│
├── instance/
│   └── medical_bot.db             # SQLite база данных (для разработки)
│
├── main.py                        # Точка входа в приложение
├── bot_handlers.py                # Обработчики команд Telegram
├── dialog_manager.py              # Управление диалогами
├── ai_integration.py              # Интеграция с OpenAI
├── database.py                    # Работа с базой данных
│
├── requirements.txt               # Python зависимости
```

## Идеи для улучшения
- Добавить больше медицинских кейсов
