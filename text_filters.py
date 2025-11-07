import re
from typing import Optional, Tuple, List, Dict

class TextFilters:
    @staticmethod
    def apply_whitelist(text: str, whitelist: List[str]) -> Tuple[bool, str]:
        if not whitelist:
            return True, text

        text_lower = text.lower()

        for word in whitelist:
            word_pattern = r'\b' + re.escape(word.lower()) + r'\b'
            if re.search(word_pattern, text_lower):
                return True, text

        return False, "الرسالة لا تحتوي على الكلمات المسموحة"

    @staticmethod
    def apply_blacklist(text: str, blacklist: List[str]) -> Tuple[bool, str]:
        if not blacklist:
            return True, text

        text_lower = text.lower()

        for word in blacklist:
            word_pattern = r'\b' + re.escape(word.lower()) + r'\b'
            if re.search(word_pattern, text_lower):
                return False, f"الرسالة تحتوي على كلمة محظورة: {word}"

        return True, text

    @staticmethod
    def apply_replacements(text: str, replacements: List[Dict], entities: List[Dict] = None) -> Tuple[str, List[Dict]]:
        if not replacements:
            return text, entities or []

        from entity_handler import EntityHandler
        import logging
        logger = logging.getLogger(__name__)

        new_text = text
        new_entities = entities or []

        # استخدام 'pairs' بدلاً من 'replacements' للاتساق مع أسماء المتغيرات في الكود الأصلي
        pairs = replacements

        for replacement in pairs:
            old_word = replacement.get('old', '')
            new_word = replacement.get('new', '')
            old_entities_data = replacement.get('old_entities', [])
            new_entities_data = replacement.get('new_entities', [])

            if not old_word:
                continue

            logger.info(f"🔄 محاولة استبدال '{old_word}' بـ '{new_word}'")
            logger.info(f"   old_entities من الملف: {len(old_entities_data)} items")
            logger.info(f"   new_entities من الملف: {len(new_entities_data)} items")
            
            if old_entities_data:
                logger.info(f"   محتوى old_entities_data:")
                for i, e in enumerate(old_entities_data):
                    logger.info(f"      [{i}] type={e.get('type')}, offset={e.get('offset')}, length={e.get('length')}")
            else:
                logger.warning(f"   ⚠️ old_entities_data فارغة!")
            
            if new_entities_data:
                logger.info(f"   محتوى new_entities_data:")
                for i, e in enumerate(new_entities_data):
                    logger.info(f"      [{i}] type={e.get('type')}, offset={e.get('offset')}, length={e.get('length')}")
            else:
                logger.warning(f"   ⚠️ new_entities_data فارغة!")

            # البحث عن جميع مواقع النص القديم
            old_word_lower = old_word.lower()
            text_lower = new_text.lower()

            start_pos = 0
            replacements_made = []

            while True:
                pos = text_lower.find(old_word_lower, start_pos)
                if pos == -1:
                    break

                # التأكد من أنها كلمة كاملة (اختياري - يمكن إزالته للسماح بالاستبدال الجزئي)
                is_word_boundary = True
                if pos > 0 and new_text[pos-1].isalnum():
                    is_word_boundary = False
                if pos + len(old_word) < len(new_text) and new_text[pos + len(old_word)].isalnum():
                    is_word_boundary = False

                if is_word_boundary:
                    replacements_made.append(pos)

                start_pos = pos + 1

            # تطبيق الاستبدالات من الآخر للأول لعدم تأثير المواقع
            for pos in reversed(replacements_made):
                # حساب المواقع بصيغة UTF-16
                pos_utf16 = EntityHandler.python_offset_to_utf16(new_text, pos)
                
                # حساب الطول الصحيح بصيغة UTF-16
                old_end_pos = pos + len(old_word)
                old_end_utf16 = EntityHandler.python_offset_to_utf16(new_text, old_end_pos)
                old_len_utf16 = old_end_utf16 - pos_utf16
                
                # حساب طول النص الجديد بصيغة UTF-16
                new_end_utf16 = EntityHandler.python_offset_to_utf16(new_word, len(new_word))
                new_len_utf16 = new_end_utf16
                
                diff = new_len_utf16 - old_len_utf16

                logger.info(f"🔄 استبدال '{old_word}' بـ '{new_word}' في الموقع {pos} (UTF-16: {pos_utf16})")
                logger.info(f"   📏 old_len_utf16={old_len_utf16}, new_len_utf16={new_len_utf16}, diff={diff}")

                # استبدال النص
                new_text = new_text[:pos] + new_word + new_text[pos + len(old_word):]

                # تحديث entities:
                # 1. حذف entities القديمة في موقع الاستبدال
                # 2. إضافة entities الجديدة المحفوظة
                # 3. تحديث مواقع entities التي بعد الاستبدال

                updated_entities = []

                for entity in new_entities:
                    entity_offset = entity['offset']
                    entity_length = entity['length']
                    entity_end = entity_offset + entity_length

                    # إذا كانت entity قبل موقع الاستبدال، نحافظ عليها كما هي
                    if entity_end <= pos_utf16:
                        updated_entities.append(entity)
                        logger.info(f"   ✓ حفظ entity قبل الاستبدال: type={entity['type']}, offset={entity_offset}")
                    # إذا كانت entity بعد موقع الاستبدال، نحرك offset
                    elif entity_offset >= pos_utf16 + old_len_utf16:
                        entity = entity.copy()
                        entity['offset'] += diff
                        updated_entities.append(entity)
                        logger.info(f"   ↔️ تحريك entity بعد الاستبدال: type={entity['type']}, offset {entity_offset} → {entity['offset']}")
                    else:
                        # entity تتقاطع مع النص المستبدل، نتجاهلها
                        logger.info(f"   ✗ تجاهل entity متقاطعة: type={entity['type']}, offset={entity_offset}")

                # إضافة entities الجديدة المحفوظة مع تعديل offset
                if new_entities_data:
                    logger.info(f"   📝 إضافة {len(new_entities_data)} entities جديدة")
                    for new_ent in new_entities_data:
                        new_ent_copy = new_ent.copy()
                        # offset الجديد = offset الأصلي + موقع الاستبدال (pos_utf16)
                        original_offset = new_ent_copy['offset']
                        new_ent_copy['offset'] = pos_utf16 + original_offset
                        updated_entities.append(new_ent_copy)
                        logger.info(f"   ➕ إضافة entity: type={new_ent_copy['type']}, offset {original_offset} → {new_ent_copy['offset']}, length={new_ent_copy['length']}")

                # ترتيب entities حسب offset
                updated_entities.sort(key=lambda x: x['offset'])
                new_entities = updated_entities

            if replacements_made:
                logger.info(f"✅ تم تطبيق {len(replacements_made)} استبدال لـ '{old_word}'")
                logger.info(f"   📊 entities نهائية: {len(new_entities)}")

        return new_text, new_entities

    @staticmethod
    def check_forwarded_filter(is_forwarded: bool, filter_mode: str) -> bool:
        if filter_mode == 'allow':
            return True
        elif filter_mode == 'block':
            return not is_forwarded
        return True