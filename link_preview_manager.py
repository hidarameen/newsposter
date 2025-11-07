import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class LinkPreviewManager:
    """مدير معاينة الروابط في الرسائل"""
    
    @staticmethod
    def should_disable_preview(settings: Dict) -> bool:
        """
        التحقق من ما إذا كان يجب تعطيل معاينة الروابط
        
        Args:
            settings: إعدادات معاينة الروابط
            
        Returns:
            True إذا كان يجب تعطيل المعاينة
        """
        if not settings.get('enabled', False):
            return False
        
        mode = settings.get('mode', 'show')
        
        # show = إظهار المعاينة (لا نعطل)
        # hide = إخفاء المعاينة (نعطل)
        return mode == 'hide'
    
    @staticmethod
    def get_link_preview_option(settings: Dict) -> Optional[bool]:
        """
        الحصول على قيمة disable_web_page_preview للاستخدام في إرسال الرسائل
        
        Args:
            settings: إعدادات معاينة الروابط
            
        Returns:
            True لتعطيل المعاينة، False لتفعيلها، None للتجاهل
        """
        if not settings.get('enabled', False):
            return None
        
        mode = settings.get('mode', 'show')
        
        if mode == 'hide':
            logger.info("🔗 معاينة الروابط: مُعطلة")
            return True
        elif mode == 'show':
            logger.info("🔗 معاينة الروابط: مُفعلة")
            return False
        
        return None
    
    @staticmethod
    def get_mode_description(mode: str) -> str:
        """الحصول على وصف الوضع"""
        modes = {
            'show': '✅ إظهار معاينة الروابط',
            'hide': '❌ إخفاء معاينة الروابط'
        }
        return modes.get(mode, mode)
