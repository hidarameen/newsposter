import json
import os
from typing import Dict, List, Optional, Any
from config import USERS_DATA_DIR
import logging

logger = logging.getLogger(__name__)

class TaskSettingsManager:
    def __init__(self, user_id: int, task_id: int, force_new: bool = False):
        self.user_id = user_id
        self.task_id = task_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.settings_file = os.path.join(self.user_dir, f'task_{task_id}_settings.json')
        
        # إذا كان force_new=True، حذف الملف القديم إن وجد
        if force_new and os.path.exists(self.settings_file):
            logger.info(f"🗑️ حذف ملف إعدادات قديم للمهمة {task_id} للمستخدم {user_id}")
            os.remove(self.settings_file)
        
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.settings_file):
            default_settings = {
                'media_filters': {
                    'enabled': False,
                    'allowed_types': ['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note', 'animation', 'sticker']
                },
                'header': {
                    'enabled': False,
                    'text': '',
                    'entities': []
                },
                'footer': {
                    'enabled': False,
                    'text': '',
                    'entities': []
                },
                'inline_buttons': {
                    'enabled': False,
                    'buttons': []
                },
                'whitelist_words': {
                    'enabled': False,
                    'words': []
                },
                'blacklist_words': {
                    'enabled': False,
                    'words': []
                },
                'replacements': {
                    'enabled': False,
                    'pairs': []
                },
                'link_management': {
                    'enabled': False,
                    'mode': 'block'
                },
                'button_filter': {
                    'enabled': False,
                    'mode': 'block'
                },
                'forwarded_filter': {
                    'enabled': False,
                    'mode': 'allow'
                },
                'language_filter': {
                    'enabled': False,
                    'mode': 'allow',
                    'languages': [],
                    'sensitivity': 'medium'
                },
                'text_format': {
                    'enabled': False,
                    'format_type': 'normal'
                },
                'auto_pin': {
                    'enabled': False,
                    'disable_notification': True,
                    'delete_notification_after': 5
                },
                'link_preview': {
                    'enabled': False,
                    'mode': 'show'
                },
                'reply_preservation': {
                    'enabled': False
                },
                'auto_delete': {
                    'enabled': False,
                    'delay_value': 60,
                    'delay_unit': 'minutes'
                },
                'day_filter': {
                    'enabled': False,
                    'mode': 'allow',
                    'days': []
                },
                'hour_filter': {
                    'enabled': False,
                    'mode': 'allow',
                    'hours': [],
                    'start_hour': 0,
                    'end_hour': 23
                },
                'translation': {
                    'enabled': False,
                    'mode': 'all_to_target',
                    'source_lang': 'auto',
                    'target_lang': 'ar'
                },
                'character_limit': {
                    'enabled': False,
                    'mode': 'max',
                    'min_chars': 10,
                    'max_chars': 4000,
                    'exact_chars': 100,
                    'tolerance': 0
                }
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)

    def load_settings(self) -> Dict:
        with open(self.settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_settings(self, settings: Dict):
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def update_setting(self, category: str, key: str, value: Any):
        settings = self.load_settings()
        if category in settings:
            settings[category][key] = value
            self.save_settings(settings)

    def get_setting(self, category: str, key: Optional[str] = None):
        settings = self.load_settings()
        if key is None:
            return settings.get(category, {})
        return settings.get(category, {}).get(key)

    def toggle_feature(self, feature_name: str) -> bool:
        """تبديل حالة ميزة معينة"""
        settings = self.load_settings()

        # التأكد من وجود الميزة في الإعدادات
        if feature_name not in settings:
            settings[feature_name] = {'enabled': False}

        # التأكد من وجود enabled في الميزة
        if 'enabled' not in settings[feature_name]:
            settings[feature_name]['enabled'] = False

        # قراءة الحالة الحالية
        current_state = settings[feature_name]['enabled']

        # عكس الحالة
        new_state = not current_state

        # حفظ الحالة الجديدة
        settings[feature_name]['enabled'] = new_state

        # حفظ الإعدادات
        self.save_settings(settings)

        # التحقق من الحفظ
        saved_settings = self.load_settings()
        actual_state = saved_settings.get(feature_name, {}).get('enabled', False)

        logger.info(f"🔄 Toggle {feature_name}: {current_state} → {new_state} (saved: {actual_state})")

        return new_state

    def add_whitelist_word(self, word: str):
        settings = self.load_settings()
        if word not in settings['whitelist_words']['words']:
            settings['whitelist_words']['words'].append(word)
            self.save_settings(settings)

    def add_blacklist_word(self, word: str):
        settings = self.load_settings()
        if word not in settings['blacklist_words']['words']:
            settings['blacklist_words']['words'].append(word)
            self.save_settings(settings)

    def add_replacement(self, old_word: str, new_word: str, old_entities: Optional[list] = None, new_entities: Optional[list] = None):
        settings = self.load_settings()

        # التأكد من أن entities ليست None
        old_entities_list = old_entities if old_entities is not None else []
        new_entities_list = new_entities if new_entities is not None else []

        replacement = {
            'old': old_word,
            'new': new_word,
            'old_entities': old_entities_list,
            'new_entities': new_entities_list
        }

        logger.info(f"💾 TaskSettingsManager.add_replacement:")
        logger.info(f"   old_word: '{old_word}'")
        logger.info(f"   new_word: '{new_word}'")
        logger.info(f"   old_entities قبل الحفظ: {len(old_entities_list)} items")
        logger.info(f"   new_entities قبل الحفظ: {len(new_entities_list)} items")

        if old_entities_list:
            logger.info(f"   محتوى old_entities:")
            for i, e in enumerate(old_entities_list):
                logger.info(f"      [{i}] {e}")

        if new_entities_list:
            logger.info(f"   محتوى new_entities:")
            for i, e in enumerate(new_entities_list):
                logger.info(f"      [{i}] {e}")

        settings['replacements']['pairs'].append(replacement)
        self.save_settings(settings)

        # التحقق من الحفظ
        reloaded_settings = self.load_settings()
        saved_pairs = reloaded_settings['replacements']['pairs']
        if saved_pairs:
            last_pair = saved_pairs[-1]
            logger.info(f"✅ تم التحقق من الحفظ - آخر استبدال محفوظ:")
            logger.info(f"   old_entities بعد التحميل: {len(last_pair.get('old_entities', []))} items")
            logger.info(f"   new_entities بعد التحميل: {len(last_pair.get('new_entities', []))} items")

            if last_pair.get('old_entities'):
                logger.info(f"   محتوى old_entities المحفوظة:")
                for i, e in enumerate(last_pair['old_entities']):
                    logger.info(f"      [{i}] {e}")
            else:
                logger.warning(f"   ⚠️ old_entities فارغة بعد الحفظ!")

            if last_pair.get('new_entities'):
                logger.info(f"   محتوى new_entities المحفوظة:")
                for i, e in enumerate(last_pair['new_entities']):
                    logger.info(f"      [{i}] {e}")
            else:
                logger.warning(f"   ⚠️ new_entities فارغة بعد الحفظ!")

    def clear_replacements(self):
        settings = self.load_settings()
        settings['replacements']['pairs'] = []
        self.save_settings(settings)

    def set_header(self, text: str, entities: Optional[List] = None):
        settings = self.load_settings()
        settings['header']['text'] = text
        settings['header']['entities'] = entities or []
        self.save_settings(settings)

    def set_footer(self, text: str, entities: Optional[List] = None):
        settings = self.load_settings()
        settings['footer']['text'] = text
        settings['footer']['entities'] = entities or []
        self.save_settings(settings)

    def set_inline_buttons(self, buttons: List[List[Dict]]):
        settings = self.load_settings()
        settings['inline_buttons']['buttons'] = buttons
        self.save_settings(settings)

    def set_media_filters(self, allowed_types: List[str]):
        settings = self.load_settings()
        settings['media_filters']['allowed_types'] = allowed_types
        self.save_settings(settings)