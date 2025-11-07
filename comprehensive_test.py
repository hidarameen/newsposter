#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ملف اختبار شامل لجميع وظائف نظام توجيه الرسائل
Comprehensive Test Suite for Message Forwarding System
"""

import os
import json
import shutil
from datetime import datetime, timedelta
from typing import List, Optional

# استيراد الوحدات المطلوبة
from subscription_manager import SubscriptionManager
from user_task_manager import UserTaskManager
from task_settings_manager import TaskSettingsManager
from message_processor import MessageProcessor
from text_filters import TextFilters
from link_filters import LinkFilters
from media_filters import MediaFilters
from language_filters import LanguageFilters
from entity_handler import EntityHandler
from button_parser import ButtonParser

# ========== Mock Classes ==========

class MockMessageEntity:
    """محاكاة كائن MessageEntity من Telegram"""
    def __init__(self, type: str, offset: int, length: int, url: Optional[str] = None):
        self.type = type
        self.offset = offset
        self.length = length
        self.url = url
        self.user = None
        self.language = None

class MockMessage:
    """محاكاة كائن Message من Telegram"""
    def __init__(self, text: Optional[str] = None, caption: Optional[str] = None, 
                 photo=None, video=None, document=None, 
                 forward_date=None, entities=None, caption_entities=None,
                 reply_markup=None):
        self.text = text
        self.caption = caption
        self.photo = photo
        self.video = video
        self.document = document
        self.audio = None
        self.voice = None
        self.video_note = None
        self.animation = None
        self.sticker = None
        self.forward_date = forward_date
        self.entities = entities or []
        self.caption_entities = caption_entities or []
        self.reply_markup = reply_markup
        self.media_group_id: Optional[str] = None

# ========== Test Statistics ==========

class TestStats:
    """إحصائيات الاختبارات"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        self.total += 1
        if passed:
            self.passed += 1
            status = "✅"
        else:
            self.failed += 1
            status = "❌"
        
        result = f"{status} {test_name}"
        if message:
            result += f": {message}"
        
        self.results.append(result)
        print(result)
    
    def print_summary(self):
        print("\n" + "="*60)
        print("📊 ملخص النتائج / Test Summary")
        print("="*60)
        print(f"إجمالي الاختبارات / Total Tests: {self.total}")
        print(f"ناجح / Passed: {self.passed} ✅")
        print(f"فاشل / Failed: {self.failed} ❌")
        print(f"نسبة النجاح / Success Rate: {(self.passed/self.total*100):.1f}%")
        print("="*60)
        
        if self.failed > 0:
            print("\n❌ الاختبارات الفاشلة / Failed Tests:")
            for result in self.results:
                if result.startswith("❌"):
                    print(f"  {result}")

stats = TestStats()

# ========== Helper Functions ==========

def print_section(title: str):
    """طباعة عنوان قسم"""
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def cleanup_test_user(user_id: int):
    """حذف بيانات مستخدم الاختبار"""
    user_dir = f"users_data/{user_id}"
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)

# ========== Test Functions ==========

def test_subscription_system():
    """1️⃣ اختبار نظام الاشتراكات"""
    print_section("اختبار نظام الاشتراكات / Subscription System Test")
    
    test_user_id = 999999
    cleanup_test_user(test_user_id)
    
    # إنشاء مدير الاشتراكات
    sub_manager = SubscriptionManager(test_user_id)
    
    # اختبار 1: المستخدم الجديد يجب أن يكون في الخطة المجانية
    plan_details = sub_manager.get_plan_details()
    stats.add_result(
        "المستخدم الجديد - خطة مجانية",
        plan_details['plan'] == 'free' and not plan_details['is_active'],
        f"الخطة: {plan_details['plan']}"
    )
    
    # اختبار 2: المستخدم الجديد يمكنه استخدام التجربة المجانية
    can_trial = sub_manager.can_use_trial()
    stats.add_result(
        "إمكانية التجربة المجانية",
        can_trial,
        "يمكن استخدام التجربة المجانية"
    )
    
    # اختبار 3: الترقية إلى Premium مع تجربة مجانية 7 أيام
    sub_manager.activate_subscription('premium', 7, is_trial=True)
    plan_details = sub_manager.get_plan_details()
    stats.add_result(
        "تفعيل Premium - تجربة 7 أيام",
        plan_details['plan'] == 'premium' and 
        plan_details['is_active'] and 
        plan_details['is_trial'],
        f"الأيام المتبقية: {plan_details['days_remaining']}"
    )
    
    # اختبار 4: التحقق من أنه لا يمكن استخدام التجربة المجانية مرة أخرى
    can_trial_again = sub_manager.can_use_trial()
    stats.add_result(
        "منع التجربة المجانية المتكررة",
        not can_trial_again,
        "لا يمكن استخدام التجربة مرة أخرى"
    )
    
    # اختبار 5: التحقق من الحد الأقصى للمهام
    max_tasks = sub_manager.get_max_tasks()
    stats.add_result(
        "الحد الأقصى للمهام - Premium",
        max_tasks == -1,
        "غير محدود للـ Premium"
    )
    
    cleanup_test_user(test_user_id)

