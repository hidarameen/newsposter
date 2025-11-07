
import logging
from aiogram import Bot
from aiogram.types import Message
from message_processor import MessageProcessor
from album_processor import AlbumProcessor
from entity_handler import EntityHandler
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager
from auto_pin_filter import auto_pin_manager
from auto_delete_manager import auto_delete_manager
from reply_preservation_handler import reply_preservation
from link_preview_manager import LinkPreviewManager
from task_statistics_manager import TaskStatistics
from translation_handler import TranslationHandler

# Configure and initialize logger at module level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedMediaHandler:
    @staticmethod
    async def process_and_send_message(bot: Bot, message: Message, target_chat_id: int, user_id: int, task_id: int) -> bool:
        try:
            logger.info(f"🔧 [User:{user_id} Task:{task_id}] بدء معالجة رسالة للقناة {target_chat_id}")
            processor = MessageProcessor(user_id, task_id)
            settings_manager = TaskSettingsManager(user_id, task_id)
            sub_manager = SubscriptionManager(user_id)
            
            should_process, reason = processor.should_process_message(message)
            if not should_process:
                logger.warning(f"⚠️ [User:{user_id} Task:{task_id}] تم حظر الرسالة: {reason}")
                
                # تسجيل الرسالة المفلترة
                stats = TaskStatistics(user_id, task_id)
                stats.increment_filtered_message('media_filter')
                
                return False
            
            logger.info(f"✅ [User:{user_id} Task:{task_id}] الرسالة مسموحة، بدء معالجة النص")
            
            allowed, processed_text, entities, reason = processor.process_message_text(message)
            if not allowed:
                logger.warning(f"⚠️ [User:{user_id} Task:{task_id}] تم حظر الرسالة بعد معالجة النص: {reason}")
                
                # تسجيل الرسالة المفلترة (تحديد نوع الفلتر من سبب الحظر)
                stats = TaskStatistics(user_id, task_id)
                stats.increment_filtered_message('text_filter')
                
                return False
            
            logger.info(f"✅ [User:{user_id} Task:{task_id}] تمت معالجة النص بنجاح")
            
            # إعدادات الميزات المتقدمة
            settings = settings_manager.load_settings()
            is_premium = sub_manager.is_premium()
            
            # تطبيق الترجمة إذا كانت مفعلة مع الحفاظ على entities
            translation_setting = settings.get('translation', {})
            if is_premium and translation_setting.get('enabled', False) and processed_text:
                translator = TranslationHandler()
                try:
                    translated, translated_text, new_entities = await translator.process_translation(
                        processed_text, 
                        translation_setting,
                        entities
                    )
                    if translated and translated_text:
                        processed_text = translated_text
                        entities = new_entities  # استخدام entities المحدثة بعد الترجمة
                        logger.info(
                            f"✅ [User:{user_id} Task:{task_id}] تمت ترجمة النص بنجاح "
                            f"مع الحفاظ على {len(entities)} entities"
                        )
                        
                        # تتبع إحصائيات الترجمة
                        stats = TaskStatistics(user_id, task_id)
                        stats.increment_translation()
                except Exception as e:
                    logger.error(f"❌ [User:{user_id} Task:{task_id}] خطأ في الترجمة: {e}")
            
            reply_markup = processor.get_reply_markup(message)
            
            # تحويل entities إلى HTML للحصول على التنسيقات الصحيحة
            if entities and processed_text:
                html_text = EntityHandler.entities_to_html(processed_text, entities)
                logger.info(f"🎨 تحويل النص إلى HTML: '{html_text[:100]}...'")
            else:
                html_text = processed_text
            
            # الحصول على reply_to_message_id إذا كان مفعل Reply Preservation
            reply_to_msg_id = None
            reply_preservation_setting = settings.get('reply_preservation', {})
            if is_premium and reply_preservation_setting.get('enabled', False):
                reply_to_msg_id = reply_preservation.get_reply_to_message_id(
                    message, target_chat_id
                )
            
            # الحصول على إعداد Link Preview
            link_preview_setting = settings.get('link_preview', {})
            disable_web_preview = None
            if is_premium and link_preview_setting.get('enabled', False):
                disable_web_preview = LinkPreviewManager.get_link_preview_option(
                    link_preview_setting
                )
            
            logger.info(f"📤 [User:{user_id} Task:{task_id}] بدء الإرسال إلى القناة {target_chat_id}")
            
            sent_msg = None
            
            if message.photo:
                sent_msg = await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=message.photo[-1].file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.video:
                sent_msg = await bot.send_video(
                    chat_id=target_chat_id,
                    video=message.video.file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.document:
                sent_msg = await bot.send_document(
                    chat_id=target_chat_id,
                    document=message.document.file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.audio:
                sent_msg = await bot.send_audio(
                    chat_id=target_chat_id,
                    audio=message.audio.file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.voice:
                sent_msg = await bot.send_voice(
                    chat_id=target_chat_id,
                    voice=message.voice.file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.video_note:
                sent_msg = await bot.send_video_note(
                    chat_id=target_chat_id,
                    video_note=message.video_note.file_id,
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.animation:
                sent_msg = await bot.send_animation(
                    chat_id=target_chat_id,
                    animation=message.animation.file_id,
                    caption=html_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.sticker:
                sent_msg = await bot.send_sticker(
                    chat_id=target_chat_id,
                    sticker=message.sticker.file_id,
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_msg_id
                )
            elif message.text:
                kwargs = {
                    'chat_id': target_chat_id,
                    'text': html_text or message.text,
                    'parse_mode': 'HTML',
                    'reply_markup': reply_markup,
                    'reply_to_message_id': reply_to_msg_id
                }
                if disable_web_preview is not None:
                    kwargs['disable_web_page_preview'] = disable_web_preview
                
                sent_msg = await bot.send_message(**kwargs)
            else:
                result = await bot.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_to_message_id=reply_to_msg_id
                )
                sent_msg = result if hasattr(result, 'message_id') else None
            
            logger.info(f"✅ [User:{user_id} Task:{task_id}] تم إرسال الرسالة بنجاح إلى القناة {target_chat_id}")
            
            # تسجيل الإحصائيات للرسالة الناجحة
            stats = TaskStatistics(user_id, task_id)
            
            # تحديد نوع الوسائط
            if message.photo:
                media_type = 'photo'
            elif message.video:
                media_type = 'video'
            elif message.document:
                media_type = 'document'
            elif message.audio:
                media_type = 'audio'
            elif message.voice:
                media_type = 'voice'
            elif message.video_note:
                media_type = 'video_note'
            elif message.animation:
                media_type = 'animation'
            elif message.sticker:
                media_type = 'sticker'
            else:
                media_type = 'text'
            
            text_length = len(processed_text) if processed_text else 0
            stats.increment_successful_forward(media_type, text_length)
            
            # حفظ mapping للردود
            if is_premium and reply_preservation_setting.get('enabled', False) and sent_msg:
                reply_preservation.store_message_mapping(
                    message.chat.id,
                    message.message_id,
                    target_chat_id,
                    sent_msg.message_id
                )
            
            # تثبيت الرسالة تلقائياً
            auto_pin_setting = settings.get('auto_pin', {})
            if is_premium and auto_pin_setting.get('enabled', False) and sent_msg:
                await auto_pin_manager.pin_message(
                    bot,
                    target_chat_id,
                    sent_msg.message_id,
                    auto_pin_setting.get('disable_notification', True),
                    auto_pin_setting.get('delete_notification_after')
                )
                # تتبع إحصائيات التثبيت التلقائي
                stats = TaskStatistics(user_id, task_id)
                stats.increment_auto_pin()
            
            # جدولة الحذف التلقائي
            auto_delete_setting = settings.get('auto_delete', {})
            if is_premium and auto_delete_setting.get('enabled', False) and sent_msg:
                delay_value = auto_delete_setting.get('delay_value', 60)
                delay_unit = auto_delete_setting.get('delay_unit', 'minutes')
                delay_seconds = auto_delete_manager.convert_time_to_seconds(
                    delay_value, delay_unit
                )
                
                auto_delete_manager.schedule_deletion(
                    bot,
                    target_chat_id,
                    sent_msg.message_id,
                    delay_seconds,
                    task_id
                )
                # تتبع إحصائيات الحذف التلقائي
                stats = TaskStatistics(user_id, task_id)
                stats.increment_auto_delete()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [User:{user_id} Task:{task_id}] خطأ في معالجة وإرسال الرسالة إلى {target_chat_id}: {e}", exc_info=True)
            
            # تسجيل الفشل
            stats = TaskStatistics(user_id, task_id)
            stats.increment_failed_forward()
            
            return False
