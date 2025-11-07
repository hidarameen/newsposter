import logging
from typing import Dict, List, Tuple, Optional
from deep_translator import GoogleTranslator, single_detection
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES

logger = logging.getLogger(__name__)

class TranslationHandler:
    """معالج ترجمة النصوص"""
    
    # اللغات الشائعة
    COMMON_LANGUAGES = {
        'ar': '🇸🇦 العربية',
        'en': '🇬🇧 الإنجليزية',
        'fr': '🇫🇷 الفرنسية',
        'es': '🇪🇸 الإسبانية',
        'de': '🇩🇪 الألمانية',
        'it': '🇮🇹 الإيطالية',
        'ru': '🇷🇺 الروسية',
        'tr': '🇹🇷 التركية',
        'fa': '🇮🇷 الفارسية',
        'ur': '🇵🇰 الأردية',
        'hi': '🇮🇳 الهندية',
        'zh-CN': '🇨🇳 الصينية المبسطة',
        'ja': '🇯🇵 اليابانية',
        'ko': '🇰🇷 الكورية',
    }
    
    async def translate_text(
        self,
        text: str,
        source_lang: str = 'auto',
        target_lang: str = 'en',
        split_by_sentence: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        ترجمة نص
        
        Args:
            text: النص المراد ترجمته
            source_lang: اللغة المصدر ('auto' للكشف التلقائي)
            target_lang: اللغة الهدف
            split_by_sentence: تقسيم النص إلى جمل وترجمة كل جملة على حدة (للنصوص المختلطة)
            
        Returns:
            (نجاح, النص المترجم, اللغة المكتشفة)
        """
        if not text or not text.strip():
            return False, None, None
        
        try:
            # تحويل zh-cn إلى zh-CN للتوافق مع deep-translator
            if target_lang.lower() == 'zh-cn':
                target_lang = 'zh-CN'
            if source_lang.lower() == 'zh-cn':
                source_lang = 'zh-CN'
            
            # كشف اللغة المصدر إذا كان source_lang='auto'
            detected_lang = source_lang
            if source_lang == 'auto':
                try:
                    from langdetect import detect
                    import asyncio
                    loop = asyncio.get_event_loop()
                    detected_lang = await loop.run_in_executor(
                        None,
                        detect,
                        text
                    )
                    logger.info(f"🔍 تم كشف اللغة: {detected_lang}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل كشف اللغة، سيتم استخدام 'auto': {e}")
                    detected_lang = 'auto'
            
            # إذا طُلب تقسيم النص، نقسمه ونترجم كل جزء على حدة
            if split_by_sentence:
                import re
                # تقسيم النص على الجمل والمسافات الكبيرة
                sentences = re.split(r'([.!?،؛\n]+)', text)
                translated_parts = []
                
                import asyncio
                loop = asyncio.get_event_loop()
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                
                for part in sentences:
                    if part.strip():
                        try:
                            translated_part = await loop.run_in_executor(
                                None,
                                translator.translate,
                                part
                            )
                            translated_parts.append(translated_part)
                        except:
                            translated_parts.append(part)  # في حالة الفشل، نستخدم الأصلي
                    else:
                        translated_parts.append(part)
                
                translated_text = ''.join(translated_parts)
            else:
                # الترجمة العادية - تشغيل في executor لأن deep-translator ليس async
                import asyncio
                loop = asyncio.get_event_loop()
                
                # استخدام GoogleTranslator من deep-translator
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                
                result = await loop.run_in_executor(
                    None,
                    translator.translate,
                    text
                )
                
                translated_text = result
            
            logger.info(
                f"✅ تمت الترجمة من {detected_lang} إلى {target_lang}: "
                f"'{text[:50]}...' → '{translated_text[:50]}...'"
            )
            
            return True, translated_text, detected_lang
            
        except Exception as e:
            logger.error(f"❌ خطأ في الترجمة: {e}")
            return False, None, None
    
    async def translate_with_entities(
        self,
        text: str,
        entities: List[Dict],
        source_lang: str = 'auto',
        target_lang: str = 'en'
    ) -> Tuple[bool, Optional[str], List[Dict], Optional[str]]:
        """
        ترجمة نص مع محاولة الحفاظ على entities (التنسيقات)
        
        ملاحظة: سيتم الحفاظ فقط على entities من نوع معين (links, mentions)
        التنسيقات الأخرى (bold, italic) ستُفقد لأن مواقعها تتغير بعد الترجمة
        
        Args:
            text: النص المراد ترجمته
            entities: قائمة entities
            source_lang: اللغة المصدر
            target_lang: اللغة الهدف
            
        Returns:
            (نجاح, النص المترجم, entities المحدثة, اللغة المكتشفة)
        """
        if not text or not text.strip():
            return False, None, [], None
        
        try:
            from entity_handler import EntityHandler
            
            # فصل entities التي يمكن الحفاظ عليها (links, mentions)
            # من entities التنسيقية (bold, italic, etc)
            preservable_types = ['text_link', 'url', 'mention', 'text_mention', 'email', 'phone_number']
            preservable_entities = [e for e in entities if e.get('type') in preservable_types]
            
            # ترجمة النص فقط
            success, translated_text, detected_lang = await self.translate_text(
                text, source_lang, target_lang
            )
            
            if not success or not translated_text:
                return False, None, [], None
            
            # محاولة إيجاد وحفظ الـ entities القابلة للحفظ في النص المترجم
            new_entities = []
            
            for entity in preservable_entities:
                # استخراج النص الأصلي للـ entity
                from entity_handler import EntityHandler
                offset = entity['offset']
                length = entity['length']
                
                # تحويل من UTF-16 إلى Python index
                py_start = EntityHandler.utf16_offset_to_python(text, offset)
                py_end = EntityHandler.utf16_offset_to_python(text, offset + length)
                entity_text = text[py_start:py_end]
                
                # البحث عن entity_text في النص المترجم
                # بالنسبة لـ URLs وEmail، النص لا يتغير
                if entity.get('type') in ['url', 'email', 'phone_number', 'text_link']:
                    new_py_pos = translated_text.find(entity_text)
                    if new_py_pos != -1:
                        new_offset = EntityHandler.python_offset_to_utf16(translated_text, new_py_pos)
                        new_py_end = new_py_pos + len(entity_text)
                        new_utf16_end = EntityHandler.python_offset_to_utf16(translated_text, new_py_end)
                        new_length = new_utf16_end - new_offset
                        
                        new_entity = entity.copy()
                        new_entity['offset'] = new_offset
                        new_entity['length'] = new_length
                        new_entities.append(new_entity)
            
            logger.info(
                f"✅ تمت الترجمة مع الحفاظ على {len(new_entities)}/{len(preservable_entities)} entities قابلة للحفظ"
            )
            
            return True, translated_text, new_entities, detected_lang
            
        except Exception as e:
            logger.error(f"❌ خطأ في الترجمة مع entities: {e}")
            # في حالة الفشل، نرجع الترجمة العادية بدون entities
            success, translated, detected = await self.translate_text(text, source_lang, target_lang)
            return success, translated, [], detected
    
    def should_translate(self, settings: Dict, detected_lang: Optional[str] = None, text: str = None) -> bool:
        """
        التحقق من ضرورة الترجمة
        
        Args:
            settings: إعدادات الترجمة
            detected_lang: اللغة المكتشفة (اختياري)
            text: النص المراد فحصه (اختياري - لفحص اللغات المختلطة)
            
        Returns:
            True إذا كان يجب الترجمة
        """
        if not settings.get('enabled', False):
            return False
        
        mode = settings.get('mode', 'all_to_target')
        source_lang = settings.get('source_lang', 'auto')
        target_lang = settings.get('target_lang', 'en')
        
        # تطبيع أكواد اللغات
        if detected_lang:
            detected_lang = detected_lang.lower()
        if target_lang:
            target_lang = target_lang.lower()
        
        # إذا كانت اللغة المكتشفة هي نفس اللغة الهدف بشكل كامل، لا حاجة للترجمة
        # لكن نتحقق أولاً إذا كان النص يحتوي على لغات مختلطة
        if detected_lang and detected_lang == target_lang and text:
            # فحص إذا كان النص يحتوي على لغات أخرى (نص مختلط)
            if source_lang != 'auto' and source_lang.lower() != target_lang.lower():
                # فحص وجود اللغة المصدر في النص
                from language_filters import LanguageFilters
                source_ratio = LanguageFilters.detect_language_ratio(text, source_lang)
                # إذا كان هناك 10% أو أكثر من اللغة المصدر، نترجم
                if source_ratio >= 0.10:
                    logger.info(f"✅ نص مختلط: {source_ratio*100:.1f}% من {source_lang} - سيتم الترجمة")
                    return True
            
            logger.info(f"⏭️ تخطي الترجمة: النص بالفعل بنفس اللغة الهدف ({target_lang})")
            return False
        
        # وضع الترجمة من جميع اللغات إلى لغة محددة
        # يترجم كل شيء حتى النصوص المختلطة
        if mode == 'all_to_target':
            return True
        
        # وضع الترجمة من لغة محددة إلى لغة أخرى
        elif mode == 'specific_to_target':
            # إذا لم نتمكن من كشف اللغة، نترجم على أي حال
            if not detected_lang or detected_lang == 'auto' or detected_lang == 'unknown':
                return True
            
            # إذا كانت اللغة المكتشفة تطابق المصدر، نترجم
            if detected_lang == source_lang.lower():
                return True
            
            # فحص النصوص المختلطة
            if text and source_lang != 'auto':
                from language_filters import LanguageFilters
                source_ratio = LanguageFilters.detect_language_ratio(text, source_lang)
                # إذا كان هناك 15% أو أكثر من اللغة المصدر، نترجم
                if source_ratio >= 0.15:
                    logger.info(f"✅ نص مختلط في specific mode: {source_ratio*100:.1f}% من {source_lang} - سيتم الترجمة")
                    return True
            
            logger.info(f"⏭️ تخطي الترجمة: اللغة المكتشفة ({detected_lang}) لا تطابق المصدر ({source_lang})")
            return False
        
        return False
    
    async def process_translation(
        self,
        text: str,
        settings: Dict,
        entities: Optional[List[Dict]] = None
    ) -> Tuple[bool, Optional[str], List[Dict]]:
        """
        معالجة الترجمة حسب الإعدادات
        
        Args:
            text: النص الأصلي
            settings: إعدادات الترجمة
            entities: قائمة entities (اختياري)
            
        Returns:
            (تم التعديل, النص المترجم أو الأصلي, entities المحدثة)
        """
        if not settings.get('enabled', False):
            return False, text, entities or []
        
        source_lang = settings.get('source_lang', 'auto')
        target_lang = settings.get('target_lang', 'en')
        mode = settings.get('mode', 'all_to_target')
        
        # فحص إذا كان النص يحتوي على لغات مختلفة عن اللغة الهدف
        from language_filters import LanguageFilters
        target_ratio = LanguageFilters.detect_language_ratio(text, target_lang)
        has_non_target = target_ratio < 0.95  # إذا كان أقل من 95% من اللغة الهدف
        
        # في وضع specific_to_target، نفحص أولاً إذا كان النص يحتوي على اللغة المصدر
        if mode == 'specific_to_target' and source_lang != 'auto':
            source_ratio = LanguageFilters.detect_language_ratio(text, source_lang)
            # إذا كان النص لا يحتوي على اللغة المصدر بنسبة 10% على الأقل، لا نترجم
            if source_ratio < 0.10:
                logger.info(f"⏭️ تخطي الترجمة: النص يحتوي على {source_ratio*100:.1f}% فقط من {source_lang}")
                return False, text, entities or []
        
        # في وضع all_to_target، إذا كان النص بالكامل باللغة الهدف، لا نترجم
        if mode == 'all_to_target' and not has_non_target:
            logger.info(f"⏭️ تخطي الترجمة: النص بالفعل {target_ratio*100:.1f}% باللغة الهدف ({target_lang})")
            return False, text, entities or []
        
        # محاولة الترجمة مع entities إذا كانت موجودة
        if entities:
            success, translated, new_entities, detected_lang = await self.translate_with_entities(
                text, entities, source_lang, target_lang
            )
        else:
            # إذا كان نص مختلط، نستخدم الترجمة بالتقسيم
            use_split = has_non_target and mode == 'all_to_target'
            success, translated, detected_lang = await self.translate_text(
                text, source_lang, target_lang, split_by_sentence=use_split
            )
            new_entities = []
        
        if not success:
            logger.warning("⚠️ فشلت الترجمة، سيتم استخدام النص الأصلي")
            return False, text, entities or []
        
        # في حالة النصوص المختلطة، نتحقق أن الترجمة فعلاً غيرت النص
        if has_non_target:
            if translated != text:
                logger.info(f"✅ نص مختلط: تمت ترجمة النص بنجاح ({target_ratio*100:.1f}% من اللغة الهدف)")
                return True, translated, new_entities
            else:
                logger.warning(f"⚠️ نص مختلط: الترجمة لم تغير النص، سيتم استخدام الأصلي")
                return False, text, entities or []
        
        # إذا كان النص المترجم مختلف عن الأصلي، نعتبره نجاح
        if translated != text:
            return True, translated, new_entities
        
        logger.info("⏭️ تخطي: النص المترجم هو نفس النص الأصلي")
        return False, text, entities or []
    
    @staticmethod
    def get_language_name(lang_code: str) -> str:
        """
        الحصول على اسم اللغة من الكود
        
        Args:
            lang_code: كود اللغة
            
        Returns:
            اسم اللغة
        """
        # تطبيع الكود
        lang_code_normalized = lang_code.lower()
        if lang_code_normalized == 'zh-cn':
            lang_code_normalized = 'zh-CN'
        
        # البحث في اللغات الشائعة أولاً
        for code, name in TranslationHandler.COMMON_LANGUAGES.items():
            if code.lower() == lang_code_normalized.lower():
                return name
        
        # البحث في جميع اللغات المدعومة
        for name, code in GOOGLE_LANGUAGES_TO_CODES.items():
            if code.lower() == lang_code_normalized.lower():
                return name
        
        return lang_code
    
    @staticmethod
    def get_all_languages() -> Dict[str, str]:
        """الحصول على جميع اللغات المتاحة"""
        # تحويل من اسم -> كود إلى كود -> اسم
        return {code: name for name, code in GOOGLE_LANGUAGES_TO_CODES.items()}
    
    @staticmethod
    def get_common_languages() -> Dict[str, str]:
        """الحصول على اللغات الشائعة"""
        return TranslationHandler.COMMON_LANGUAGES.copy()
    
    @staticmethod
    def get_mode_description(mode: str) -> str:
        """الحصول على وصف الوضع"""
        modes = {
            'all_to_target': '🌍 ترجمة من جميع اللغات إلى اللغة المحددة',
            'specific_to_target': '🎯 ترجمة من لغة محددة إلى لغة أخرى'
        }
        return modes.get(mode, mode)