def test_task_limits():
    """2️⃣ اختبار حدود إضافة المهام"""
    print_section("اختبار حدود المهام / Task Limits Test")
    
    test_user_id = 999998
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    task_manager = UserTaskManager(test_user_id)
    
    # اختبار 1: المستخدم المجاني يمكنه إضافة مهمة واحدة
    can_add_first = sub_manager.can_add_task(0)
    stats.add_result(
        "المستخدم المجاني - إضافة المهمة الأولى",
        can_add_first,
        "يمكن إضافة مهمة واحدة"
    )
    
    # إضافة المهمة الأولى
    task_id = task_manager.add_task(
        admin_task_id=1,
        admin_task_name="شهاب",
        source_channel={'id': -1001234567890, 'name': 'قناة المصدر'},
        target_channel={'id': -1009876543210, 'name': 'قناة الهدف'}
    )
    
    # اختبار 2: المستخدم المجاني لا يمكنه إضافة مهمة ثانية
    current_tasks = len(task_manager.get_all_tasks())
    can_add_second = sub_manager.can_add_task(current_tasks)
    stats.add_result(
        "المستخدم المجاني - منع المهمة الثانية",
        not can_add_second,
        f"عدد المهام الحالية: {current_tasks}"
    )
    
    # اختبار 3: بعد الترقية للPremium، يمكن إضافة مهام غير محدودة
    sub_manager.activate_subscription('premium', 30)
    can_add_unlimited = sub_manager.can_add_task(current_tasks)
    stats.add_result(
        "Premium - إضافة مهام غير محدودة",
        can_add_unlimited,
        "يمكن إضافة عدد غير محدود من المهام"
    )
    
    # إضافة مهام إضافية للتأكيد
    task_id2 = task_manager.add_task(
        admin_task_id=2,
        admin_task_name="مهمة 2",
        source_channel={'id': -1001111111111, 'name': 'قناة 2'},
        target_channel={'id': -1002222222222, 'name': 'هدف 2'}
    )
    
    task_id3 = task_manager.add_task(
        admin_task_id=3,
        admin_task_name="مهمة 3",
        source_channel={'id': -1003333333333, 'name': 'قناة 3'},
        target_channel={'id': -1004444444444, 'name': 'هدف 3'}
    )
    
    total_tasks = len(task_manager.get_all_tasks())
    stats.add_result(
        "Premium - إضافة 3 مهام",
        total_tasks == 3,
        f"إجمالي المهام: {total_tasks}"
    )
    
    cleanup_test_user(test_user_id)

def test_media_filters():
    """3️⃣ اختبار فلاتر الوسائط"""
    print_section("اختبار فلاتر الوسائط / Media Filters Test")
    
    test_user_id = 999997
    task_id = 1
    cleanup_test_user(test_user_id)
    
    # تفعيل Premium
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: تفعيل فلتر الوسائط (السماح فقط بالنصوص)
    settings_manager.update_setting('media_filters', 'enabled', True)
    settings_manager.set_media_filters(['text'])
    
    # اختبار رسالة نصية (يجب أن تمر)
    text_message = MockMessage(text="مرحبا بك")
    is_allowed = MediaFilters.is_media_allowed(text_message, ['text'])  # type: ignore
    stats.add_result(
        "فلتر الوسائط - رسالة نصية مسموحة",
        is_allowed,
        "النصوص مسموحة"
    )
    
    # اختبار رسالة صورة (يجب أن تحظر)
    photo_message = MockMessage(photo=[{'file_id': 'photo123'}], caption="صورة")
    is_blocked = not MediaFilters.is_media_allowed(photo_message, ['text'])  # type: ignore
    stats.add_result(
        "فلتر الوسائط - حظر الصور",
        is_blocked,
        "الصور محظورة"
    )
    
    # اختبار 2: السماح بالصور والفيديوهات
    settings_manager.set_media_filters(['photo', 'video', 'text'])
    photo_allowed = MediaFilters.is_media_allowed(photo_message, ['photo', 'video', 'text'])  # type: ignore
    stats.add_result(
        "فلتر الوسائط - السماح بالصور",
        photo_allowed,
        "الصور مسموحة بعد التحديث"
    )
    
    cleanup_test_user(test_user_id)

