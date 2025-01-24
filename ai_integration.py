import os
import json
import logging
from pathlib import Path
from openai import OpenAI

from config import OpenAIkey

# Настройка логирования
logger = logging.getLogger(__name__)

client = OpenAI(api_key=OpenAIkey)

async def process_voice_message(voice_file) -> str:
    """Обработка голосового сообщения с помощью Whisper API"""
    # Создание временной директории, если она не существует
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / "temp_voice.ogg"
    try:
        # Загрузка голосового файла
        logger.info("Загрузка голосового файла...")
        await voice_file.download_to_drive(custom_path=str(file_path))
        logger.info(f"Голосовой файл успешно загружен: {file_path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Голосовой файл не найден: {file_path}")
            
        logger.info("Начало транскрипции через Whisper API...")
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            if not transcript:
                raise ValueError("Получена пустая транскрипция от Whisper API")
                
            logger.info("Транскрипция голоса успешно завершена")
            logger.debug(f"Транскрибированный текст: {transcript[:100]}...")  # Логируем первые 100 символов
            return transcript
            
    except FileNotFoundError as e:
        logger.error(f"Ошибка файла: {str(e)}")
        raise Exception("Не удалось получить доступ к голосовому файлу")
    except Exception as e:
        logger.error(f"Ошибка обработки голосового сообщения: {str(e)}")
        raise Exception(f"Не удалось обработать голосовое сообщение: {str(e)}")
    finally:
        # Очистка временного файла
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Временный голосовой файл удален: {file_path}")
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл: {str(e)}")

async def generate_response(text: str, user_id: int, conversation_context: dict = None) -> str:
    """Генерация ответа с помощью GPT-4"""
    try:
        system_content = (
            "You are a patient talking to a doctor during a medical consultation. "
            "You must ALWAYS respond as the patient, never as the doctor. "
            "Always respond in English and stay in character as someone seeking medical help. "
        )
        if conversation_context and 'scenario' in conversation_context:
            scenario = conversation_context['scenario']
            difficulty = conversation_context.get('difficulty', 'beginner')
            symptoms = scenario.get('symptoms', {})
            
            system_content += f"Your initial complaint is: {scenario['initial_complaint']}. "
            system_content += "Your current symptoms include: "
            system_content += ", ".join([f"{k}: {v}" for k, v in symptoms.items()])
            
            # Настройка стиля ответов в зависимости от уровня сложности
            if difficulty == 'beginner':
                system_content += ". Provide clear, straightforward answers. Be direct about your symptoms. "
                system_content += "If the doctor misses an important question, you can give subtle hints."
            elif difficulty == 'intermediate':
                system_content += ". Provide moderately detailed answers. Sometimes forget to mention minor details "
                system_content += "unless specifically asked. You may occasionally need clarifying questions."
            else:  # advanced
                system_content += ". Provide complex, sometimes vague answers that require follow-up questions. "
                system_content += "You might go off-topic occasionally or mention seemingly unrelated symptoms. "
                system_content += "The doctor needs to guide the conversation to get precise information."
            
            system_content += " Stay in character and provide consistent responses based on these symptoms."

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": system_content
                },
                {"role": "user", "content": text}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating response: {str(e)}"

async def text_to_speech(text: str, conversation_context: dict = None) -> bytes:
    """Convert text to speech with gender-appropriate voice"""
    try:
        logger.info("Starting text-to-speech conversion...")
        if not text:
            raise ValueError("Empty text provided for speech conversion")
            
        # Ensure text is not too long
        if len(text) > 4096:
            text = text[:4096]  # Telegram voice message limit
            logger.info(f"Text truncated to {len(text)} characters")
            
        logger.info("Making API request to OpenAI TTS...")
        try:
            # Select voice based on patient gender with strict gender separation
            if conversation_context and 'scenario' in conversation_context:
                gender = conversation_context['scenario'].get('patient_gender', 'neutral')
                logger.info(f"Selecting voice for gender: {gender}")
                
                # Define voices with primary choices for each gender
                female_voice = 'nova'     # Primary female voice
                male_voice = 'echo'       # Primary male voice
                neutral_voice = 'alloy'   # Neutral voice
                
                if gender == 'female':
                    voice = female_voice
                    logger.info("Using female voice: nova")
                elif gender == 'male':
                    voice = male_voice
                    logger.info("Using male voice: echo")
                else:  # neutral
                    voice = neutral_voice
                    logger.info("Using neutral voice: alloy")
            else:
                voice = 'alloy'  # Default to neutral voice if no context
                logger.info("No context provided, using default neutral voice: alloy")
            
            logger.info(f"Using voice: {voice} for gender: {gender if conversation_context else 'unknown'}")
            
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="opus",  # Using opus format which is better supported by Telegram
                speed=1.0
            )
            
            if not response:
                raise ValueError("No response received from TTS API")
                
            if not hasattr(response, 'content'):
                raise ValueError("Invalid response format from TTS API")
                
            content = response.content
            if not isinstance(content, bytes):
                raise ValueError(f"Unexpected content type: {type(content)}")
                
            content_size = len(content)
            logger.info(f"Received audio content: {content_size} bytes")
            
            if content_size < 100:  # Suspiciously small file
                raise ValueError(f"Audio content too small ({content_size} bytes)")
                
            logger.info("Text-to-speech conversion completed successfully")
            return content
            
        except Exception as api_error:
            logger.error(f"OpenAI API error: {str(api_error)}")
            raise ValueError(f"TTS API error: {str(api_error)}")
            
    except Exception as e:
        logger.error(f"Error in text-to-speech conversion: {str(e)}")
        logger.error("Full error details:", exc_info=True)
        raise
