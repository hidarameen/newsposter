"""
اختبار ترجمة النصوص المختلطة (عربي + إنجليزي)
"""
import asyncio
import logging
from translation_handler import TranslationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mixed_text_translation():
    """اختبار ترجمة النصوص المختلطة"""
    print("\n" + "="*70)
    print("🧪 اختبار ترجمة النصوص المختلطة (عربي + إنجليزي)")
    print("="*70)
    
    translator = TranslationHandler()
    
    # اختبار 1: نص مختلط - all_to_target
    print("\n📝 اختبار 1: نص مختلط - وضع all_to_target (ترجمة الكل للعربية)")
    mixed_text_1 = "This is English text مع بعض الكلمات العربية here and there"
    settings_1 = {
        'enabled': True,
        'mode': 'all_to_target',
        'source_lang': 'auto',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(mixed_text_1, settings_1)
    print(f"النص الأصلي: {mixed_text_1}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 2: نص مختلط - specific_to_target (ترجمة الإنجليزي فقط)
    print("\n📝 اختبار 2: نص مختلط - وضع specific_to_target (إنجليزي->عربي)")
    mixed_text_2 = "مرحباً هذا نص عربي with some English words في المنتصف"
    settings_2 = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(mixed_text_2, settings_2)
    print(f"النص الأصلي: {mixed_text_2}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 3: نص عربي غالب مع قليل من الإنجليزي
    print("\n📝 اختبار 3: نص عربي غالب مع 20% إنجليزي")
    mixed_text_3 = "هذا نص عربي طويل جداً يحتوي على الكثير من الكلمات العربية with just a few English words"
    settings_3 = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(mixed_text_3, settings_3)
    print(f"النص الأصلي: {mixed_text_3}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 4: نص إنجليزي غالب مع قليل من العربي
    print("\n📝 اختبار 4: نص إنجليزي غالب مع قليل من العربي")
    mixed_text_4 = "This is a long English text with many English words and مع بعض الكلمات العربية"
    settings_4 = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(mixed_text_4, settings_4)
    print(f"النص الأصلي: {mixed_text_4}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم' if modified else '❌ لا'}")
    
    # اختبار 5: نص عربي فقط - يجب ألا يترجم (في وضع en->ar)
    print("\n📝 اختبار 5: نص عربي فقط - لا يجب ترجمته (في وضع en->ar)")
    arabic_only = "هذا نص عربي كامل بدون أي كلمات إنجليزية على الإطلاق"
    settings_5 = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(arabic_only, settings_5)
    print(f"النص الأصلي: {arabic_only}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم (خطأ!)' if modified else '❌ لا (صحيح!)'}")
    
    # اختبار 6: نص إنجليزي فقط - يجب أن يترجم (في وضع en->ar)
    print("\n📝 اختبار 6: نص إنجليزي فقط - يجب ترجمته (في وضع en->ar)")
    english_only = "This is a complete English text without any Arabic words at all"
    settings_6 = {
        'enabled': True,
        'mode': 'specific_to_target',
        'source_lang': 'en',
        'target_lang': 'ar'
    }
    modified, result, entities = await translator.process_translation(english_only, settings_6)
    print(f"النص الأصلي: {english_only}")
    print(f"النص المعالج: {result}")
    print(f"تم الترجمة: {'✅ نعم (صحيح!)' if modified else '❌ لا (خطأ!)'}")
    
    print("\n" + "="*70)
    print("✅ اكتملت اختبارات النصوص المختلطة")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(test_mixed_text_translation())