def test_word_filters():
    """4️⃣ اختبار فلاتر الكلمات"""
    print_section("اختبار فلاتر الكلمات / Word Filters Test")
    
    test_user_id = 999996
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: القائمة البيضاء (Whitelist)
    settings_manager.update_setting('whitelist_words', 'enabled', True)
    settings_manager.add_whitelist_word('مرحبا')
    settings_manager.add_whitelist_word('أهلا')
    
    allowed, reason = TextFilters.apply_whitelist('مرحبا بك', ['مرحبا', 'أهلا'])
    stats.add_result(
        "القائمة البيضاء - كلمة مسموحة",
        allowed,
        "الرسالة تحتوي على كلمة من القائمة البيضاء"
    )
    
    not_allowed, reason = TextFilters.apply_whitelist('مساء الخير', ['مرحبا', 'أهلا'])
    stats.add_result(
        "القائمة البيضاء - كلمة غير مسموحة",
        not not_allowed,
        reason
    )
    
    # اختبار 2: القائمة السوداء (Blacklist)
    settings_manager.update_setting('blacklist_words', 'enabled', True)
    settings_manager.add_blacklist_word('سيء')
    settings_manager.add_blacklist_word('محظور')
    
    blocked, reason = TextFilters.apply_blacklist('هذا محتوى سيء', ['سيء', 'محظور'])
    stats.add_result(
        "القائمة السوداء - حظر كلمة",
        not blocked,
        reason
    )
    
    passed, reason = TextFilters.apply_blacklist('هذا محتوى جيد', ['سيء', 'محظور'])
    stats.add_result(
        "القائمة السوداء - كلمة آمنة",
        passed,
        "لا توجد كلمات محظورة"
    )
    
    # اختبار 3: الاستبدالات
    settings_manager.update_setting('replacements', 'enabled', True)
    settings_manager.add_replacement('قديم', 'جديد')
    settings_manager.add_replacement('ضعيف', 'قوي')
    
    new_text, entities = TextFilters.apply_replacements(
        'النظام قديم والأداء ضعيف جداً',
        [{'old': 'قديم', 'new': 'جديد'}, {'old': 'ضعيف', 'new': 'قوي'}]
    )
    stats.add_result(
        "الاستبدالات - تبديل الكلمات",
        'جديد' in new_text and 'قوي' in new_text,
        f"النص الجديد: {new_text}"
    )
    
    cleanup_test_user(test_user_id)

def test_link_filters():
    """5️⃣ اختبار فلاتر الروابط"""
    print_section("اختبار فلاتر الروابط / Link Filters Test")
    
    test_user_id = 999995
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: اكتشاف الروابط
    test_text = "زوروا موقعنا https://example.com وحسابنا @username"
    links = LinkFilters.find_all_links(test_text)
    stats.add_result(
        "اكتشاف الروابط",
        len(links) >= 2,
        f"تم اكتشاف {len(links)} روابط"
    )
    
    # اختبار 2: حظر الروابط
    settings_manager.update_setting('link_management', 'enabled', True)
    settings_manager.update_setting('link_management', 'mode', 'block')
    
    allowed, result_text, entities = LinkFilters.apply_link_filter(test_text, 'block')
    stats.add_result(
        "حظر الروابط - block mode",
        not allowed,
        "تم حظر الرسالة لاحتوائها على روابط"
    )
    
    # اختبار 3: إزالة الروابط
    settings_manager.update_setting('link_management', 'mode', 'remove')
    allowed, cleaned_text, entities = LinkFilters.apply_link_filter(test_text, 'remove')
    has_no_links = 'https://' not in cleaned_text and '@username' not in cleaned_text
    stats.add_result(
        "إزالة الروابط - remove mode",
        allowed and has_no_links,
        f"النص بعد التنظيف: {cleaned_text}"
    )
    
    # اختبار 4: نص بدون روابط
    clean_text = "هذا نص عادي بدون روابط"
    allowed, result, entities = LinkFilters.apply_link_filter(clean_text, 'block')
    stats.add_result(
        "نص بدون روابط",
        allowed,
        "النص مسموح (لا يحتوي على روابط)"
    )
    
    cleanup_test_user(test_user_id)

def test_language_filters():
    """6️⃣ اختبار فلاتر اللغة"""
    print_section("اختبار فلاتر اللغة / Language Filters Test")
    
    test_user_id = 999994
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: اكتشاف اللغة العربية
    arabic_text = "مرحبا بكم في اختبار اللغة العربية"
    ar_ratio = LanguageFilters.detect_language_ratio(arabic_text, 'ar')
    stats.add_result(
        "اكتشاف اللغة العربية",
        ar_ratio > 0.7,
        f"نسبة اللغة العربية: {ar_ratio:.2f}"
    )
    
    # اختبار 2: اكتشاف اللغة الإنجليزية
    english_text = "Hello welcome to the English language test"
    en_ratio = LanguageFilters.detect_language_ratio(english_text, 'en')
    stats.add_result(
        "اكتشاف اللغة الإنجليزية",
        en_ratio > 0.7,
        f"نسبة اللغة الإنجليزية: {en_ratio:.2f}"
    )
    
    # اختبار 3: السماح بالعربية فقط
    settings_manager.update_setting('language_filter', 'enabled', True)
    settings_manager.update_setting('language_filter', 'mode', 'allow')
    settings_manager.update_setting('language_filter', 'languages', ['ar'])
    
    allowed, reason = LanguageFilters.apply_language_filter(arabic_text, 'allow', ['ar'], 'full')
    stats.add_result(
        "السماح بالعربية - نص عربي",
        allowed,
        "النص العربي مسموح"
    )
    
    not_allowed, reason = LanguageFilters.apply_language_filter(english_text, 'allow', ['ar'], 'full')
    stats.add_result(
        "السماح بالعربية - حظر الإنجليزية",
        not not_allowed,
        reason
    )
    
    # اختبار 4: حظر الإنجليزية
    blocked, reason = LanguageFilters.apply_language_filter(english_text, 'block', ['en'], 'full')
    stats.add_result(
        "حظر الإنجليزية",
        not blocked,
        reason
    )
    
    cleanup_test_user(test_user_id)

