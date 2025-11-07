import json
import logging
from pathlib import Path
from typing import Optional
from config import WELCOME_MESSAGE_FILE

logger = logging.getLogger(__name__)

class WelcomeMessageManager:
    """مدير رسائل الترحيب المخصصة"""
    
    def __init__(self):
        self.config_file = Path(WELCOME_MESSAGE_FILE)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not self.config_file.exists():
            default_config = {
                "enabled": False,
                "message": "",
                "use_custom": False
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    def get_welcome_message(self) -> Optional[str]:
        """الحصول على رسالة الترحيب المخصصة إذا كانت مفعلة"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if config.get('enabled', False) and config.get('use_custom', False):
                return config.get('message', '')
            
            return None
        except Exception as e:
            logger.error(f"خطأ في قراءة رسالة الترحيب: {e}")
            return None
    
    def set_welcome_message(self, message: str):
        """تعيين رسالة الترحيب المخصصة"""
        try:
            config = {
                "enabled": True,
                "message": message,
                "use_custom": True
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("تم تحديث رسالة الترحيب المخصصة")
        except Exception as e:
            logger.error(f"خطأ في حفظ رسالة الترحيب: {e}")
            raise
    
    def disable_custom_message(self):
        """تعطيل الرسالة المخصصة والعودة للرسالة الافتراضية"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config['enabled'] = False
            config['use_custom'] = False
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("تم تعطيل رسالة الترحيب المخصصة")
        except Exception as e:
            logger.error(f"خطأ في تعطيل رسالة الترحيب: {e}")
            raise
    
    def get_config(self) -> dict:
        """الحصول على إعدادات رسالة الترحيب"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في قراءة إعدادات الترحيب: {e}")
            return {"enabled": False, "message": "", "use_custom": False}

welcome_message_manager = WelcomeMessageManager()
