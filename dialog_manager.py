import json
import logging
from typing import Dict, Optional, Any
from difflib import SequenceMatcher
import random
from database import User, Session, db_session

logger = logging.getLogger(__name__)

def string_similarity(a: str, b: str) -> float:
    """Вычисляет схожесть двух строк, возвращает значение от 0 до 1"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

class ConversationManager:
    def __init__(self):
        self.active_conversations: Dict[int, dict] = {}
        self.load_scenarios()

    def load_scenarios(self):
        """Загрузка медицинских сценариев из JSON файла"""
        try:
            with open('data/medical_scenarios.json', 'r') as f:
                data = json.load(f)
                self.scenarios = data.get('scenarios', [])
                logger.info(f"Загружено {len(self.scenarios)} сценариев")
        except Exception as e:
            logger.error(f"Ошибка при загрузке сценариев: {e}")
            self.scenarios = []

    def start_conversation(self, user_id: int, difficulty: str):
        """Начало нового диалога с выбранным уровнем сложности"""
        scenario = self._select_scenario(difficulty)
        self.active_conversations[user_id] = {
            'difficulty': difficulty,
            'scenario': scenario,
            'questions_asked': [],
            'diagnosis_made': False
        }

    def add_question(self, user_id: int, question: str):
        """Отслеживание вопросов, заданных пользователем"""
        try:
            if user_id in self.active_conversations:
                if 'questions_asked' not in self.active_conversations[user_id]:
                    self.active_conversations[user_id]['questions_asked'] = []
                if question and isinstance(question, str):
                    self.active_conversations[user_id]['questions_asked'].append(question)
                    logger.debug(f"Добавлен вопрос для пользователя {user_id}. Всего вопросов: {len(self.active_conversations[user_id]['questions_asked'])}")
            else:
                logger.warning(f"Попытка добавить вопрос для неактивного диалога: user_id={user_id}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении вопроса: {str(e)}")

    def _select_scenario(self, difficulty: str) -> dict:
        """Выбор случайного сценария соответствующей сложности"""
        suitable_scenarios = [s for s in self.scenarios if s['difficulty'] == difficulty]
        return random.choice(suitable_scenarios)

    def get_initial_prompt(self, user_id: int) -> str:
        """Получение начального сообщения для пациента"""
        if user_id not in self.active_conversations:
            return "Please start a dialogue first!"

        scenario = self.active_conversations[user_id]['scenario']
        return scenario['initial_complaint']

    def is_conversation_active(self, user_id: int) -> bool:
        """Проверка активности диалога для пользователя"""
        return user_id in self.active_conversations

    def get_conversation_context(self, user_id: int) -> Optional[dict]:
        """Получение контекста текущего диалога"""
        return self.active_conversations.get(user_id)

    def end_conversation(self, user_id: int):
        """Завершение диалога"""
        if user_id in self.active_conversations:
            # Сохраняем прогресс пользователя перед завершением
            context = self.active_conversations[user_id]
            session_data = {
                'scenario_id': context['scenario']['id'],
                'difficulty': context['difficulty'],
                'questions_asked': len(context.get('questions_asked', [])),
                'correct_diagnosis': context.get('diagnosis_made', False)
            }
            self._update_user_progress(user_id, session_data)
            del self.active_conversations[user_id]

    def _update_user_progress(self, user_id: int, session_data: Dict[str, Any]):
        """Обновление прогресса пользователя в базе данных"""
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

    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
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