def test_forwarded_filter():
    """7️⃣ اختبار فلتر الرسائل المعاد توجيهها"""
    print_section("اختبار فلتر الرسائل المعاد توجيهها / Forwarded Messages Filter Test")
    
    test_user_id = 999993
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # تفعيل فلتر الرسائل المعاد توجيهها
    settings_manager.update_setting('forwarded_filter', 'enabled', True)
    settings_manager.update_setting('forwarded_filter', 'mode', 'block')
    
    # اختبار 1: حظر رسالة معاد توجيهها
    is_forwarded = True
    result = TextFilters.check_forwarded_filter(is_forwarded, 'block')
    stats.add_result(
        "حظر الرسائل المعاد توجيهها",
        not result,
        "تم حظر الرسالة المعاد توجيهها"
    )
    
    # اختبار 2: السماح برسالة عادية
    is_forwarded = False
    result = TextFilters.check_forwarded_filter(is_forwarded, 'block')
    stats.add_result(
        "السماح بالرسائل العادية",
        result,
        "الرسالة العادية مسموحة"
    )
    
    # اختبار 3: وضع السماح بكل شيء
    settings_manager.update_setting('forwarded_filter', 'mode', 'allow')
    result = TextFilters.check_forwarded_filter(True, 'allow')
    stats.add_result(
        "السماح بجميع الرسائل",
        result,
        "جميع الرسائل مسموحة في وضع allow"
    )
    
    cleanup_test_user(test_user_id)

def test_header_footer():
    """8️⃣ اختبار Header وFooter"""
    print_section("اختبار Header و Footer / Header & Footer Test")
    
    test_user_id = 999992
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: إضافة Header مع entities
    header_text = "📢 رأس الرسالة"
    header_entities = [
        {'type': 'bold', 'offset': 0, 'length': 4},
    ]
    settings_manager.update_setting('header', 'enabled', True)
    settings_manager.set_header(header_text, header_entities)
    
    settings = settings_manager.load_settings()
    stats.add_result(
        "إضافة Header",
        settings['header']['enabled'] and settings['header']['text'] == header_text,
        f"Header: {header_text}"
    )
    
    # اختبار 2: إضافة Footer مع entities
    footer_text = "📝 ذيل الرسالة"
    footer_entities = [
        {'type': 'italic', 'offset': 0, 'length': 4},
    ]
    settings_manager.update_setting('footer', 'enabled', True)
    settings_manager.set_footer(footer_text, footer_entities)
    
    settings = settings_manager.load_settings()
    stats.add_result(
        "إضافة Footer",
        settings['footer']['enabled'] and settings['footer']['text'] == footer_text,
        f"Footer: {footer_text}"
    )
    
    # اختبار 3: دمج Header مع النص الأصلي
    original_text = "النص الأصلي"
    original_entities = []
    
    # محاكاة إضافة header
    merged_text = header_text + '\n' + original_text
    header_len = len(header_text) + 1
    shifted_entities = EntityHandler.shift_entities(original_entities, header_len)
    final_entities = EntityHandler.merge_entities(header_entities, shifted_entities)
    
    stats.add_result(
        "دمج Header مع النص",
        merged_text.startswith(header_text) and original_text in merged_text,
        f"النص المدمج: {merged_text[:50]}..."
    )
    
    # اختبار 4: إضافة أزرار مخصصة
    buttons = [
        [
            {'text': 'زيارة الموقع', 'type': 'url', 'url': 'https://example.com'},
            {'text': 'المساعدة', 'type': 'url', 'url': 'https://help.example.com'}
        ],
        [
            {'text': 'شارك على Facebook', 'type': 'share', 'platform': 'facebook'}
        ]
    ]
    settings_manager.update_setting('inline_buttons', 'enabled', True)
    settings_manager.set_inline_buttons(buttons)
    
    settings = settings_manager.load_settings()
    stats.add_result(
        "إضافة أزرار مخصصة",
        settings['inline_buttons']['enabled'] and len(settings['inline_buttons']['buttons']) == 2,
        f"عدد صفوف الأزرار: {len(buttons)}"
    )
    
    cleanup_test_user(test_user_id)

