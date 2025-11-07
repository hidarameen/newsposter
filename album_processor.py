import asyncio
from typing import Dict, List, Optional, Tuple
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from aiogram import Bot
from message_processor import MessageProcessor
from entity_handler import EntityHandler
import logging

# إنشاء logger للملف
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AlbumBuffer:
    def __init__(self, timeout: float = 1.0):
        self.albums: Dict[str, List[Message]] = {}
        self.timeout = timeout
        self.tasks: Dict[str, asyncio.Task] = {}

    async def add_message(self, message: Message, media_group_id: str, callback):
        if media_group_id not in self.albums:
            self.albums[media_group_id] = []

        self.albums[media_group_id].append(message)

        if media_group_id in self.tasks:
            self.tasks[media_group_id].cancel()

        self.tasks[media_group_id] = asyncio.create_task(
            self._process_album_after_timeout(media_group_id, callback)
        )

    async def _process_album_after_timeout(self, media_group_id: str, callback):
        try:
            await asyncio.sleep(self.timeout)

            if media_group_id in self.albums:
                album_messages = self.albums[media_group_id]
                del self.albums[media_group_id]

                if media_group_id in self.tasks:
                    del self.tasks[media_group_id]

                await callback(album_messages)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"خطأ في معالجة الألبوم {media_group_id}: {e}")

