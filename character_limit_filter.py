import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class CharacterLimitFilter:
    """فلتر حدود الأحرف للتحكم في طول الرسائل"""
    
    @staticmethod
    def check_character_limit(text: str, settings: Dict) -> Tuple[bool, str]:
        """
        التحقق من حدود الأحرف
        
        Args:
            text: النص المراد فحصه
            settings: إعدادات فلتر حدود الأحرف
            
        Returns:
            (مسموح, سبب الرفض)
        """
        if not settings.get('enabled', False):
            return True, ""
        
        if not text:
            return True, ""
        
        text_length = len(text)
        mode = settings.get('mode', 'max')
        
        # وضع الحد الأقصى: نشر الرسائل الأقل من الحد
        if mode == 'max':
            max_chars = settings.get('max_chars', 1000)
            
            if text_length > max_chars:
                return False, f"الرسالة تحتوي على {text_length} حرف (الحد الأقصى: {max_chars})"
            
            logger.info(f"✅ عدد الأحرف ({text_length}) أقل من الحد الأقصى ({max_chars})")
            return True, ""
        
        # وضع الحد الأدنى: نشر الرسائل الأكبر من الحد
        elif mode == 'min':
            min_chars = settings.get('min_chars', 10)
            
            if text_length < min_chars:
                return False, f"الرسالة تحتوي على {text_length} حرف (الحد الأدنى: {min_chars})"
            
            logger.info(f"✅ عدد الأحرف ({text_length}) أكبر من الحد الأدنى ({min_chars})")
            return True, ""
        
        # وضع النطاق: نشر الرسائل ضمن النطاق
        elif mode == 'range':
            min_chars = settings.get('min_chars', 10)
            max_chars = settings.get('max_chars', 1000)
            
            if text_length < min_chars:
                return False, f"الرسالة تحتوي على {text_length} حرف (الحد الأدنى: {min_chars})"
            
            if text_length > max_chars:
                return False, f"الرسالة تحتوي على {text_length} حرف (الحد الأقصى: {max_chars})"
            
            logger.info(
                f"✅ عدد الأحرف ({text_length}) ضمن النطاق "
                f"({min_chars} - {max_chars})"
            )
            return True, ""
        
        # وضع دقيق: نشر الرسائل بعدد محدد بالضبط
        elif mode == 'exact':
            exact_chars = settings.get('exact_chars', 100)
            tolerance = settings.get('tolerance', 0)  # هامش الخطأ
            
            if abs(text_length - exact_chars) > tolerance:
                return False, (
                    f"الرسالة تحتوي على {text_length} حرف "
                    f"(المطلوب: {exact_chars} ± {tolerance})"
                )
            
            logger.info(f"✅ عدد الأحرف ({text_length}) يطابق الحد المطلوب")
            return True, ""
        
        return True, ""
    
    @staticmethod
    def get_character_count(text: str) -> int:
        """الحصول على عدد الأحرف في النص"""
        return len(text) if text else 0
    
    @staticmethod
    def get_mode_description(mode: str, settings: Dict) -> str:
        """الحصول على وصف الوضع"""
        if mode == 'max':
            max_chars = settings.get('max_chars', 1000)
            return f"📏 حد أقصى: {max_chars} حرف"
        
        elif mode == 'min':
            min_chars = settings.get('min_chars', 10)
            return f"📏 حد أدنى: {min_chars} حرف"
        
        elif mode == 'range':
            min_chars = settings.get('min_chars', 10)
            max_chars = settings.get('max_chars', 1000)
            return f"📏 نطاق: {min_chars} - {max_chars} حرف"
        
        elif mode == 'exact':
            exact_chars = settings.get('exact_chars', 100)
            tolerance = settings.get('tolerance', 0)
            if tolerance > 0:
                return f"📏 دقيق: {exact_chars} ± {tolerance} حرف"
            return f"📏 دقيق: {exact_chars} حرف"
        
        return mode
    
    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        اقتطاع النص إلى طول معين
        
        Args:
            text: النص الأصلي
            max_length: الطول الأقصى
            suffix: اللاحقة (مثل "...")
            
        Returns:
            النص المقتطع
        """
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