def test_message_processing():
    """9️⃣ اختبار معالجة الرسائل"""
    print_section("اختبار معالجة الرسائل / Message Processing Test")
    
    test_user_id = 999991
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    processor = MessageProcessor(test_user_id, task_id)
    
    # اختبار 1: رسالة نصية بسيطة
    simple_message = MockMessage(text="مرحبا بكم")
    allowed, text, entities, reason = processor.process_message_text(simple_message)  # type: ignore
    stats.add_result(
        "معالجة رسالة نصية بسيطة",
        allowed and text == "مرحبا بكم",
        "تمت المعالجة بنجاح"
    )
    
    # اختبار 2: رسالة مع كلمات محظورة
    settings_manager.update_setting('blacklist_words', 'enabled', True)
    settings_manager.add_blacklist_word('سيء')
    
    processor = MessageProcessor(test_user_id, task_id)  # إعادة إنشاء للتحديث
    bad_message = MockMessage(text="هذا محتوى سيء")
    allowed, text, entities, reason = processor.process_message_text(bad_message)  # type: ignore
    stats.add_result(
        "حظر رسالة مع كلمة محظورة",
        not allowed,
        reason
    )
    
    # اختبار 3: رسالة مع روابط
    settings_manager.update_setting('link_management', 'enabled', True)
    settings_manager.update_setting('link_management', 'mode', 'remove')
    
    processor = MessageProcessor(test_user_id, task_id)
    link_message = MockMessage(text="زوروا https://example.com للمزيد")
    allowed, text, entities, reason = processor.process_message_text(link_message)  # type: ignore
    has_no_link = text is not None and 'https://' not in text
    stats.add_result(
        "معالجة رسالة مع روابط",
        allowed and has_no_link,
        f"النص بعد الإزالة: {text}"
    )
    
    # اختبار 4: رسالة معاد توجيهها
    settings_manager.update_setting('forwarded_filter', 'enabled', True)
    settings_manager.update_setting('forwarded_filter', 'mode', 'block')
    
    processor = MessageProcessor(test_user_id, task_id)
    forwarded_message = MockMessage(text="رسالة معاد توجيهها", forward_date=datetime.now())
    should_process, reason = processor.should_process_message(forwarded_message)  # type: ignore
    stats.add_result(
        "حظر رسالة معاد توجيهها",
        not should_process,
        reason
    )
    
    # اختبار 5: رسالة بلغة محظورة
    settings_manager.update_setting('language_filter', 'enabled', True)
    settings_manager.update_setting('language_filter', 'mode', 'allow')
    settings_manager.update_setting('language_filter', 'languages', ['ar'])
    
    processor = MessageProcessor(test_user_id, task_id)
    english_message = MockMessage(text="This is an English message")
    allowed, text, entities, reason = processor.process_message_text(english_message)  # type: ignore
    stats.add_result(
        "حظر رسالة بلغة غير مسموحة",
        not allowed,
        reason
    )
    
    cleanup_test_user(test_user_id)

def test_duplicate_prevention():
    """🔟 اختبار منع التكرار"""
    print_section("اختبار منع التكرار / Duplicate Prevention Test")
    
    test_user_id = 999990
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: منع تكرار الكلمات المحظورة
    settings_manager.add_blacklist_word('كلمة1')
    settings_manager.add_blacklist_word('كلمة2')
    
    settings = settings_manager.load_settings()
    initial_count = len(settings['blacklist_words']['words'])
    
    # محاولة إضافة نفس الكلمة
    settings_manager.add_blacklist_word('كلمة1')
    
    settings = settings_manager.load_settings()
    final_count = len(settings['blacklist_words']['words'])
    
    stats.add_result(
        "منع تكرار الكلمات المحظورة",
        initial_count == final_count,
        f"العدد قبل: {initial_count}, بعد: {final_count}"
    )
    
    # اختبار 2: منع تكرار الكلمات في القائمة البيضاء
    settings_manager.add_whitelist_word('مسموح1')
    settings_manager.add_whitelist_word('مسموح2')
    
    settings = settings_manager.load_settings()
    initial_count = len(settings['whitelist_words']['words'])
    
    settings_manager.add_whitelist_word('مسموح1')
    
    settings = settings_manager.load_settings()
    final_count = len(settings['whitelist_words']['words'])
    
    stats.add_result(
        "منع تكرار الكلمات المسموحة",
        initial_count == final_count,
        f"العدد قبل: {initial_count}, بعد: {final_count}"
    )
    
    # اختبار 3: الكلمات الفريدة
    unique_words = list(set(['كلمة1', 'كلمة2', 'كلمة1', 'كلمة3']))
    stats.add_result(
        "فحص فرادة الكلمات",
        len(unique_words) == 3,
        f"كلمات فريدة: {unique_words}"
    )
    
    cleanup_test_user(test_user_id)