class AlbumProcessor:
    def __init__(self, user_id: int, task_id: int):
        self.user_id = user_id
        self.task_id = task_id
        self.message_processor = MessageProcessor(user_id, task_id)

    async def process_and_send_album(self, bot: Bot, album_messages: List[Message], target_chat_id: int) -> bool:
        try:
            # فحص جميع الوسائط في الألبوم
            logger.info(f"🔍 [ALBUM] بدء فحص ألبوم يحتوي على {len(album_messages)} وسائط")
            for idx, msg in enumerate(album_messages, 1):
                should_process, reason = self.message_processor.should_process_message(msg)
                if not should_process:
                    logger.info(f"❌ [ALBUM] تم حظر الألبوم: الوسيط #{idx} محظور - {reason}")
                    return False
            
            logger.info(f"✅ [ALBUM] جميع الوسائط مسموحة - بدء المعالجة")

            # البحث عن الرسالة التي تحتوي على caption
            caption_message = None
            caption_message_index = -1
            for idx, msg in enumerate(album_messages):
                if msg.caption:
                    caption_message = msg
                    caption_message_index = idx
                    logger.info(f"📍 [ALBUM] وجدت caption في الصورة #{idx+1} من {len(album_messages)}")
                    break

            # معالجة caption إذا وجد
            processed_text = None
            entities_list = []

            if caption_message:
                logger.info(f"\n{'='*80}")
                logger.info(f"🔬 [خطوة 1] الـ caption الأصلي من الرسالة:")
                logger.info(f"{'='*80}")
                original_caption = caption_message.caption or ""
                original_caption_entities = caption_message.caption_entities

                logger.info(f"📝 النص: '{original_caption}'")
                logger.info(f"📏 طول النص: {len(original_caption)} حرف")
                logger.info(f"📌 عدد Entities الأصلية: {len(original_caption_entities) if original_caption_entities else 0}")

                if original_caption_entities:
                    for i, ent in enumerate(original_caption_entities, 1):
                        text_part = original_caption[ent.offset:ent.offset+ent.length] if ent.offset + ent.length <= len(original_caption) else '???'
                        logger.info(f"   {i}. {ent.type}: '{text_part}' (offset={ent.offset}, length={ent.length})")

                # معالجة النص
                logger.info(f"\n{'='*80}")
                logger.info(f"🔬 [خطوة 2] إرسال للمعالج (MessageProcessor):")
                logger.info(f"{'='*80}")

                allowed, processed_text, entities, reason = self.message_processor.process_message_text(caption_message)

                if not allowed:
                    logger.error(f"❌ [ALBUM] تم حظر الألبوم: {reason}")
                    return False

                logger.info(f"✅ [ALBUM] تم قبول الرسالة للمعالجة")
                logger.info(f"📝 النص بعد المعالجة: '{processed_text}'")
                logger.info(f"📏 طول النص بعد المعالجة: {len(processed_text) if processed_text else 0} حرف")
                logger.info(f"📌 عدد Entities المرجعة (dict format): {len(entities) if entities else 0}")

                if entities:
                    for i, e in enumerate(entities, 1):
                        logger.info(f"   {i}. Dict Entity: type={e.get('type')}, offset={e.get('offset')}, length={e.get('length')}")

                # تحويل entities من dict إلى MessageEntity
                logger.info(f"\n{'='*80}")
                logger.info(f"🔬 [خطوة 3] تحويل Entities من dict إلى MessageEntity:")
                logger.info(f"{'='*80}")

                entities_list = EntityHandler.dict_to_entities(entities) if entities else []

                logger.info(f"📌 عدد Entities بعد التحويل: {len(entities_list)}")

                if entities_list:
                    for i, ent in enumerate(entities_list, 1):
                        if processed_text and ent.offset + ent.length <= len(processed_text):
                            text_part = processed_text[ent.offset:ent.offset+ent.length]
                            logger.info(f"   {i}. MessageEntity: type={ent.type}, offset={ent.offset}, length={ent.length}, text='{text_part}'")
                        else:
                            logger.info(f"   {i}. MessageEntity: type={ent.type}, offset={ent.offset}, length={ent.length}, text='⚠️ خارج النطاق'")
                else:
                    logger.warning(f"⚠️ [ALBUM] لا توجد entities بعد التحويل!")

            else:
                logger.info(f"ℹ️ [ALBUM] لا يوجد caption في الألبوم")

            # بناء media_group مع وضع caption في موضعه الأصلي
            logger.info(f"\n{'='*80}")
            logger.info(f"🔬 [خطوة 4] بناء Media Group:")
            logger.info(f"{'='*80}")

            media_group = []
            for idx, message in enumerate(album_messages):
                logger.info(f"\n📸 [صورة {idx+1}/{len(album_messages)}]:")

                # إذا كانت هذه الصورة تحتوي على caption، ضع caption المعالج
                if idx == caption_message_index:
                    logger.info(f"   ✅ هذه الصورة تحتوي على caption")
                    logger.info(f"   📝 Caption: '{processed_text[:50]}...' ({len(processed_text) if processed_text else 0} حرف)")
                    logger.info(f"   📌 Entities: {len(entities_list)} entity")
                    media_item = self._create_media_item(message, processed_text, entities_list)
                else:
                    logger.info(f"   ⬜ صورة بدون caption")
                    media_item = self._create_media_item(message, None, None)

                if media_item:
                    media_group.append(media_item)
                    logger.info(f"   ✅ تمت إضافة الوسيط إلى media_group")
                else:
                    logger.warning(f"   ⚠️ فشل إنشاء media_item")

            if not media_group:
                logger.warning("لا توجد وسائط صالحة في الألبوم")
                return False

            # تقسيم الألبوم إلى مجموعات (10 وسائط كحد أقصى لكل مجموعة)
            logger.info(f"\n{'='*80}")
            logger.info(f"🔬 [خطوة 5] إرسال الألبوم:")
            logger.info(f"{'='*80}")

            MAX_MEDIA_PER_ALBUM = 10
            media_chunks = [media_group[i:i + MAX_MEDIA_PER_ALBUM] for i in range(0, len(media_group), MAX_MEDIA_PER_ALBUM)]

            logger.info(f"📦 عدد الوسائط الكلي: {len(media_group)}")
            logger.info(f"📦 عدد المجموعات: {len(media_chunks)}")

            for chunk_idx, chunk in enumerate(media_chunks, 1):
                logger.info(f"\n📤 إرسال المجموعة {chunk_idx}/{len(media_chunks)} ({len(chunk)} وسائط)...")

                # فحص الوسيط الذي يحتوي على caption
                for i, media in enumerate(chunk):
                    if media.caption:
                        logger.info(f"   ✅ الوسيط {i+1} يحتوي على caption ({len(media.caption)} حرف)")
                        logger.info(f"   📌 عدد Entities: {len(media.caption_entities) if media.caption_entities else 0}")
                        if media.caption_entities:
                            for j, e in enumerate(media.caption_entities[:3], 1):
                                logger.info(f"      {j}. {e.type} at {e.offset}:{e.offset+e.length}")

                await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=chunk
                )
                logger.info(f"   ✅ تم إرسال المجموعة {chunk_idx} بنجاح")

            # إرسال reply_markup إذا وجد (من الرسالة التي تحتوي على caption)
            if caption_message:
                reply_markup = self.message_processor.get_reply_markup(caption_message)
                if reply_markup:
                    logger.info(f"📤 إرسال أزرار reply_markup...")
                    await bot.send_message(
                        chat_id=target_chat_id,
                        text="⬆️",
                        reply_markup=reply_markup
                    )

            logger.info(f"\n{'='*80}")
            logger.info(f"✅ [النتيجة النهائية] تم إرسال الألبوم بنجاح!")
            logger.info(f"{'='*80}")
            logger.info(f"   📊 إحصائيات:")
            logger.info(f"      - عدد الوسائط: {len(media_group)}")
            logger.info(f"      - عدد المجموعات: {len(media_chunks)}")
            logger.info(f"      - Caption: {'موجود' if processed_text else 'غير موجود'}")
            logger.info(f"      - Entities: {len(entities_list)} entity")
            logger.info(f"{'='*80}\n")

            return True

        except Exception as e:
            logger.error(f"❌ خطأ في معالجة وإرسال الألبوم: {e}")
            return False

    def _create_media_item(self, message: Message, caption: Optional[str] = None, caption_entities = None):
        try:
            logger.info(f"\n   🔨 [_create_media_item] بدء إنشاء media item:")
            logger.info(f"      📥 المدخلات:")
            logger.info(f"         - caption: {'موجود' if caption else 'None'} ({len(caption) if caption else 0} حرف)")
            logger.info(f"         - caption_entities: {type(caption_entities).__name__} ({len(caption_entities) if isinstance(caption_entities, list) else 'N/A'})")

            # معالجة caption_entities بشكل صحيح
            # القاعدة:
            # - إذا لا يوجد caption → caption_entities = None
            # - إذا يوجد caption بدون entities → caption_entities = []
            # - إذا يوجد caption مع entities → caption_entities = [list of entities]

            original_entities_count = len(caption_entities) if isinstance(caption_entities, list) else 0

            if caption is None:
                # لا يوجد caption → لا entities
                caption_entities = None
                logger.info(f"      📋 القرار: لا caption → entities = None")
            elif caption_entities is None:
                # يوجد caption لكن لم يتم تمرير entities → قائمة فارغة
                caption_entities = []
                logger.info(f"      📋 القرار: يوجد caption بدون entities → entities = []")
            else:
                # استخدم entities الممررة كما هي
                logger.info(f"      📋 القرار: الحفاظ على {len(caption_entities)} entities")

            logger.info(f"      📤 المخرجات:")
            logger.info(f"         - caption: {'موجود' if caption else 'None'}")
            logger.info(f"         - caption_entities: {type(caption_entities).__name__} ({len(caption_entities) if isinstance(caption_entities, list) else 'N/A'})")

            if caption_entities and isinstance(caption_entities, list) and len(caption_entities) > 0:
                logger.info(f"      📌 تفاصيل Entities ({len(caption_entities)}):")
                for i, ent in enumerate(caption_entities, 1):
                    if caption and ent.offset + ent.length <= len(caption):
                        text_part = caption[ent.offset:ent.offset+ent.length]
                        logger.info(f"         {i}. {ent.type}: '{text_part}' (offset={ent.offset}, length={ent.length})")
                    else:
                        logger.info(f"         {i}. {ent.type}: (offset={ent.offset}, length={ent.length}) ⚠️")

            # التحقق من التطابق
            if original_entities_count > 0 and isinstance(caption_entities, list):
                if len(caption_entities) == original_entities_count:
                    logger.info(f"      ✅ تطابق: تم الحفاظ على جميع الـ {original_entities_count} entities")
                else:
                    logger.error(f"      ❌ عدم تطابق: {original_entities_count} → {len(caption_entities)} entities!")

            if message.photo:
                media_item = InputMediaPhoto(
                    media=message.photo[-1].file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                    parse_mode=None
                )
                logger.info(f"      ✅ تم إنشاء InputMediaPhoto بنجاح")
                return media_item
            elif message.video:
                media_item = InputMediaVideo(
                    media=message.video.file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                    parse_mode=None
                )
                logger.info(f"      ✅ تم إنشاء InputMediaVideo بنجاح")
                return media_item
            elif message.document:
                media_item = InputMediaDocument(
                    media=message.document.file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                    parse_mode=None
                )
                logger.info(f"      ✅ تم إنشاء InputMediaDocument بنجاح")
                return media_item
            elif message.audio:
                media_item = InputMediaAudio(
                    media=message.audio.file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                    parse_mode=None
                )
                logger.info(f"      ✅ تم إنشاء InputMediaAudio بنجاح")
                return media_item

            return None

        except Exception as e:
            logger.error(f"خطأ في إنشاء عنصر وسائط: {e}")
            logger.exception(e)
            return None

    def is_album_allowed(self, album_messages: List[Message]) -> Tuple[bool, str]:
        from media_filters import MediaFilters
        settings = self.message_processor.settings_manager.load_settings()

        media_filter = settings['media_filters']
        if media_filter['enabled']:
            for message in album_messages:
                if not MediaFilters.is_media_allowed(message, media_filter['allowed_types']):
                    return False, "نوع الوسائط في الألبوم غير مسموح"

        return True, ""