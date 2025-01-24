import logging
import os
from bot_handlers import setup_bot
from telegram import Update
from database import db_session

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

def run_telegram_bot():
    """Запуск Telegram бота"""
    try:
        logger.info("Настройка Telegram бота...")
        application = setup_bot()
        logger.info("Запуск опроса бота...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Ошибка в Telegram боте: {str(e)}", exc_info=True)
        raise

def main():
    try:
        logger.info("Starting Medical English Practice Bot...")
        run_telegram_bot()
    except Exception as e:
        logger.error(f"Critical error in main: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()