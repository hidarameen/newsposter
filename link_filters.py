import re
from typing import Tuple, List, Dict, Optional

class LinkFilters:
    @staticmethod
    def find_all_links(text: str) -> List[str]:
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'

        username_pattern = r'@[a-zA-Z0-9_]{5,32}'

        tme_pattern = r't\.me/[a-zA-Z0-9_]+'
        
        # pattern للروابط بدون http/https
        domain_pattern = r'(?<![/@])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?'

        urls = re.findall(url_pattern, text)
        usernames = re.findall(username_pattern, text)
        tme_links = re.findall(tme_pattern, text)
        domain_links = re.findall(domain_pattern, text)

        all_links = urls + usernames + tme_links + domain_links

        return list(set(all_links))

    @staticmethod
    def remove_links(text: str, entities: Optional[List[Dict]] = None) -> Tuple[str, List[Dict]]:
        from entity_handler import EntityHandler

        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'

        username_pattern = r'@[a-zA-Z0-9_]{5,32}'

        tme_pattern = r't\.me/[a-zA-Z0-9_]+'
        
        # pattern للروابط بدون http/https
        domain_pattern = r'(?<![/@])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?'

        new_text = text
        new_text = re.sub(url_pattern, '', new_text)
        new_text = re.sub(username_pattern, '', new_text)
        new_text = re.sub(tme_pattern, '', new_text)
        new_text = re.sub(domain_pattern, '', new_text)

        new_text = re.sub(r'\s+', ' ', new_text).strip()

        new_entities = EntityHandler.preserve_entities(text,
            EntityHandler.dict_to_entities(entities) if entities else None,
            new_text)

        return new_text, new_entities

    @staticmethod
    def apply_link_filter(text: str, mode: str, entities: List[Dict]) -> Tuple[bool, str, List[Dict]]:
        """تطبيق فلتر الروابط مع الحفاظ على بنية الأسطر"""
        from entity_handler import EntityHandler
        
        if not text:
            return True, text, entities

        # التحقق من وجود روابط
        url_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r't\.me/[a-zA-Z0-9_]+',
            r'@[a-zA-Z0-9_]+',
            # إضافة pattern لروابط بدون http/https (مثل domain.com/path)
            r'(?<![/@])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?'
        ]

        has_link = any(re.search(pattern, text, re.IGNORECASE) for pattern in url_patterns)

        # التحقق من وجود entities من نوع url, text_link, mention
        has_link_entity = any(
            e.get('type') in ['url', 'text_link', 'mention', 'text_mention']
            for e in entities
        ) if entities else False

        has_link = has_link or has_link_entity

        if not has_link:
            return True, text, entities

        if mode == 'block':
            return False, "الرسالة تحتوي على روابط", []

        elif mode == 'remove':
            # معالجة النص سطر بسطر - حذف الأسطر التي تحتوي على روابط
            lines = text.split('\n')
            new_lines = []

            for line in lines:
                # التحقق من وجود رابط في السطر
                line_has_link = any(re.search(pattern, line, re.IGNORECASE) for pattern in url_patterns)
                
                if line_has_link:
                    # حذف السطر بالكامل إذا كان يحتوي على رابط
                    continue
                else:
                    # الحفاظ على السطر كما هو
                    new_lines.append(line)

            new_text = '\n'.join(new_lines)

            # إزالة entities المرتبطة بالروابط
            if entities:
                new_entities = [
                    e for e in entities
                    if e.get('type') not in ['url', 'text_link', 'mention', 'text_mention']
                ]

                # إعادة حساب offsets
                new_entities = EntityHandler.preserve_entities(
                    text,
                    EntityHandler.dict_to_entities(entities) if entities else None,
                    new_text
                )
            else:
                new_entities = []

            # تنظيف الأسطر الفارغة المتتالية فقط (3 أو أكثر -> 2)
            new_text = re.sub(r'\n{3,}', '\n\n', new_text)
            new_text = new_text.strip()

            return True, new_text, new_entities

        return True, text, entities