def test_entity_handling():
    """1️⃣1️⃣ اختبار معالجة Entities"""
    print_section("اختبار معالجة Entities / Entity Handling Test")
    
    # اختبار 1: تحويل entities من وإلى dict
    mock_entities = [
        MockMessageEntity('bold', 0, 5),
        MockMessageEntity('italic', 6, 4),
        MockMessageEntity('text_link', 11, 4, 'https://example.com')
    ]
    
    entities_dict = EntityHandler.entities_to_dict(mock_entities)  # type: ignore
    stats.add_result(
        "تحويل Entities إلى Dict",
        len(entities_dict) == 3 and entities_dict[2]['url'] == 'https://example.com',
        f"عدد الـ entities: {len(entities_dict)}"
    )
    
    # اختبار 2: تحويل dict إلى entities
    entities_back = EntityHandler.dict_to_entities(entities_dict)
    stats.add_result(
        "تحويل Dict إلى Entities",
        len(entities_back) == 3 and entities_back[0].type == 'bold',
        f"عدد الـ entities: {len(entities_back)}"
    )
    
    # اختبار 3: إزاحة entities
    shifted = EntityHandler.shift_entities(entities_dict, 10)
    stats.add_result(
        "إزاحة Entities",
        shifted[0]['offset'] == 10 and shifted[1]['offset'] == 16,
        f"الإزاحات الجديدة: {[e['offset'] for e in shifted]}"
    )
    
    # اختبار 4: دمج entities
    entities1 = [{'type': 'bold', 'offset': 0, 'length': 5}]
    entities2 = [{'type': 'italic', 'offset': 10, 'length': 5}]
    merged = EntityHandler.merge_entities(entities1, entities2)
    stats.add_result(
        "دمج Entities",
        len(merged) == 2 and merged[0]['offset'] < merged[1]['offset'],
        f"عدد الـ entities المدمجة: {len(merged)}"
    )

def test_album_processing():
    """1️⃣2️⃣ اختبار معالجة الألبومات"""
    print_section("اختبار معالجة الألبومات / Album Processing Test")
    
    test_user_id = 999989
    task_id = 1
    cleanup_test_user(test_user_id)
    
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # اختبار 1: إنشاء ألبوم من 3 صور
    album_messages = [
        MockMessage(photo=[{'file_id': 'photo1'}], caption="صورة 1"),
        MockMessage(photo=[{'file_id': 'photo2'}], caption=""),
        MockMessage(photo=[{'file_id': 'photo3'}], caption=""),
    ]
    
    # تعيين media_group_id لجميع الرسائل
    media_group_id = "album123"
    for msg in album_messages:
        msg.media_group_id = media_group_id
    
    stats.add_result(
        "إنشاء ألبوم - 3 صور",
        len(album_messages) == 3,
        f"عدد الرسائل في الألبوم: {len(album_messages)}"
    )
    
    # اختبار 2: السماح بالألبومات
    from album_processor import AlbumProcessor
    album_proc = AlbumProcessor(test_user_id, task_id)
    
    is_allowed, reason = album_proc.is_album_allowed(album_messages)  # type: ignore
    stats.add_result(
        "التحقق من الألبوم المسموح",
        is_allowed,
        "الألبوم مسموح بشكل افتراضي"
    )
    
    # اختبار 3: حظر ألبوم بناءً على فلتر الوسائط
    settings_manager.update_setting('media_filters', 'enabled', True)
    settings_manager.set_media_filters(['text', 'video'])  # فقط النصوص والفيديو، لا صور
    
    album_proc = AlbumProcessor(test_user_id, task_id)
    is_blocked, reason = album_proc.is_album_allowed(album_messages)  # type: ignore
    stats.add_result(
        "حظر ألبوم الصور",
        not is_blocked,
        reason
    )
    
    # اختبار 4: السماح بألبوم الصور بعد التحديث
    settings_manager.set_media_filters(['text', 'photo', 'video'])
    album_proc = AlbumProcessor(test_user_id, task_id)
    is_allowed, reason = album_proc.is_album_allowed(album_messages)  # type: ignore
    stats.add_result(
        "السماح بألبوم الصور",
        is_allowed,
        "تم السماح بالألبوم بعد تحديث الفلتر"
    )
    
    # اختبار 5: التحقق من Header/Footer في الألبومات
    settings_manager.update_setting('header', 'enabled', True)
    settings_manager.set_header("📸 ألبوم الصور", [])
    
    settings_manager.update_setting('footer', 'enabled', True)
    settings_manager.set_footer("🔗 @PhotoChannel", [])
    
    processor = MessageProcessor(test_user_id, task_id)
    allowed, text, entities, reason = processor.process_message_text(album_messages[0])  # type: ignore
    
    stats.add_result(
        "Header/Footer في الألبومات",
        bool(allowed and text and "📸 ألبوم الصور" in text and "🔗 @PhotoChannel" in text),
        "تمت إضافة Header و Footer للألبوم"
    )
    
    cleanup_test_user(test_user_id)

