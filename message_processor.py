import logging
from typing import Optional, Tuple, Dict, List
from aiogram.types import Message, InlineKeyboardMarkup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager
from entity_handler import EntityHandler
from text_filters import TextFilters
from link_filters import LinkFilters
from button_filters import ButtonFilters
from media_filters import MediaFilters
from language_filters import LanguageFilters
from button_parser import ButtonParser
from day_filter import DayFilter
from hour_filter import HourFilter
from character_limit_filter import CharacterLimitFilter
from timezone_manager import TimezoneManager

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self, user_id: int, task_id: int):
        self.user_id = user_id
        self.task_id = task_id
        self.settings_manager = TaskSettingsManager(user_id, task_id)
        self.subscription_manager = SubscriptionManager(user_id)

    def should_process_message(self, message: Message) -> Tuple[bool, str]:
        settings = self.settings_manager.load_settings()
        is_premium = self.subscription_manager.is_premium()

        # الحصول على المنطقة الزمنية
        tz_manager = TimezoneManager(self.user_id)
        timezone = tz_manager.get_timezone()

        # فلتر الأيام
        day_filter = settings.get('day_filter', {})
        if is_premium and day_filter.get('enabled', False):
            allowed, reason = DayFilter.check_day_allowed(day_filter, timezone)
            if not allowed:
                return False, reason

        # فلتر الساعات
        hour_filter = settings.get('hour_filter', {})
        if is_premium and hour_filter.get('enabled', False):
            allowed, reason = HourFilter.check_hour_allowed(hour_filter, timezone)
            if not allowed:
                return False, reason

        media_filter = settings['media_filters']
        if media_filter['enabled']:
            if not MediaFilters.is_media_allowed(message, media_filter['allowed_types']):
                return False, "نوع الوسائط غير مسموح"

        forwarded_filter = settings['forwarded_filter']
        if is_premium and forwarded_filter['enabled']:
            is_forwarded = message.forward_date is not None
            if not TextFilters.check_forwarded_filter(is_forwarded, forwarded_filter['mode']):
                return False, "رسالة موجهة محظورة"

        button_filter = settings['button_filter']
        if is_premium and button_filter['enabled']:
            allowed, _ = ButtonFilters.apply_button_filter(message.reply_markup, button_filter['mode'])
            if not allowed:
                return False, "الرسالة تحتوي على أزرار محظورة"

        return True, ""

    def process_message_text(self, message: Message) -> Tuple[bool, Optional[str], List[Dict], str]:
        text = message.text or message.caption or ""
        original_entities = message.entities or message.caption_entities

        logger.info(f"🔍 process_message_text - النص الأصلي: '{text}'")
        logger.info(f"🔍 process_message_text - entities أصلية: {len(original_entities) if original_entities else 0}")
        if original_entities:
            for e in original_entities:
                logger.info(f"   Original Entity: {e.type} at {e.offset}:{e.offset+e.length}")

        entities = EntityHandler.entities_to_dict(original_entities, text)
        logger.info(f"🔍 بعد entities_to_dict: {len(entities)} entities")

        if not text:
            return True, text, entities, ""

        settings = self.settings_manager.load_settings()
        is_premium = self.subscription_manager.is_premium()

        # فلتر حدود الأحرف
        char_limit = settings.get('character_limit', {})
        if is_premium and char_limit.get('enabled', False):
            allowed, reason = CharacterLimitFilter.check_character_limit(text, char_limit)
            if not allowed:
                return False, None, [], reason

        whitelist = settings['whitelist_words']
        if is_premium and whitelist['enabled']:
            allowed, reason = TextFilters.apply_whitelist(text, whitelist['words'])
            if not allowed:
                return False, None, [], reason

        blacklist = settings['blacklist_words']
        if is_premium and blacklist['enabled']:
            allowed, reason = TextFilters.apply_blacklist(text, blacklist['words'])
            if not allowed:
                return False, None, [], reason

        language_filter = settings['language_filter']
        if is_premium and language_filter['enabled']:
            allowed, reason = LanguageFilters.apply_language_filter(
                text,
                language_filter['mode'],
                language_filter['languages'],
                language_filter['sensitivity']
            )
            if not allowed:
                return False, None, [], reason

        link_mgmt = settings['link_management']
        if is_premium and link_mgmt['enabled']:
            allowed, text, entities = LinkFilters.apply_link_filter(text, link_mgmt['mode'], entities)
            if not allowed:
                return False, None, [], text

        replacements = settings['replacements']
        if is_premium and replacements['enabled']:
            text, entities = TextFilters.apply_replacements(text, replacements['pairs'], entities)

        # تخطي الترجمة في process_message_text لأنها غير async
        # الترجمة سيتم تطبيقها في integrated_media_handler.py الذي يستخدم async
        # translation = settings.get('translation', {})
        # if is_premium and translation.get('enabled', False) and text:
        #     from translation_handler import TranslationHandler
        #     translator = TranslationHandler()
        #     try:
        #         translated, translated_text = await translator.process_translation(text, translation)
        #         if translated and translated_text:
        #             text = translated_text
        #             logger.info(f"✅ تمت ترجمة النص بنجاح")
        #     except Exception as e:
        #         logger.error(f"❌ خطأ في الترجمة: {e}")

        # تعطيل إضافة emoji مؤقتاً للحفاظ على entities
        # سيتم إعادة تفعيله بعد إصلاح حساب الـ offsets
        # text, entities = self.add_emoji_prefix(text, entities)

        # معالجة الهيدر مع الحفاظ الكامل على entities
        # التأكد من أن المهمة للمستخدم (وليست إدارية)
        header = settings['header']
        if is_premium and header['enabled'] and header['text'] and self.user_id and self.task_id:
            header_saved_entities = header.get('entities', [])
            logger.info(f"📋 هيدر - النص: '{header['text']}'")
            logger.info(f"📋 هيدر - entities محفوظة: {len(header_saved_entities)}")
            
            # حساب الإزاحة الصحيحة بصيغة UTF-16
            # الهيدر + سطر جديد
            header_with_newline = header['text'] + '\n'
            
            # حساب طول الهيدر بصيغة UTF-16
            shift_amount = 0
            for char in header_with_newline:
                # Emoji والأحرف الخاصة (> U+FFFF) تأخذ 2 units في UTF-16
                if ord(char) > 0xFFFF:
                    shift_amount += 2
                else:
                    shift_amount += 1
            
            logger.info(f"📋 إزاحة الهيدر (UTF-16): {shift_amount} (طول Python: {len(header_with_newline)})")
            
            # shift entities الرسالة الأصلية
            shifted_message_entities = EntityHandler.shift_entities(entities, shift_amount)
            logger.info(f"📋 entities الرسالة بعد الإزاحة: {len(shifted_message_entities)}")
            
            # دمج entities الهيدر مع entities الرسالة المزاحة
            entities = EntityHandler.merge_entities(header_saved_entities, shifted_message_entities)
            logger.info(f"📋 بعد دمج الهيدر: {len(entities)} entities")
            
            # تحديث النص
            text = header['text'] + '\n' + text

        # معالجة الفوتر مع الحفاظ الكامل على entities
        # التأكد من أن المهمة للمستخدم (وليست إدارية)
        footer = settings['footer']
        if is_premium and footer['enabled'] and footer['text'] and self.user_id and self.task_id:
            footer_saved_entities = footer.get('entities', [])
            logger.info(f"📋 فوتر - النص: '{footer['text']}'")
            logger.info(f"📋 فوتر - entities محفوظة: {len(footer_saved_entities)}")
            
            # حساب الإزاحة الصحيحة بصيغة UTF-16
            # النص الحالي + سطر جديد
            current_text_with_newline = text + '\n'
            
            # حساب طول النص الحالي بصيغة UTF-16
            shift_amount = 0
            for char in current_text_with_newline:
                if ord(char) > 0xFFFF:
                    shift_amount += 2
                else:
                    shift_amount += 1
            
            logger.info(f"📋 إزاحة الفوتر (UTF-16): {shift_amount} (طول Python: {len(current_text_with_newline)})")
            
            # shift entities الفوتر
            shifted_footer_entities = EntityHandler.shift_entities(footer_saved_entities, shift_amount)
            
            # دمج entities الحالية مع entities الفوتر المزاحة
            entities = EntityHandler.merge_entities(entities, shifted_footer_entities)
            logger.info(f"📋 بعد دمج الفوتر: {len(entities)} entities")
            
            # تحديث النص
            text = text + '\n' + footer['text']

        # تطبيق تنسيق النص الموحد (آخر خطوة قبل الإرسال)
        text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
        if is_premium and text_format.get('enabled', False) and text_format.get('format_type'):
            from text_formatter import TextFormatter
            
            format_type = text_format['format_type']
            text_link_url = text_format.get('text_link_url', '')
            logger.info(f"🎨 [TextFormat] تطبيق تنسيق '{format_type}' على النص النهائي")
            logger.info(f"   📊 قبل التنسيق: {len(entities) if entities else 0} entities")
            
            text, entities = TextFormatter.apply_format(text, entities, format_type, text_link_url)
            
            logger.info(f"   📊 بعد التنسيق: {len(entities) if entities else 0} entities")

        logger.info(f"🔍 process_message_text - النص النهائي: '{text}'")
        logger.info(f"🔍 process_message_text - entities نهائية (dict): {len(entities) if entities else 0}")
        if entities:
            for e in entities[:5]:  # أول 5 فقط
                logger.info(f"   Final Entity (dict): {e}")

        return True, text, entities, ""

    def get_reply_markup(self, message: Message, post_url: Optional[str] = None, message_text: Optional[str] = None) -> Optional[InlineKeyboardMarkup]:
        settings = self.settings_manager.load_settings()
        is_premium = self.subscription_manager.is_premium()

        button_filter = settings['button_filter']
        if is_premium and button_filter['enabled'] and button_filter['mode'] == 'remove':
            reply_markup = None
        else:
            reply_markup = message.reply_markup

        inline_buttons = settings['inline_buttons']
        if is_premium and inline_buttons['enabled'] and inline_buttons['buttons']:
            # استخدام نص الرسالة أو الكابشن
            text_for_sharing = message_text or message.text or message.caption or ''
            custom_markup = ButtonParser.buttons_to_markup(inline_buttons['buttons'], post_url or '', text_for_sharing)

            if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
                combined_keyboard = custom_markup.inline_keyboard + reply_markup.inline_keyboard
                return InlineKeyboardMarkup(inline_keyboard=combined_keyboard)
            else:
                return custom_markup

        return reply_markup

    def get_settings_summary(self) -> str:
        settings = self.settings_manager.load_settings()
        is_premium = self.subscription_manager.is_premium()

        summary = "⚙️ <b>ملخص الإعدادات النشطة:</b>\n\n"

        active_filters = []

        if settings['media_filters']['enabled']:
            active_filters.append(f"📹 فلاتر الوسائط")

        if is_premium and settings['header']['enabled']:
            active_filters.append(f"📝 رأس الرسالة")

        if is_premium and settings['footer']['enabled']:
            active_filters.append(f"📝 ذيل الرسالة")

        if is_premium and settings['inline_buttons']['enabled']:
            active_filters.append(f"🔘 أزرار إنلاين")

        if is_premium and settings['whitelist_words']['enabled']:
            active_filters.append(f"✅ قائمة بيضاء ({len(settings['whitelist_words']['words'])} كلمات)")

        if is_premium and settings['blacklist_words']['enabled']:
            active_filters.append(f"🚫 قائمة سوداء ({len(settings['blacklist_words']['words'])} كلمات)")

        if is_premium and settings['replacements']['enabled']:
            active_filters.append(f"🔄 استبدالات ({len(settings['replacements']['pairs'])} استبدال)")

        if is_premium and settings['link_management']['enabled']:
            active_filters.append(f"🔗 إدارة الروابط ({settings['link_management']['mode']})")

        if is_premium and settings['button_filter']['enabled']:
            active_filters.append(f"🚫 فلتر الأزرار ({settings['button_filter']['mode']})")

        if is_premium and settings['forwarded_filter']['enabled']:
            active_filters.append(f"↪️ فلتر الرسائل الموجهة ({settings['forwarded_filter']['mode']})")

        if is_premium and settings['language_filter']['enabled']:
            active_filters.append(f"🌐 فلتر اللغة ({settings['language_filter']['mode']})")

        if is_premium and settings.get('day_filter', {}).get('enabled', False):
            active_filters.append(f"📅 فلتر الأيام ({settings['day_filter']['mode']})")

        if is_premium and settings.get('hour_filter', {}).get('enabled', False):
            active_filters.append(f"🕒 فلتر الساعات ({settings['hour_filter']['mode']})")

        if is_premium and settings.get('character_limit', {}).get('enabled', False):
            active_filters.append(f"📏 حدود الأحرف ({settings['character_limit']['mode']})")

        if is_premium and settings.get('translation', {}).get('enabled', False):
            active_filters.append(f"🌍 ترجمة النصوص")

        if is_premium and settings.get('auto_pin', {}).get('enabled', False):
            active_filters.append(f"📌 تثبيت تلقائي")

        if is_premium and settings.get('auto_delete', {}).get('enabled', False):
            active_filters.append(f"🗑️ حذف تلقائي")

        if is_premium and settings.get('reply_preservation', {}).get('enabled', False):
            active_filters.append(f"💬 حفظ الردود")

        if is_premium and settings.get('link_preview', {}).get('enabled', False):
            active_filters.append(f"🔗 معاينة الروابط ({settings['link_preview']['mode']})")

        if active_filters:
            summary += "\n".join([f"  • {f}" for f in active_filters])
        else:
            summary += "لا توجد فلاتر نشطة"

        return summary

    def add_emoji_prefix(self, text: str, entities: List[Dict]) -> Tuple[str, List[Dict]]:
        """إضافة emoji في بداية كل سطر مع إعادة حساب دقيقة للـ entities"""
        if not text:
            return text, entities

        emoji = "🔴"
        emoji_len = len(emoji)  # عدد الأحرف (1 حرف emoji)

        lines = text.split('\n')
        new_text = ""
        offset_map = {}  # خريطة لتتبع الموقع القديم -> الجديد

        current_old_pos = 0
        current_new_pos = 0

        for i, line in enumerate(lines):
            # حفظ موقع بداية السطر
            offset_map[current_old_pos] = current_new_pos

            if line.strip():  # سطر غير فارغ
                new_text += emoji + line

                # تتبع كل موقع في السطر
                for j in range(len(line)):
                    old_pos = current_old_pos + j
                    new_pos = current_new_pos + emoji_len + j
                    offset_map[old_pos] = new_pos

                current_old_pos += len(line)
                current_new_pos += emoji_len + len(line)
            else:  # سطر فارغ
                new_text += line
                current_old_pos += len(line)
                current_new_pos += len(line)

            # إضافة newline إذا لم نكن في آخر سطر
            if i < len(lines) - 1:
                new_text += '\n'
                offset_map[current_old_pos] = current_new_pos
                current_old_pos += 1
                current_new_pos += 1

        # تعديل مواقع الـ entities
        if entities:
            adjusted_entities = []

            for entity in entities:
                old_offset = entity['offset']

                # إيجاد أقرب موقع في الخريطة
                if old_offset in offset_map:
                    new_offset = offset_map[old_offset]
                else:
                    # إيجاد أقرب موقع أصغر
                    closest_offset = max([k for k in offset_map.keys() if k <= old_offset], default=0)
                    diff = old_offset - closest_offset
                    new_offset = offset_map[closest_offset] + diff

                new_entity = entity.copy()
                new_entity['offset'] = new_offset
                adjusted_entities.append(new_entity)

            return new_text, adjusted_entities

        return new_text, entities