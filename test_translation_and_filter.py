"""
اختبار وظائف الترجمة وفلتر اللغة مع entities
"""
import asyncio
import logging
from translation_handler import TranslationHandler
from language_filters import LanguageFilters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_translation():
    """اختبار وظيفة الترجمة"""
    print("\n" + "="*60)
    print("🧪 اختبار وظيفة الترجمة")
    print("="*60)
    
    translator = TranslationHandler()
    
    # اختبار 1: ترجمة من الإنجليزية للعربية
    print("\n📝 اختبار 1: ترجمة من الإنجليزية للعربية")
    text_en = "Hello, how are you?"
    success, translated, detected = await translator.translate_text(text_en, 'auto', 'ar')
    print(f"النص الأصلي: {text_en}")
    print(f"النص المترجم: {translated}")
    print(f"اللغة المكتشفة: {detected}")
    print(f"النتيجة: {'✅ نجح' if success else '❌ فشل'}")
    
    # اختبار 2: ترجمة من العربية للإنجليزية
    print("\n📝 اختبار 2: ترجمة من العربية للإنجليزية")
    text_ar = "مرحباً، كيف حالك؟"
    success, translated, detected = await translator.translate_text(text_ar, 'auto', 'en')
    print(f"النص الأصلي: {text_ar}")
    print(f"النص المترجم: {translated}")
    print(f"اللغة المكتشفة: {detected}")
    print(f"النتيجة: {'✅ نجح' if success else '❌ فشل'}")
    
    # اختبار 3: process_translation مع all_to_target
    print("\n📝 اختبار 3: معالجة الترجمة - وضع all_to_target")
    settings = {
        'enabled': True,
        'mode': 'all_to_target',
        'source_lang': 'auto',
        'target_lang': 'ar'
    }
    text_test = "This is a test message for translation"
    modified, result, entities = await translator.process_translation(text_test, settings)
    print(f"النص الأصلي: {text_test}")
    print(f"النص المعالج: {result}")
    print(f"تم التعديل: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 4: process_translation مع specific_to_target
    print("\n📝 اختبار 4: معالجة الترجمة - وضع specific_to_target (en->ar)")
    settings = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    text_en = "This should be translated"
    modified, result, entities = await translator.process_translation(text_en, settings)
    print(f"النص الأصلي: {text_en}")
    print(f"النص المعالج: {result}")
    print(f"تم التعديل: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 5: ترجمة مع entities
    print("\n📝 اختبار 5: ترجمة مع الحفاظ على entities")
    text_with_format = "Hello world"
    entities_list = [
        {'type': 'bold', 'offset': 0, 'length': 5},  # "Hello" bold
        {'type': 'italic', 'offset': 6, 'length': 5}  # "world" italic
    ]
    success, translated, new_entities, detected = await translator.translate_with_entities(
        text_with_format, entities_list, 'en', 'ar'
    )
    print(f"النص الأصلي: {text_with_format}")
    print(f"Entities الأصلية: {entities_list}")
    print(f"النص المترجم: {translated}")
    print(f"Entities الجديدة: {new_entities}")
    print(f"النتيجة: {'✅ نجح' if success else '❌ فشل'}")

def test_language_filter():
    """اختبار فلتر اللغة"""
    print("\n" + "="*60)
    print("🧪 اختبار فلتر اللغة")
    print("="*60)
    
    # اختبار 1: نص عربي كامل - وضع full
    print("\n📝 اختبار 1: نص عربي كامل - وضع السماح - حساسية كاملة")
    text_ar_full = "هذا نص عربي كامل بدون أي كلمات إنجليزية"
    allowed, reason = LanguageFilters.apply_language_filter(text_ar_full, 'allow', ['ar'], 'full')
    ratio = LanguageFilters.detect_language_ratio(text_ar_full, 'ar')
    print(f"النص: {text_ar_full}")
    print(f"نسبة العربية: {ratio*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")
    
    # اختبار 2: نص مختلط - وضع full
    print("\n📝 اختبار 2: نص مختلط (عربي + إنجليزي) - وضع السماح - حساسية كاملة")
    text_mixed = "هذا نص مختلط with some English words"
    allowed, reason = LanguageFilters.apply_language_filter(text_mixed, 'allow', ['ar'], 'full')
    ratio = LanguageFilters.detect_language_ratio(text_mixed, 'ar')
    print(f"النص: {text_mixed}")
    print(f"نسبة العربية: {ratio*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")
    
    # اختبار 3: نص مختلط - وضع partial
    print("\n📝 اختبار 3: نص مختلط (عربي + إنجليزي) - وضع السماح - حساسية جزئية")
    allowed, reason = LanguageFilters.apply_language_filter(text_mixed, 'allow', ['ar'], 'partial')
    print(f"النص: {text_mixed}")
    print(f"نسبة العربية: {ratio*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")
    
    # اختبار 4: نص إنجليزي فقط - وضع block
    print("\n📝 اختبار 4: نص إنجليزي فقط - وضع الحظر - حساسية كاملة")
    text_en_full = "This is a complete English text without any Arabic"
    allowed, reason = LanguageFilters.apply_language_filter(text_en_full, 'block', ['en'], 'full')
    ratio = LanguageFilters.detect_language_ratio(text_en_full, 'en')
    print(f"النص: {text_en_full}")
    print(f"نسبة الإنجليزية: {ratio*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")
    
    # اختبار 5: نص إنجليزي قليل - وضع block partial
    print("\n📝 اختبار 5: نص مختلط (قليل من الإنجليزية) - وضع الحظر - حساسية جزئية")
    text_little_en = "هذا نص عربي مع كلمات قليلة بالإنجليزية like this"
    allowed, reason = LanguageFilters.apply_language_filter(text_little_en, 'block', ['en'], 'partial')
    ratio_en = LanguageFilters.detect_language_ratio(text_little_en, 'en')
    print(f"النص: {text_little_en}")
    print(f"نسبة الإنجليزية: {ratio_en*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")
    
    # اختبار 6: نص إنجليزي قليل - وضع block full
    print("\n📝 اختبار 6: نص مختلط (قليل من الإنجليزية) - وضع الحظر - حساسية كاملة")
    allowed, reason = LanguageFilters.apply_language_filter(text_little_en, 'block', ['en'], 'full')
    print(f"النص: {text_little_en}")
    print(f"نسبة الإنجليزية: {ratio_en*100:.1f}%")
    print(f"النتيجة: {'✅ مسموح' if allowed else f'❌ محظور - {reason}'}")

async def main():
    """تشغيل جميع الاختبارات"""
    print("\n🚀 بدء الاختبارات الشاملة")
    
    # اختبار الترجمة
    await test_translation()
    
    # اختبار فلتر اللغة
    test_language_filter()
    
    print("\n" + "="*60)
    print("✅ اكتملت جميع الاختبارات")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