def test_button_parser():
    """1️⃣3️⃣ اختبار تحليل الأزرار"""
    print_section("اختبار تحليل الأزرار / Button Parser Test")
    
    # اختبار 1: تحليل زر رابط بسيط
    button_text = "زيارة الموقع - https://example.com"
    parsed = ButtonParser._parse_single_button(button_text)
    stats.add_result(
        "تحليل زر رابط",
        bool(parsed and parsed['type'] == 'url' and parsed['text'] == 'زيارة الموقع'),
        f"البيانات: {parsed}"
    )
    
    # اختبار 2: تحليل زر مشاركة
    button_text = "شارك - facebook"
    parsed = ButtonParser._parse_single_button(button_text)
    stats.add_result(
        "تحليل زر مشاركة",
        bool(parsed and parsed['type'] == 'share' and parsed['platform'] == 'facebook'),
        f"البيانات: {parsed}"
    )
    
    # اختبار 3: تحليل أزرار متعددة
    buttons_text = """زيارة - https://example.com
شارك - facebook | تويتر - twitter
المساعدة - https://help.example.com"""
    
    parsed_buttons = ButtonParser.parse_buttons_from_text(buttons_text)
    stats.add_result(
        "تحليل أزرار متعددة",
        len(parsed_buttons) == 3 and len(parsed_buttons[1]) == 2,
        f"عدد الصفوف: {len(parsed_buttons)}"
    )
    
    # اختبار 4: إنشاء markup من الأزرار
    buttons = [
        [{'text': 'زيارة', 'type': 'url', 'url': 'https://example.com'}]
    ]
    markup = ButtonParser.buttons_to_markup(buttons)
    stats.add_result(
        "إنشاء Markup من الأزرار",
        markup and len(markup.inline_keyboard) == 1,
        f"عدد الصفوف في الـ markup: {len(markup.inline_keyboard)}"
    )

