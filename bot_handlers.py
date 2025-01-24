import logging
import os
import time
import asyncio
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from dialog_manager import ConversationManager
from database import User, Session, db_session
from ai_integration import process_voice_message, generate_response, text_to_speech
from config import TelegramToken

logger = logging.getLogger(__name__)

def get_start_dialogue_markup():
    """Helper function to create Start Dialogue button markup"""
    keyboard = [[InlineKeyboardButton("Start Dialogue", callback_data='start_dialogue')]]
    return InlineKeyboardMarkup(keyboard)

conversation_manager = ConversationManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        logger.info(f"Start command received from user {user.id}")

        try:
            with db_session() as session:
                # Create or get user from database
                db_user = session.query(User).filter_by(telegram_id=user.id).first()
                if not db_user:
                    db_user = User(
                        telegram_id=user.id,
                        username=user.username,
                        voice_mode=False,
                        current_level='beginner'
                    )
                    session.add(db_user)
                    session.commit()
                    logger.info(f"Created new user with telegram_id {user.id}")
        except Exception as db_error:
            logger.error(f"Database error in start command: {db_error}")
            raise

        keyboard = [
            [InlineKeyboardButton("Start Dialogue", callback_data='start_dialogue')],
            [InlineKeyboardButton("Settings", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Добро пожаловать в Medical English Practice Bot! Здесь вы можете практиковать медицинский английский "
            "проводя консультации с пациентами.",
            reply_markup=reply_markup
        )
        logger.info(f"Sent welcome message to user {user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")
        await update.message.reply_text(
            "Извините, произошла ошибка при запуске бота. Пожалуйста, попробуйте еще раз через несколько секунд."
        )
        raise

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'start_dialogue':
        keyboard = [
            [
                InlineKeyboardButton("Beginner", callback_data='level_beginner'),
                InlineKeyboardButton("Intermediate", callback_data='level_intermediate'),
                InlineKeyboardButton("Advanced", callback_data='level_advanced')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        info_message = (
            "You can ask questions to the patient and when you're ready make a diagnosis.\n\n"
        )
        
        try:
            with db_session() as session:
                user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
                if user and user.voice_mode:
                    info_message += "Voice mode is enabled. You can send voice messages!\n\n"
        except Exception as e:
            logger.error(f"Database error in handle_callback (start_dialogue): {e}")

        info_message += "Please select difficulty level:"
        await query.message.reply_text(info_message, reply_markup=reply_markup)
    
    elif query.data.startswith('level_'):
        level = query.data.split('_')[1]
        conversation_manager.start_conversation(query.from_user.id, level)
        initial_prompt = conversation_manager.get_initial_prompt(query.from_user.id)
        context = conversation_manager.get_conversation_context(query.from_user.id)
        
        message = f"{initial_prompt}\n\n"
        
        if level == 'beginner' and context and 'scenario' in context:
            hints = context['scenario'].get('hints', [])
            if hints:
                message += "Here are some suggested questions you might want to ask:\n"
                message += "\n".join(f"- {hint}" for hint in hints)
                message += "\n\n"
        
        message += "You can start asking questions to the patient."
        
        await query.message.reply_text(message)
    
    elif query.data == 'make_diagnosis':
        context.user_data['awaiting_diagnosis'] = True
        await query.message.reply_text(
            "Please provide your diagnosis:"
        )
    
    elif query.data == 'settings':
        try:
            with db_session() as session:
                user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
                current_mode = "Voice Mode: ON 🗣" if user.voice_mode else "Voice Mode: OFF 📝"
                
                keyboard = [
                    [InlineKeyboardButton("Toggle Voice Mode", callback_data='toggle_voice')],
                    [InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    f"Settings\n\n{current_mode}\n\nYou can toggle between voice and text modes:",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Database error in handle_callback (settings): {e}")

    
    elif query.data == 'toggle_voice':
        try:
            with db_session() as session:
                user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
                user.voice_mode = not user.voice_mode
                session.commit()
                
                new_mode = "Voice Mode: ON 🗣" if user.voice_mode else "Voice Mode: OFF 📝"
                await query.message.reply_text(f"Mode updated! {new_mode}")
        except Exception as e:
            logger.error(f"Database error in handle_callback (toggle_voice): {e}")
    
    elif query.data == 'show_transcription':
        bot_response = context.user_data.get('bot_response')
        if bot_response:
            await query.message.reply_text(bot_response)
        else:
            await query.message.reply_text("No recent bot response available.")
            
    elif query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("Start Dialogue", callback_data='start_dialogue')],
            [InlineKeyboardButton("Settings", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "Main Menu:",
            reply_markup=reply_markup
        )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        if not conversation_manager.is_conversation_active(user_id):
            await update.message.reply_text(
                "Please start a dialogue first!",
                reply_markup=get_start_dialogue_markup()
            )
            return

        try:
            with db_session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                if not user or not user.voice_mode:
                    await update.message.reply_text(
                        "Voice mode is disabled. Enable it in settings or use text input."
                    )
                    return
        except Exception as e:
            logger.error(f"Database error in handle_voice (voice mode check): {e}")
            return

        voice = update.message.voice
        if not voice:
            await update.message.reply_text("Voice message not detected. Please try again.")
            return
            
        processing_msg = await update.message.reply_text("Processing your voice message and generating response...")
        
        try:
            logger.info("Retrieving voice file from Telegram...")
            file = await context.bot.get_file(voice.file_id)
            if not file:
                raise ValueError("Failed to retrieve voice file")
            logger.info("Voice file retrieved successfully")
            
            logger.info("Starting transcription with Whisper API...")
            text = await process_voice_message(file)
            if not text:
                raise ValueError("Failed to transcribe voice message")
            logger.info("Voice transcription completed successfully")
            
            logger.info("Generating response using GPT...")
            conv_context = conversation_manager.get_conversation_context(user_id)
            
            try:
                conversation_manager.add_question(user_id, text)
                logger.info(f"Added voice question from user {user_id}: {text[:50]}...")
            except Exception as e:
                logger.error(f"Error tracking voice question: {str(e)}")
            
            response = await generate_response(text, user_id, conv_context)
            logger.info("GPT response generated successfully")
            
            context.user_data['bot_response'] = response
            
            logger.info("Starting voice response generation...")
            audio_content = await text_to_speech(response, conv_context)
            
            if not audio_content:
                raise ValueError("No audio content received from text_to_speech")
                
            audio_size = len(audio_content)
            logger.info(f"Received audio content of size: {audio_size} bytes")
            
            if audio_size < 100:  # Suspiciously small file
                raise ValueError(f"Audio content too small ({audio_size} bytes)")
            
            voice_file = None
            try:
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True, mode=0o755)
                
                timestamp = int(time.time())
                voice_file = temp_dir / f"response_{user_id}_{timestamp}.opus"
                
                logger.info(f"Saving voice response to {voice_file}")
                with open(voice_file, "wb") as f:
                    f.write(audio_content)
                
                if not voice_file.exists():
                    raise ValueError("Voice file was not created")
                
                file_size = voice_file.stat().st_size
                if file_size == 0:
                    raise ValueError("Voice file is empty")
                
                if file_size < 100:  # Additional size check
                    raise ValueError(f"Voice file too small: {file_size} bytes")
                
                logger.info(f"Voice file created successfully, size: {file_size} bytes")
                
                with open(voice_file, "rb") as f:
                    try:
                        await context.bot.send_voice(
                            chat_id=update.effective_chat.id,
                            voice=f,
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("Make Diagnosis", callback_data='make_diagnosis')],
                                [InlineKeyboardButton("Show Transcription", callback_data='show_transcription')]
                            ])
                        )
                        logger.info("Voice message sent successfully")
                    except Exception as telegram_error:
                        logger.error(f"Error sending voice message via Telegram: {str(telegram_error)}")
                        raise ValueError(f"Failed to send voice message: {str(telegram_error)}")
                        
            except Exception as file_error:
                logger.error(f"Error handling voice file: {str(file_error)}")
                raise ValueError(f"Voice file handling error: {str(file_error)}")
            finally:
                try:
                    if voice_file and voice_file.exists():
                        voice_file.unlink()
                        logger.debug("Temporary voice file cleaned up")
                except Exception as e:
                    logger.warning(f"Failed to clean up voice file: {str(e)}")
                
            logger.info("Voice response sent successfully")
            
            try:
                await processing_msg.delete()
                logger.debug("Processing message deleted successfully")
            except Exception as e:
                logger.warning(f"Could not delete processing message: {str(e)}")
            
        except Exception as voice_error:
            logger.error(f"Error generating voice response: {str(voice_error)}")
            logger.error("Full error details:", exc_info=True)
            
            keyboard = [
                [InlineKeyboardButton("Make Diagnosis", callback_data='make_diagnosis')],
                [InlineKeyboardButton("Show Transcription", callback_data='show_transcription')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await processing_msg.edit_text(
                    "Voice generation failed. Sending text response instead.",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.warning(f"Could not update processing message: {str(e)}")
                await update.message.reply_text(response, reply_markup=reply_markup)
        
    except ValueError as ve:
        logger.error(f"Validation error in voice processing: {str(ve)}")
        await update.message.reply_text(
            f"Error: {str(ve)}. Please try again or use text input."
        )
    except Exception as e:
        logger.error(f"Unexpected error in voice processing: {str(e)}")
        await update.message.reply_text(
            "Sorry, an unexpected error occurred while processing your voice message. "
            "Please try again or use text input."
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not conversation_manager.is_conversation_active(user_id):
        await update.message.reply_text(
            "Please start a dialogue first!",
            reply_markup=get_start_dialogue_markup()
        )
        return

    conv_context = conversation_manager.get_conversation_context(user_id)
    
    if context.user_data.get('awaiting_diagnosis', False):
        diagnosis = update.message.text.strip()
        context.user_data['awaiting_diagnosis'] = False  
        
        if not conv_context or 'scenario' not in conv_context:
            await update.message.reply_text("Please start a dialogue first!")
            return
            
        scenario = conv_context['scenario']
        correct_diagnosis = scenario['correct_diagnosis']
        
        try:
            with db_session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                questions_list = conv_context.get('questions_asked', [])
                questions_asked = len(questions_list)
                logger.info(f"Questions asked by user {user_id}: {questions_asked}")
                logger.debug(f"Questions list: {questions_list}")
                
                recommended_questions = set(scenario.get('hints', []))
                asked_questions = set(questions_list)
                missed_questions = recommended_questions - asked_questions if recommended_questions else set()
        except Exception as e:
            logger.error(f"Database error in handle_text (diagnosis feedback): {e}")
            return


        from dialog_manager import string_similarity
        
        def normalize_text(text):
            return ''.join(c.lower() for c in text if c.isalnum())
        
        user_normalized = normalize_text(diagnosis)
        correct_normalized = normalize_text(correct_diagnosis)
        
        full_similarity = string_similarity(user_normalized, correct_normalized)
        
        user_words = set(normalize_text(word) for word in diagnosis.split())
        correct_words = set(normalize_text(word) for word in correct_diagnosis.split())
        
        matching_words = sum(1 for uw in user_words if any(string_similarity(uw, cw) > 0.7 for cw in correct_words))
        word_match_ratio = matching_words / len(correct_words) if correct_words else 0
        
        def has_medical_term_match(user_text, correct_text):
            variations = {
                'pneumonia': ['pneumonia', 'pheumonia', 'pneumoniae', 'pneumonic', 'pneumo'],
                'bacterial': ['bacterial', 'bacteriological', 'bacterium', 'bacteria'],
                'strep': ['strep', 'streptococcal', 'streptococcus'],
                'viral': ['viral', 'virus'],
                'infection': ['infection', 'infected', 'infectious']
            }
            
            for term_group in variations.values():
                if any(var in user_text for var in term_group) and any(var in correct_text for var in term_group):
                    return True
            return False
        
        user_diag_lower = diagnosis.lower()
        correct_diag_lower = correct_diagnosis.lower()
        is_exact_match = user_diag_lower == correct_diag_lower
        is_close_match = (
            full_similarity > 0.6 or 
            word_match_ratio > 0.6 or 
            has_medical_term_match(user_diag_lower, correct_diag_lower) or
            (any(term in user_diag_lower for term in ['pneumonia', 'pheumonia', 'pneumonic']) and 
             any(term in correct_diag_lower for term in ['pneumonia', 'pheumonia', 'pneumonic']))
        )
        is_partial_match = full_similarity > 0.35 or word_match_ratio > 0.35
        
        if is_exact_match:
            feedback = (
                "🎉 Отличная работа! Диагноз поставлен верно!\n\n"
                f"📋 Детали консультации:\n"
                f"• Диагноз: {correct_diagnosis}\n"
                f"• Задано вопросов: {questions_asked}"
            )
        elif is_close_match:
            feedback = (
                "✅ Диагноз верный!\n\n"
                f"📋 Детали консультации:\n"
                f"• Ваш диагноз: {diagnosis}\n"
                f"• Правильное написание: {correct_diagnosis}\n"
                f"• Задано вопросов: {questions_asked}"
            )
        elif is_partial_match:
            feedback = (
                "👍 Почти верно! Вы определили основное заболевание.\n\n"
                f"📋 Детали консультации:\n"
                f"• Ваш диагноз: {diagnosis}\n"
                f"• Полный диагноз: {correct_diagnosis}\n"
                f"• Задано вопросов: {questions_asked}"
            )
        else:
            feedback = (
                "⚠️ Диагноз близок, но требует уточнения.\n\n"
                f"📋 Детали консультации:\n"
                f"• Ваш диагноз: {diagnosis}\n"
                f"• Правильный диагноз: {correct_diagnosis}\n"
                f"• Задано вопросов: {questions_asked}\n\n"
                "💡 Совет: Попробуйте уточнить тип или причину заболевания"
            )
        
        if not is_exact_match and missed_questions:
            feedback += "\n\n💡 Для улучшения диагностики:\n"
            feedback += "Рекомендуемые вопросы:\n"
            feedback += "\n".join(f"• {q}" for q in missed_questions)
        
        try:
            await update.message.reply_text(feedback)
            if 'medical_terms' in scenario and scenario['medical_terms']:
                terms_message = "📚 Медицинские термины по данному случаю:\n\n"
                for term, translations in scenario['medical_terms'].items():
                    terms_message += f"• {translations['en']} - {translations['ru']}\n"
                await update.message.reply_text(terms_message)
            conversation_manager.end_conversation(user_id)
            keyboard = [[InlineKeyboardButton("Start New Dialogue", callback_data='start_dialogue')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "The consultation is complete. Would you like to start a new dialogue?",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error processing diagnosis feedback: {str(e)}")
            await update.message.reply_text(
                "An error occurred while processing your diagnosis. Please try again."
            )
        return

    try:
        conversation_manager.add_question(user_id, update.message.text)
        logger.info(f"Added text question from user {user_id}: {update.message.text[:50]}...")
        response = await generate_response(update.message.text, user_id, conv_context)
    except Exception as e:
        logger.error(f"Error processing text message: {str(e)}")
        response = "Sorry, there was an error processing your message. Please try again."
    
    keyboard = [[InlineKeyboardButton("Make Diagnosis", callback_data='make_diagnosis')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response, reply_markup=reply_markup)

def setup_bot() -> Application:
    """Initialize and configure the bot"""
    application = Application.builder().token(TelegramToken).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    return application