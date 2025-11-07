import json
import os
from pathlib import Path
from typing import Optional
import logging
from config import ADMIN_SETTINGS_FILE

logger = logging.getLogger(__name__)

class AdminSettingsManager:
    """إدارة إعدادات المشرف للبوت"""
    
    def __init__(self):
        self.config_file = Path(ADMIN_SETTINGS_FILE)
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """تحميل الإعدادات من الملف"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطأ في تحميل إعدادات المشرف: {e}")
        
        return {
            "min_subscribers": 0,  # الحد الأدنى لعدد المشتركين (0 = بدون حد)
            "enforce_min_subscribers": True  # تفعيل فرض الحد الأدنى
        }
    
    def _save_config(self):
        """حفظ الإعدادات إلى الملف"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ إعدادات المشرف: {e}")
    
    def get_min_subscribers(self) -> int:
        """الحصول على الحد الأدنى لعدد المشتركين"""
        return self.config.get("min_subscribers", 0)
    
    def set_min_subscribers(self, min_count: int):
        """
        تعيين الحد الأدنى لعدد المشتركين
        
        Args:
            min_count: الحد الأدنى (0 = بدون حد)
        """
        self.config["min_subscribers"] = max(0, min_count)
        self._save_config()
        logger.info(f"تم تعيين الحد الأدنى لعدد المشتركين: {min_count}")
    
    def is_enforcement_enabled(self) -> bool:
        """التحقق من تفعيل فرض الحد الأدنى"""
        return self.config.get("enforce_min_subscribers", True)
    
    def set_enforcement(self, enabled: bool):
        """
        تفعيل أو تعطيل فرض الحد الأدنى
        
        Args:
            enabled: True للتفعيل, False للتعطيل
        """
        self.config["enforce_min_subscribers"] = enabled
        self._save_config()
        logger.info(f"تم {'تفعيل' if enabled else 'تعطيل'} فرض الحد الأدنى لعدد المشتركين")
    
    def get_all_settings(self) -> dict:
        """الحصول على جميع الإعدادات"""
        return self.config.copy()

# إنشاء نسخة عامة من المدير
admin_settings = AdminSettingsManager()
