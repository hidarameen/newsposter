
from typing import Tuple
import re

class LanguageFilters:
    
    LANGUAGE_PATTERNS = {
        'ar': r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]',
        'en': r'[a-zA-Z]',
        'ru': r'[а-яА-ЯёЁ]',
        'fa': r'[\u0600-\u06FF]',
        'ur': r'[\u0600-\u06FF]',
        'tr': r'[a-zA-ZçÇğĞıİöÖşŞüÜ]',
        'de': r'[a-zA-ZäöüßÄÖÜ]',
        'fr': r'[a-zA-ZàâäæçéèêëïîôùûüÿœÀÂÄÆÇÉÈÊËÏÎÔÙÛÜŸŒ]',
        'es': r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]',
        'it': r'[a-zA-ZàèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ]',
        'pt': r'[a-zA-ZáâãàçéêíóôõúüÁÂÃÀÇÉÊÍÓÔÕÚÜ]'
    }
    
    @staticmethod
    def detect_language_ratio(text: str, language: str) -> float:
        """
        كشف نسبة وجود لغة معينة في النص
        
        Args:
            text: النص المراد فحصه
            language: كود اللغة
            
        Returns:
            نسبة وجود اللغة (0.0 - 1.0)
        """
        if language not in LanguageFilters.LANGUAGE_PATTERNS:
            return 0.0
        
        pattern = LanguageFilters.LANGUAGE_PATTERNS[language]
        
        # إزالة علامات الترقيم والمسافات للحصول على الأحرف فقط
        text_clean = re.sub(r'[^\w\s]', '', text)
        text_clean = re.sub(r'\s+', '', text_clean)
        
        if not text_clean:
            return 0.0
        
        # البحث عن أحرف اللغة في النص المنظف
        language_chars = len(re.findall(pattern, text_clean))
        total_chars = len(text_clean)
        
        if total_chars == 0:
            return 0.0
        
        ratio = language_chars / total_chars
        return ratio
    
    @staticmethod
    def apply_language_filter(text: str, mode: str, languages: list, sensitivity: str) -> Tuple[bool, str]:
        """
        تطبيق فلتر اللغة
        
        Args:
            text: النص المراد فحصه
            mode: وضع الفلتر ('allow' أو 'block')
            languages: قائمة اللغات
            sensitivity: حساسية الفلتر ('partial' أو 'full')
                - partial: يكتشف وجود جزء من النص باللغة (20%+)
                - full: يتطلب أن يكون النص كاملاً باللغة (85%+)
        
        Returns:
            (مسموح, سبب الرفض)
        """
        if not languages:
            return True, text
        
        # تحديد العتبة حسب الحساسية
        # partial: 20% يكفي لاكتشاف وجود اللغة
        # full: 85% للتأكد أن النص كامل تقريباً
        threshold = 0.85 if sensitivity == 'full' else 0.20
        
        language_detected = False
        detected_lang = None
        max_ratio = 0.0
        
        # فحص جميع اللغات المحددة
        for lang in languages:
            ratio = LanguageFilters.detect_language_ratio(text, lang)
            
            # تتبع أعلى نسبة
            if ratio > max_ratio:
                max_ratio = ratio
                detected_lang = lang
            
            # إذا وصلت النسبة للعتبة، تم اكتشاف اللغة
            if ratio >= threshold:
                language_detected = True
                detected_lang = lang
                break
        
        # وضع السماح: يجب أن تكتشف اللغة
        if mode == 'allow':
            if language_detected:
                return True, text
            else:
                sensitivity_desc = "كاملاً" if sensitivity == 'full' else "جزئياً"
                langs_str = ', '.join(languages)
                return False, f"النص ليس {sensitivity_desc} باللغة المحددة ({langs_str}) - نسبة الكشف: {max_ratio*100:.1f}%"
        
        # وضع الحظر: يجب ألا تكتشف اللغة
        elif mode == 'block':
            if language_detected:
                sensitivity_desc = "كاملاً" if sensitivity == 'full' else "جزئياً"
                return False, f"النص {sensitivity_desc} باللغة المحظورة: {detected_lang} (نسبة: {max_ratio*100:.1f}%)"
            else:
                return True, text
        
        return True, text
