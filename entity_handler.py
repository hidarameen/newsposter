
from typing import List, Optional, Dict
from aiogram.types import MessageEntity

class EntityHandler:
    @staticmethod
    def utf16_offset_to_python(text: str, utf16_offset: int) -> int:
        """تحويل offset من UTF-16 (Telegram) إلى Python index"""
        python_index = 0
        utf16_pos = 0
        
        for char in text:
            if utf16_pos >= utf16_offset:
                break
            # Emoji والأحرف الخاصة تأخذ 2 units في UTF-16
            char_utf16_len = 2 if ord(char) > 0xFFFF else 1
            utf16_pos += char_utf16_len
            python_index += 1
        
        return python_index
    
    @staticmethod
    def python_offset_to_utf16(text: str, python_index: int) -> int:
        """تحويل Python index إلى UTF-16 offset (Telegram)"""
        utf16_offset = 0
        
        for i, char in enumerate(text):
            if i >= python_index:
                break
            # Emoji والأحرف الخاصة تأخذ 2 units في UTF-16
            char_utf16_len = 2 if ord(char) > 0xFFFF else 1
            utf16_offset += char_utf16_len
        
        return utf16_offset
    
    @staticmethod
    def preserve_entities(original_text: str, original_entities: Optional[List[MessageEntity]], 
                         new_text: str) -> List[Dict]:
        """الحفاظ على entities بعد تعديل النص
        
        يحافظ على UTF-16 offsets الصحيحة عند تغيير النص
        """
        if not original_entities or original_text == new_text:
            return EntityHandler.entities_to_dict(original_entities, original_text) if original_entities else []
        
        import logging
        logger = logging.getLogger(__name__)
        
        preserved_entities = []
        
        for entity in original_entities:
            # تحويل UTF-16 offset إلى Python index
            py_start = EntityHandler.utf16_offset_to_python(original_text, entity.offset)
            py_end = EntityHandler.utf16_offset_to_python(original_text, entity.offset + entity.length)
            
            # استخراج النص الأصلي للـ entity
            entity_text = original_text[py_start:py_end]
            
            # البحث عن النص في النص الجديد (Python index)
            new_py_position = new_text.find(entity_text)
            
            if new_py_position != -1:
                # تحويل Python index إلى UTF-16 offset
                new_utf16_offset = EntityHandler.python_offset_to_utf16(new_text, new_py_position)
                new_py_end = new_py_position + len(entity_text)
                new_utf16_end = EntityHandler.python_offset_to_utf16(new_text, new_py_end)
                new_utf16_length = new_utf16_end - new_utf16_offset
                
                logger.debug(f"Entity '{entity_text}': py_pos={new_py_position} -> utf16_offset={new_utf16_offset}, length={new_utf16_length}")
                
                preserved_entities.append({
                    'type': entity.type,
                    'offset': new_utf16_offset,
                    'length': new_utf16_length,
                    'url': entity.url if hasattr(entity, 'url') else None,
                    'user': entity.user.to_python() if hasattr(entity, 'user') and entity.user else None,
                    'language': entity.language if hasattr(entity, 'language') else None,
                    'custom_emoji_id': entity.custom_emoji_id if hasattr(entity, 'custom_emoji_id') else None
                })
        
        logger.info(f"✅ preserve_entities: {len(original_entities)} -> {len(preserved_entities)} entities محفوظة")
        return preserved_entities
    
    @staticmethod
    def entities_to_dict(entities: Optional[List[MessageEntity]], text: str = None) -> List[Dict]:
        """تحويل entities مع الحفاظ على الـ offsets الصحيحة
        
        ملاحظة: الـ offsets في MessageEntity تكون بصيغة UTF-16 (Telegram format)
        وهي صحيحة ويجب الحفاظ عليها كما هي
        """
        if not entities:
            return []
        
        import logging
        logger = logging.getLogger(__name__)
        
        result = []
        for entity in entities:
            entity_dict = {
                'type': entity.type,
                'offset': entity.offset,  # نحافظ على offset كما هو (UTF-16)
                'length': entity.length   # نحافظ على length كما هو
            }
            
            # حفظ url (مهم جداً للـ text_link)
            if hasattr(entity, 'url') and entity.url:
                entity_dict['url'] = entity.url
                logger.debug(f"💾 حفظ url للـ entity: {entity.type} - URL: {entity.url}")
            
            # حفظ user (للـ text_mention)
            if hasattr(entity, 'user') and entity.user:
                entity_dict['user'] = entity.user.to_python()
            
            # حفظ language (للـ pre/code)
            if hasattr(entity, 'language') and entity.language:
                entity_dict['language'] = entity.language
            
            # حفظ custom_emoji_id (للـ custom_emoji)
            if hasattr(entity, 'custom_emoji_id') and entity.custom_emoji_id:
                entity_dict['custom_emoji_id'] = entity.custom_emoji_id
            
            result.append(entity_dict)
        
        return result
    
    @staticmethod
    def dict_to_entities(entities_dict: List[Dict]) -> List[MessageEntity]:
        if not entities_dict:
            return []
        
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🔄 dict_to_entities - تحويل {len(entities_dict)} entities")
        
        result = []
        for e in entities_dict:
            try:
                # بناء kwargs للـ MessageEntity
                entity_kwargs = {
                    'type': e['type'],
                    'offset': e['offset'],
                    'length': e['length']
                }
                
                logger.info(f"   Entity: type={e['type']}, offset={e['offset']}, length={e['length']}")
                
                # إضافة url إذا كان موجوداً (مهم للـ text_link)
                if 'url' in e and e['url']:
                    entity_kwargs['url'] = e['url']
                    logger.info(f"      + url={e['url']}")
                
                # إضافة language إذا كان موجوداً (للـ code blocks)
                if 'language' in e and e['language']:
                    entity_kwargs['language'] = e['language']
                    logger.info(f"      + language={e['language']}")
                
                # إضافة user إذا كان موجوداً (للـ text_mention)
                if 'user' in e and e['user']:
                    entity_kwargs['user'] = e['user']
                    logger.info(f"      + user={e['user']}")
                
                # إضافة custom_emoji_id إذا كان موجوداً
                if 'custom_emoji_id' in e and e['custom_emoji_id']:
                    entity_kwargs['custom_emoji_id'] = e['custom_emoji_id']
                    logger.info(f"      + custom_emoji_id={e['custom_emoji_id']}")
                
                entity = MessageEntity(**entity_kwargs)
                result.append(entity)
                logger.info(f"   ✅ تم إنشاء Entity بنجاح")
            except Exception as ex:
                logger.error(f"⚠️ فشل تحويل entity: {e} - خطأ: {ex}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"✅ dict_to_entities - تم تحويل {len(result)} entities بنجاح")
        return result
    
    @staticmethod
    def shift_entities(entities: List[Dict], offset: int) -> List[Dict]:
        if not entities:
            return []
        
        shifted = []
        for entity in entities:
            new_entity = entity.copy()
            new_entity['offset'] += offset
            shifted.append(new_entity)
        
        return shifted
    
    @staticmethod
    def merge_entities(entities1: List[Dict], entities2: List[Dict]) -> List[Dict]:
        merged = []
        
        if entities1:
            merged.extend(entities1)
        if entities2:
            merged.extend(entities2)
        
        merged.sort(key=lambda x: x['offset'])
        
        return merged
    
    @staticmethod
    def entities_to_html(text: str, entities: List[Dict]) -> str:
        """تحويل النص مع entities إلى HTML formatted text
        
        يعالج UTF-16 offsets بشكل صحيح ويدعم entities المتداخلة
        
        Args:
            text: النص الأصلي
            entities: قائمة entities (بصيغة dict) بـ UTF-16 offsets
        
        Returns:
            النص بصيغة HTML مع التنسيقات
        """
        import html
        
        if not text:
            return ""
        
        if not entities:
            return html.escape(text)
        
        # تحويل UTF-16 offsets إلى Python indices
        entities_with_py_offsets = []
        for entity in entities:
            utf16_offset = entity['offset']
            utf16_length = entity['length']
            
            # تحويل offset و end إلى Python indices
            py_start = EntityHandler.utf16_offset_to_python(text, utf16_offset)
            py_end = EntityHandler.utf16_offset_to_python(text, utf16_offset + utf16_length)
            
            entities_with_py_offsets.append({
                'entity': entity,
                'py_start': py_start,
                'py_end': py_end
            })
        
        # ترتيب entities حسب البداية (start أولاً) ثم النهاية (الأطول أولاً)
        sorted_entities = sorted(entities_with_py_offsets, key=lambda x: (x['py_start'], -x['py_end']))
        
        # إنشاء قائمة من الأحداث (بداية ونهاية كل entity)
        events = []
        for i, ent_data in enumerate(sorted_entities):
            entity = ent_data['entity']
            py_start = ent_data['py_start']
            py_end = ent_data['py_end']
            
            # start event: (position, priority, type, index, entity)
            # priority: 0 for start (يفتح أولاً), 1 for end (يغلق لاحقاً)
            events.append((py_start, 0, 'start', i, entity))
            events.append((py_end, 1, 'end', i, entity))
        
        # ترتيب الأحداث حسب الموقع ثم الأولوية
        events.sort(key=lambda x: (x[0], x[1]))
        
        # بناء HTML
        parts = []
        current_pos = 0
        open_tags_stack = []  # stack للتتبع (entity_idx, entity)
        
        for pos, priority, event_type, entity_idx, entity in events:
            # إضافة النص قبل الحدث
            if pos > current_pos:
                text_part = text[current_pos:pos]
                parts.append(html.escape(text_part))
                current_pos = pos
            
            if event_type == 'start':
                # فتح tag جديد
                tag = EntityHandler._get_opening_tag(entity)
                if tag:  # بعض entities قد لا يكون لها tag
                    parts.append(tag)
                    open_tags_stack.append((entity_idx, entity))
            else:
                # إغلاق tag
                # نحتاج لإغلاق بالترتيب الصحيح (LIFO لـ nested tags)
                # لكن Telegram entities قد تتداخل بشكل معقد
                # سنغلق ببساطة
                tag = EntityHandler._get_closing_tag(entity)
                if tag:
                    parts.append(tag)
                    # إزالة من stack
                    if (entity_idx, entity) in open_tags_stack:
                        open_tags_stack.remove((entity_idx, entity))
        
        # إضافة ما تبقى من النص
        if current_pos < len(text):
            parts.append(html.escape(text[current_pos:]))
        
        return ''.join(parts)
    
    @staticmethod
    def _get_opening_tag(entity: Dict) -> str:
        """الحصول على opening HTML tag للـ entity
        
        يدعم جميع أنواع entities في Telegram
        """
        import html
        
        entity_type = entity['type']
        
        # تنسيقات النص الأساسية
        if entity_type == 'bold':
            return "<b>"
        elif entity_type == 'italic':
            return "<i>"
        elif entity_type == 'underline':
            return "<u>"
        elif entity_type == 'strikethrough':
            return "<s>"
        
        # كود والاقتباسات
        elif entity_type == 'code':
            return "<code>"
        elif entity_type == 'pre':
            language = entity.get('language', '')
            if language:
                return f"<pre><code class='language-{html.escape(language)}'>"
            return "<pre>"
        elif entity_type == 'blockquote':
            return "<blockquote>"
        
        # الروابط
        elif entity_type == 'text_link':
            url = entity.get('url', '')
            return f"<a href='{html.escape(url)}'>"
        elif entity_type == 'url':
            # url عادي، لا نحتاج لـ tag إضافي
            return ""
        
        # المنشنات والهاشتاغ
        elif entity_type in ['mention', 'hashtag', 'cashtag']:
            return "<b>"
        elif entity_type == 'text_mention':
            # mention مع user link
            return "<b>"
        
        # الأوامر والإيميل والأرقام
        elif entity_type == 'bot_command':
            return "<code>"
        elif entity_type == 'email':
            return ""
        elif entity_type == 'phone_number':
            return ""
        
        # Spoiler
        elif entity_type == 'spoiler':
            return "<span class='tg-spoiler'>"
        
        # Custom emoji (لا يدعمه HTML عادي، نستخدم span)
        elif entity_type == 'custom_emoji':
            emoji_id = entity.get('custom_emoji_id', '')
            return f"<span class='custom-emoji' data-emoji-id='{html.escape(emoji_id)}'>"
        
        # أنواع أخرى غير مدعومة
        else:
            return ""
    
    @staticmethod
    def _get_closing_tag(entity: Dict) -> str:
        """الحصول على closing HTML tag للـ entity"""
        entity_type = entity['type']
        
        # تنسيقات النص الأساسية
        if entity_type == 'bold':
            return "</b>"
        elif entity_type == 'italic':
            return "</i>"
        elif entity_type == 'underline':
            return "</u>"
        elif entity_type == 'strikethrough':
            return "</s>"
        
        # كود والاقتباسات
        elif entity_type == 'code':
            return "</code>"
        elif entity_type == 'pre':
            language = entity.get('language', '')
            if language:
                return "</code></pre>"
            return "</pre>"
        elif entity_type == 'blockquote':
            return "</blockquote>"
        
        # الروابط
        elif entity_type == 'text_link':
            return "</a>"
        elif entity_type == 'url':
            return ""
        
        # المنشنات والهاشتاغ
        elif entity_type in ['mention', 'hashtag', 'cashtag', 'text_mention']:
            return "</b>"
        
        # الأوامر والإيميل والأرقام
        elif entity_type == 'bot_command':
            return "</code>"
        elif entity_type in ['email', 'phone_number']:
            return ""
        
        # Spoiler
        elif entity_type == 'spoiler':
            return "</span>"
        
        # Custom emoji
        elif entity_type == 'custom_emoji':
            return "</span>"
        
        # أنواع أخرى
        else:
            return ""
