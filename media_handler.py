
import logging
import asyncio
from typing import List, Optional, Dict
from aiogram import Bot, Router
from aiogram.types import Message
from integrated_media_handler import IntegratedMediaHandler
from album_processor import AlbumProcessor, AlbumBuffer as NewAlbumBuffer

logger = logging.getLogger(__name__)

router = Router()

class MediaHandler:
    
    @staticmethod
    async def copy_message_with_entities(bot: Bot, message: Message, target_chat_id: int, user_id: int = 0, task_id: int = 0) -> bool:
        try:
            if user_id and task_id:
                return await IntegratedMediaHandler.process_and_send_message(
                    bot, message, target_chat_id, user_id, task_id
                )
            else:
                await bot.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ الرسالة: {e}")
            return False
    
    @staticmethod
    async def copy_text_message(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            text = message.text or message.caption
            if not text:
                logger.warning("لا يوجد نص للنسخ")
                return False
            
            await bot.send_message(
                chat_id=target_chat_id,
                text=text,
                entities=message.entities or message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ رسالة نصية: {e}")
            return False
    
    @staticmethod
    async def copy_photo(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.photo:
                logger.warning("لا توجد صورة للنسخ")
                return False
            
            await bot.send_photo(
                chat_id=target_chat_id,
                photo=message.photo[-1].file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ صورة: {e}")
            return False
    
    @staticmethod
    async def copy_video(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.video:
                logger.warning("لا يوجد فيديو للنسخ")
                return False
            
            await bot.send_video(
                chat_id=target_chat_id,
                video=message.video.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ فيديو: {e}")
            return False
    
    @staticmethod
    async def copy_document(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.document:
                logger.warning("لا يوجد مستند للنسخ")
                return False
            
            await bot.send_document(
                chat_id=target_chat_id,
                document=message.document.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ مستند: {e}")
            return False
    
    @staticmethod
    async def copy_audio(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.audio:
                logger.warning("لا يوجد صوت للنسخ")
                return False
            
            await bot.send_audio(
                chat_id=target_chat_id,
                audio=message.audio.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ صوت: {e}")
            return False
    
    @staticmethod
    async def copy_voice(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.voice:
                logger.warning("لا توجد رسالة صوتية للنسخ")
                return False
            
            await bot.send_voice(
                chat_id=target_chat_id,
                voice=message.voice.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ رسالة صوتية: {e}")
            return False
    
    @staticmethod
    async def copy_video_note(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.video_note:
                logger.warning("لا يوجد مقطع فيديو دائري للنسخ")
                return False
            
            await bot.send_video_note(
                chat_id=target_chat_id,
                video_note=message.video_note.file_id
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ مقطع فيديو دائري: {e}")
            return False
    
    @staticmethod
    async def copy_animation(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.animation:
                logger.warning("لا يوجد GIF للنسخ")
                return False
            
            await bot.send_animation(
                chat_id=target_chat_id,
                animation=message.animation.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ GIF: {e}")
            return False
    
    @staticmethod
    async def copy_sticker(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            if not message.sticker:
                logger.warning("لا يوجد ملصق للنسخ")
                return False
            
            await bot.send_sticker(
                chat_id=target_chat_id,
                sticker=message.sticker.file_id
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ ملصق: {e}")
            return False
    
    @staticmethod
    async def copy_poll(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            poll = message.poll
            if not poll:
                logger.warning("لا يوجد استطلاع للنسخ")
                return False
            
            await bot.send_poll(
                chat_id=target_chat_id,
                question=poll.question,
                options=[option.text for option in poll.options],
                is_anonymous=poll.is_anonymous,
                type=poll.type,
                allows_multiple_answers=poll.allows_multiple_answers
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ استطلاع: {e}")
            return False
    
    @staticmethod
    async def copy_location(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            location = message.location
            if not location:
                logger.warning("لا يوجد موقع للنسخ")
                return False
            
            await bot.send_location(
                chat_id=target_chat_id,
                latitude=location.latitude,
                longitude=location.longitude
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ موقع: {e}")
            return False
    
    @staticmethod
    async def copy_contact(bot: Bot, message: Message, target_chat_id: int) -> bool:
        try:
            contact = message.contact
            if not contact:
                logger.warning("لا توجد جهة اتصال للنسخ")
                return False
            
            await bot.send_contact(
                chat_id=target_chat_id,
                phone_number=contact.phone_number,
                first_name=contact.first_name,
                last_name=contact.last_name
            )
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ جهة اتصال: {e}")
            return False
    
    @staticmethod
    async def copy_single_message(bot: Bot, message: Message, target_chat_id: int, user_id: int = 0, task_id: int = 0) -> bool:
        if user_id and task_id:
            return await IntegratedMediaHandler.process_and_send_message(
                bot, message, target_chat_id, user_id, task_id
            )
        
        if message.text:
            return await MediaHandler.copy_text_message(bot, message, target_chat_id)
        elif message.photo:
            return await MediaHandler.copy_photo(bot, message, target_chat_id)
        elif message.video:
            return await MediaHandler.copy_video(bot, message, target_chat_id)
        elif message.document:
            return await MediaHandler.copy_document(bot, message, target_chat_id)
        elif message.audio:
            return await MediaHandler.copy_audio(bot, message, target_chat_id)
        elif message.voice:
            return await MediaHandler.copy_voice(bot, message, target_chat_id)
        elif message.video_note:
            return await MediaHandler.copy_video_note(bot, message, target_chat_id)
        elif message.animation:
            return await MediaHandler.copy_animation(bot, message, target_chat_id)
        elif message.sticker:
            return await MediaHandler.copy_sticker(bot, message, target_chat_id)
        elif message.poll:
            return await MediaHandler.copy_poll(bot, message, target_chat_id)
        elif message.location:
            return await MediaHandler.copy_location(bot, message, target_chat_id)
        elif message.contact:
            return await MediaHandler.copy_contact(bot, message, target_chat_id)
        else:
            return await MediaHandler.copy_message_with_entities(bot, message, target_chat_id)


class AlbumBuffer:
    def __init__(self, user_id: int = 0, task_id: int = 0, timeout: float = 1.0):
        self.user_id = user_id
        self.task_id = task_id
        
        if user_id and task_id:
            self.new_buffer = NewAlbumBuffer(timeout=timeout)
            self.album_processor = AlbumProcessor(user_id, task_id)
        else:
            self.new_buffer = None
            self.album_processor = None
        
        self.albums: Dict[str, List[Message]] = {}
    
    async def add_message(self, message: Message, callback=None) -> Optional[List[Message]]:
        if not message.media_group_id:
            return None
        
        media_group_id = message.media_group_id
        
        if self.new_buffer and callback:
            await self.new_buffer.add_message(message, media_group_id, callback)
            return None
        
        if media_group_id not in self.albums:
            self.albums[media_group_id] = []
        
        self.albums[media_group_id].append(message)
        
        return None
    
    def get_album(self, media_group_id: str) -> Optional[List[Message]]:
        return self.albums.get(media_group_id)
    
    def remove_album(self, media_group_id: str):
        if media_group_id in self.albums:
            del self.albums[media_group_id]
    
    async def copy_album(self, bot: Bot, messages: List[Message], target_chat_id: int) -> bool:
        if self.album_processor:
            return await self.album_processor.process_and_send_album(bot, messages, target_chat_id)
        
        try:
            from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
            
            media_group = []
            
            # البحث عن الرسالة التي تحتوي على caption للحفاظ على موقعه
            caption_index = -1
            for idx, msg in enumerate(messages):
                if msg.caption:
                    caption_index = idx
                    break
            
            for i, msg in enumerate(messages):
                # وضع caption في موقعه الأصلي مع الحفاظ على entities
                if i == caption_index:
                    caption = msg.caption
                    caption_entities = msg.caption_entities
                    logger.info(f"📍 [copy_album] وجدت caption في الوسيط {i+1} مع {len(caption_entities) if caption_entities else 0} entities")
                else:
                    caption = None
                    caption_entities = None
                
                if msg.photo:
                    media = InputMediaPhoto(
                        media=msg.photo[-1].file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        parse_mode=None
                    )
                elif msg.video:
                    if not msg.video:
                        continue
                    media = InputMediaVideo(
                        media=msg.video.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        parse_mode=None
                    )
                elif msg.document:
                    if not msg.document:
                        continue
                    media = InputMediaDocument(
                        media=msg.document.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        parse_mode=None
                    )
                elif msg.audio:
                    if not msg.audio:
                        continue
                    media = InputMediaAudio(
                        media=msg.audio.file_id,
                        caption=caption,
                        caption_entities=caption_entities,
                        parse_mode=None
                    )
                else:
                    continue
                
                media_group.append(media)
            
            if media_group:
                await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=media_group
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ ألبوم: {e}")
            return False


album_buffer = AlbumBuffer()
