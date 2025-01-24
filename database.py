import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import host, user, password, database, port

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Создание базового класса для моделей
Base = declarative_base()

# Модели данных
class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(64))
    current_level = Column(String(20), default='beginner')
    voice_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    sessions = relationship('Session', backref='user', lazy=True)

class Session(Base):
    __tablename__ = 'session'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    scenario_id = Column(String(50))
    difficulty = Column(String(20))
    correct_diagnosis = Column(Boolean)
    questions_asked = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# Настройка подключения к базе данных PostgreSQL
def setup_database():
    """Инициализация базы данных и создание всех таблиц"""
    try:
        # Использование переменных окружения для подключения к PostgreSQL
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if not DATABASE_URL:
            # Создание URL подключения из отдельных параметров
            db_params = {
                'database': database,
                'user': user,
                'password': password,
                'host': host,
                'port': port
            }

        
            if not all(db_params.values()):
                raise ValueError("Не все необходимые параметры подключения к базе данных доступны")

            DATABASE_URL = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['database']}"

        # Создание движка SQLAlchemy
        engine = create_engine(DATABASE_URL)

        # Создание всех таблиц
        Base.metadata.create_all(engine)

        # Создание сессии
        Session = sessionmaker(bind=engine)

        logger.info("База данных PostgreSQL успешно инициализирована")
        return Session
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise

# Создание глобальной сессии для использования в приложении
db_session = setup_database()

def update_user_progress(user_id: int, session_data: dict):
    try:
        with db_session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if user:
                new_session = Session(
                    user_id=user.id,
                    scenario_id=session_data.get('scenario_id'),
                    difficulty=session_data.get('difficulty'),
                    correct_diagnosis=session_data.get('correct_diagnosis'),
                    questions_asked=session_data.get('questions_asked', 0)
                )
                session.add(new_session)
                session.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении прогресса пользователя: {str(e)}")

def get_user_statistics(user_id: int) -> dict:
    """Получение статистики пользователя"""
    try:
        with db_session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {}

            sessions = session.query(Session).filter_by(user_id=user.id).all()

            return {
                'total_sessions': len(sessions),
                'correct_diagnoses': sum(1 for s in sessions if s.correct_diagnosis),
                'average_questions': sum(s.questions_asked for s in sessions) / len(sessions) if sessions else 0
            }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики пользователя: {str(e)}")
        return {}

if not setup_database():
    logger.error("Не удалось инициализировать базу данных. Завершение работы...")
    sys.exit(1)

logger.info("Приложение успешно инициализировано")