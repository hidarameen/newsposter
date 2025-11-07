import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TextFormatter:
    """
    وظيفة تنسيق النصوص الموحد
    تحويل جميع تنسيقات النص إلى تنسيق واحد محدد
    """
    
    # أنواع التنسيقات المدعومة
    SUPPORTED_FORMATS = [
        'normal',        # عادي (إزالة جميع التنسيقات)
        'bold',          # عريض
        'italic',        # مائل
        'underline',     # تحته خط
        'strikethrough', # مشطوب
        'spoiler',       # مخفي
        'code',          # كود (أحادي المسافة)
        'blockquote',    # اقتباس
        'pre',           # كود متعدد الأسطر
        'text_link'      # رابط نصي
    ]
    
    # أنواع الـ entities القابلة للتحويل
    FORMATTABLE_TYPES = [
        'bold',
        'italic',
        'underline',
        'strikethrough',
        'spoiler',
        'code',
        'blockquote',
        'pre'
    ]
    
    # أنواع الـ entities التي لا يجب تحويلها
    PROTECTED_TYPES = [
        'url',            # روابط عادية
        'mention',        # منشن
        'hashtag',        # هاشتاج
        'cashtag',        # كاشتاج
        'bot_command',    # أوامر البوت
        'email',          # إيميل
        'phone_number',   # رقم هاتف
        'text_mention',   # منشن نصي
        'custom_emoji'    # إيموجي مخصص
    ]
    
    @staticmethod
    def apply_format(text: str, entities: List[Dict], format_type: str, text_link_url: str = '') -> tuple[str, List[Dict]]:
        """
        تطبيق تنسيق موحد على النص والـ entities
        
        Args:
            text: النص
            entities: قائمة الـ entities (dict format)
            format_type: نوع التنسيق المطلوب (normal, bold, italic, etc.)
            text_link_url: الرابط المستخدم في حالة text_link
        
        Returns:
            tuple: (النص, الـ entities المحدثة)
        """
        if not format_type or format_type not in TextFormatter.SUPPORTED_FORMATS:
            logger.warning(f"⚠️ نوع تنسيق غير مدعوم: {format_type}")
            return text, entities
        
        if not text:
            logger.info(f"ℹ️ لا يوجد نص للتنسيق")
            return text, entities
        
        logger.info(f"🎨 [TextFormatter] تطبيق تنسيق '{format_type}' على النص بالكامل")
        
        # إذا كان التنسيق "عادي"، نزيل جميع التنسيقات
        if format_type == 'normal':
            return TextFormatter._remove_all_formatting(text, entities)
        
        # تطبيق التنسيق على النص بالكامل
        return TextFormatter._apply_full_text_format(text, entities, format_type, text_link_url)
    
    @staticmethod
    def _remove_all_formatting(text: str, entities: List[Dict]) -> tuple[str, List[Dict]]:
        """
        إزالة جميع التنسيقات من النص
        الحفاظ فقط على الـ entities المحمية (روابط، منشنات، إلخ)
        """
        logger.info(f"🧹 [TextFormatter] إزالة جميع التنسيقات")
        
        protected_entities = []
        removed_count = 0
        
        for entity in entities:
            entity_type = entity.get('type')
            
            # الحفاظ على الـ entities المحمية
            if entity_type in TextFormatter.PROTECTED_TYPES:
                protected_entities.append(entity)
                logger.debug(f"   ✅ حماية entity: {entity_type}")
            else:
                removed_count += 1
                logger.debug(f"   ❌ إزالة entity: {entity_type}")
        
        logger.info(f"   📊 النتيجة: أزيلت {removed_count} entities، حُفظت {len(protected_entities)} entities")
        
        return text, protected_entities
    
    @staticmethod
    def _apply_full_text_format(text: str, entities: List[Dict], target_format: str, text_link_url: str = '') -> tuple[str, List[Dict]]:
        """
        تطبيق تنسيق موحد على النص بالكامل
        يحول جميع الـ entities القابلة للتنسيق ويضيف تنسيق للأجزاء غير المنسقة
        """
        logger.info(f"🎨 [TextFormatter] تطبيق تنسيق '{target_format}' على النص بالكامل")
        
        # حساب طول النص بصيغة UTF-16
        text_length_utf16 = 0
        for char in text:
            if ord(char) > 0xFFFF:
                text_length_utf16 += 2
            else:
                text_length_utf16 += 1
        
        new_entities = []
        protected_count = 0
        converted_count = 0
        
        # الخطوة 1: معالجة الـ entities الموجودة (تحويل + حماية)
        if entities:
            for entity in entities:
                entity_type = entity.get('type')
                
                if entity_type in TextFormatter.PROTECTED_TYPES:
                    new_entities.append(entity)
                    protected_count += 1
                    logger.debug(f"   ✅ حماية: {entity_type} at {entity.get('offset')}")
                
                elif entity_type in TextFormatter.FORMATTABLE_TYPES:
                    new_entity = entity.copy()
                    new_entity['type'] = target_format
                    if target_format == 'text_link' and text_link_url:
                        new_entity['url'] = text_link_url
                    new_entities.append(new_entity)
                    converted_count += 1
                    logger.debug(f"   🔄 تحويل: {entity_type} → {target_format} at {entity.get('offset')}")
                
                else:
                    new_entities.append(entity)
        
        # الخطوة 2: إيجاد الفجوات (الأجزاء بدون entities) وإضافة تنسيق لها
        if new_entities:
            # ترتيب entities حسب الموقع
            sorted_entities = sorted(new_entities, key=lambda e: e.get('offset', 0))
            
            # بناء قائمة المناطق المغطاة
            covered_ranges = []
            for entity in sorted_entities:
                offset = entity.get('offset', 0)
                length = entity.get('length', 0)
                covered_ranges.append((offset, offset + length))
            
            # دمج المناطق المتداخلة
            covered_ranges.sort()
            merged_ranges = []
            for start, end in covered_ranges:
                if merged_ranges and start <= merged_ranges[-1][1]:
                    merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], end))
                else:
                    merged_ranges.append((start, end))
            
            # إضافة تنسيق للفجوات
            gap_count = 0
            current_pos = 0
            for start, end in merged_ranges:
                if current_pos < start:
                    # فجوة قبل entity الحالي
                    new_entities.append({
                        'type': target_format,
                        'offset': current_pos,
                        'length': start - current_pos
                    })
                    gap_count += 1
                    logger.debug(f"   ➕ فجوة: {current_pos}:{start}")
                current_pos = max(current_pos, end)
            
            # فجوة في النهاية
            if current_pos < text_length_utf16:
                gap_entity = {
                    'type': target_format,
                    'offset': current_pos,
                    'length': text_length_utf16 - current_pos
                }
                if target_format == 'text_link' and text_link_url:
                    gap_entity['url'] = text_link_url
                new_entities.append(gap_entity)
                gap_count += 1
                logger.debug(f"   ➕ فجوة نهائية: {current_pos}:{text_length_utf16}")
            
            logger.info(f"   📊 النتيجة: حُوّل {converted_count}، حُفظ {protected_count}، فجوات {gap_count}، المجموع {len(new_entities)}")
        
        else:
            # لا توجد entities، أضف تنسيق للنص بالكامل
            full_entity = {
                'type': target_format,
                'offset': 0,
                'length': text_length_utf16
            }
            if target_format == 'text_link' and text_link_url:
                full_entity['url'] = text_link_url
            new_entities.append(full_entity)
            logger.info(f"   ✅ تنسيق كامل: 0:{text_length_utf16}")
        
        return text, new_entities
    
    @staticmethod
    def _convert_to_format(text: str, entities: List[Dict], target_format: str) -> tuple[str, List[Dict]]:
        """
        تحويل جميع التنسيقات القابلة للتحويل إلى التنسيق المطلوب
        """
        logger.info(f"🔄 [TextFormatter] تحويل التنسيقات إلى '{target_format}'")
        
        converted_entities = []
        converted_count = 0
        protected_count = 0
        
        for entity in entities:
            entity_type = entity.get('type')
            
            # الحفاظ على الـ entities المحمية كما هي
            if entity_type in TextFormatter.PROTECTED_TYPES:
                converted_entities.append(entity)
                protected_count += 1
                logger.debug(f"   ✅ حماية entity: {entity_type} at {entity.get('offset')}")
            
            # تحويل الـ entities القابلة للتحويل
            elif entity_type in TextFormatter.FORMATTABLE_TYPES:
                new_entity = entity.copy()
                new_entity['type'] = target_format
                converted_entities.append(new_entity)
                converted_count += 1
                logger.debug(f"   🔄 تحويل: {entity_type} → {target_format} at {entity.get('offset')}")
            
            # الـ entities الأخرى نتركها كما هي
            else:
                converted_entities.append(entity)
                logger.debug(f"   ➡️ ترك entity: {entity_type}")
        
        logger.info(f"   📊 النتيجة: حُوّل {converted_count} entities، حُفظت {protected_count} entities، المجموع {len(converted_entities)} entities")
        
        return text, converted_entities
    
    @staticmethod
    def get_format_display_name(format_type: str) -> str:
        """الحصول على الاسم العربي لنوع التنسيق"""
        format_names = {
            'normal': '⬜ عادي (بدون تنسيق)',
            'bold': '🔵 عريض',
            'italic': '🔷 مائل',
            'underline': '🔸 تحته خط',
            'strikethrough': '➖ مشطوب',
            'spoiler': '🔲 مخفي (Spoiler)',
            'code': '💻 كود (أحادي المسافة)',
            'blockquote': '💬 اقتباس',
            'pre': '📄 كود متعدد الأسطر',
            'text_link': '🔗 رابط نصي'
        }
        return format_names.get(format_type, format_type)
    
    @staticmethod
    def validate_format_settings(settings: Dict) -> bool:
        """التحقق من صحة إعدادات التنسيق"""
        if not isinstance(settings, dict):
            return False
        
        if 'enabled' not in settings or 'format_type' not in settings:
            return False
        
        format_type = settings.get('format_type')
        if format_type and format_type not in TextFormatter.SUPPORTED_FORMATS:
            return False
        
        return True