def test_full_integration():
    """1️⃣4️⃣ اختبار التكامل الكامل"""
    print_section("اختبار التكامل الكامل / Full Integration Test")
    
    test_user_id = 888888
    task_id = 1
    cleanup_test_user(test_user_id)
    
    print("\n🚀 إنشاء مهمة شهاب كاملة...")
    
    # الخطوة 1: تفعيل Premium
    sub_manager = SubscriptionManager(test_user_id)
    sub_manager.activate_subscription('premium', 30)
    print("✅ تم تفعيل Premium")
    
    # الخطوة 2: إنشاء مهمة
    task_manager = UserTaskManager(test_user_id)
    task_id = task_manager.add_task(
        admin_task_id=1,
        admin_task_name="شهاب",
        source_channel={'id': -1001234567890, 'name': 'قناة شهاب'},
        target_channel={'id': -1009876543210, 'name': 'قناة الهدف'}
    )
    print(f"✅ تم إنشاء المهمة #{task_id}")
    
    # الخطوة 3: تفعيل جميع الإعدادات
    settings_manager = TaskSettingsManager(test_user_id, task_id)
    
    # Header & Footer
    settings_manager.update_setting('header', 'enabled', True)
    settings_manager.set_header("📢 قناة شهاب الرسمية", [
        {'type': 'bold', 'offset': 0, 'length': 4}
    ])
    print("✅ تم إضافة Header")
    
    settings_manager.update_setting('footer', 'enabled', True)
    settings_manager.set_footer("🔗 @ShihabChannel", [
        {'type': 'italic', 'offset': 0, 'length': 2}
    ])
    print("✅ تم إضافة Footer")
    
    # Media Filter
    settings_manager.update_setting('media_filters', 'enabled', True)
    settings_manager.set_media_filters(['text', 'photo', 'video'])
    print("✅ تم تفعيل فلتر الوسائط")
    
    # Word Filters
    settings_manager.update_setting('blacklist_words', 'enabled', True)
    settings_manager.add_blacklist_word('سيء')
    settings_manager.add_blacklist_word('محظور')
    print("✅ تم إضافة كلمات محظورة")
    
    settings_manager.update_setting('replacements', 'enabled', True)
    settings_manager.add_replacement('قديم', 'جديد')
    print("✅ تم إضافة استبدالات")
    
    # Link Management
    settings_manager.update_setting('link_management', 'enabled', True)
    settings_manager.update_setting('link_management', 'mode', 'remove')
    print("✅ تم تفعيل إدارة الروابط")
    
    # Language Filter
    settings_manager.update_setting('language_filter', 'enabled', True)
    settings_manager.update_setting('language_filter', 'mode', 'allow')
    settings_manager.update_setting('language_filter', 'languages', ['ar'])
    print("✅ تم تفعيل فلتر اللغة")
    
    # Forwarded Filter
    settings_manager.update_setting('forwarded_filter', 'enabled', True)
    settings_manager.update_setting('forwarded_filter', 'mode', 'block')
    print("✅ تم تفعيل فلتر الرسائل المعاد توجيهها")
    
    # Inline Buttons
    settings_manager.update_setting('inline_buttons', 'enabled', True)
    settings_manager.set_inline_buttons([
        [
            {'text': 'قناة شهاب', 'type': 'url', 'url': 'https://t.me/ShihabChannel'},
            {'text': 'المساعدة', 'type': 'url', 'url': 'https://help.shihab.com'}
        ]
    ])
    print("✅ تم إضافة أزرار مخصصة")
    
    # الخطوة 4: معالجة رسالة اختبارية
    print("\n📨 معالجة رسائل اختبارية...")
    
    processor = MessageProcessor(test_user_id, task_id)
    
    # رسالة 1: نص عربي عادي (يجب أن تمر)
    test_message1 = MockMessage(text="مرحبا بكم في قناة شهاب")
    allowed, text, entities, reason = processor.process_message_text(test_message1)  # type: ignore
    stats.add_result(
        "التكامل - رسالة عربية عادية",
        bool(allowed and text and "📢 قناة شهاب الرسمية" in text and "🔗 @ShihabChannel" in text),
        "تمت إضافة Header و Footer بنجاح"
    )
    
    # رسالة 2: نص مع كلمة محظورة (يجب أن تحظر)
    test_message2 = MockMessage(text="هذا محتوى سيء")
    allowed, text, entities, reason = processor.process_message_text(test_message2)  # type: ignore
    stats.add_result(
        "التكامل - حظر كلمة محظورة",
        not allowed,
        reason
    )
    
    # رسالة 3: نص مع رابط - تعطيل فلتر اللغة مؤقتاً لهذا الاختبار
    settings_manager.update_setting('language_filter', 'enabled', False)
    processor = MessageProcessor(test_user_id, task_id)  # إعادة التحميل
    
    test_message3 = MockMessage(text="مرحبا بكم زوروا https://spam.com للمزيد من المعلومات")
    allowed, text, entities, reason = processor.process_message_text(test_message3)  # type: ignore
    text_preview = text[:50] if text else "None"
    has_no_link = bool(text and 'https://' not in text)
    
    # إعادة تفعيل فلتر اللغة
    settings_manager.update_setting('language_filter', 'enabled', True)
    processor = MessageProcessor(test_user_id, task_id)
    
    stats.add_result(
        "التكامل - إزالة الروابط",
        bool(allowed and has_no_link),
        f"النص النهائي: {text_preview}..."
    )
    
    # رسالة 4: نص إنجليزي (يجب أن يحظر)
    test_message4 = MockMessage(text="This is an English message")
    allowed, text, entities, reason = processor.process_message_text(test_message4)  # type: ignore
    stats.add_result(
        "التكامل - حظر اللغة الإنجليزية",
        not allowed,
        reason
    )
    
    # رسالة 5: رسالة معاد توجيهها (يجب أن تحظر)
    test_message5 = MockMessage(text="رسالة معاد توجيهها", forward_date=datetime.now())
    should_process, reason = processor.should_process_message(test_message5)  # type: ignore
    stats.add_result(
        "التكامل - حظر رسالة معاد توجيهها",
        not should_process,
        reason
    )
    
    # رسالة 6: نص مع استبدال
    test_message6 = MockMessage(text="هذا نص قديم يحتاج تحديث")
    allowed, text, entities, reason = processor.process_message_text(test_message6)  # type: ignore
    text_preview = text if text else "None"
    stats.add_result(
        "التكامل - استبدال الكلمات",
        bool(allowed and text and 'جديد' in text and 'قديم' not in text),
        f"النص بعد الاستبدال: {text_preview}"
    )
    
    # الخطوة 5: طباعة ملخص الإعدادات
    print("\n" + "="*60)
    summary = processor.get_settings_summary()
    print(summary)
    print("="*60)
    
    stats.add_result(
        "التكامل - إنشاء ملخص الإعدادات",
        "⚙️" in summary and "ملخص الإعدادات" in summary,
        "تم إنشاء الملخص بنجاح"
    )
    
    cleanup_test_user(test_user_id)

def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*60)
    print("🧪 بدء الاختبار الشامل / Starting Comprehensive Tests")
    print("="*60)
    print(f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # تشغيل جميع الاختبارات
        test_subscription_system()
        test_task_limits()
        test_media_filters()
        test_word_filters()
        test_link_filters()
        test_language_filters()
        test_forwarded_filter()
        test_header_footer()
        test_message_processing()
        test_duplicate_prevention()
        test_entity_handling()
        test_album_processing()
        test_button_parser()
        test_full_integration()
        
        # طباعة الملخص النهائي
        stats.print_summary()
        
        # طباعة رسالة النجاح أو الفشل
        if stats.failed == 0:
            print("\n🎉 جميع الاختبارات نجحت! / All tests passed!")
        else:
            print(f"\n⚠️ {stats.failed} اختبار فشل / {stats.failed} test(s) failed")
        
    except Exception as e:
        print(f"\n❌ خطأ في تشغيل الاختبارات: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
