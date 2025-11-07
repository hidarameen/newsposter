
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES

logger = logging.getLogger(__name__)
router = Router()

class OtherSettingsStates(StatesGroup):
    waiting_for_language = State()

def check_premium(feature_key, subscription_manager):
    if not subscription_manager.is_premium():
        feature_info = PREMIUM_FEATURES.get(feature_key, {'name': 'هذه الميزة', 'icon': '🔒', 'description': ''})
        icon = feature_info.get('icon', '🔒')
        name = feature_info.get('name', 'هذه الميزة')
        description = feature_info.get('description', '')
        
        msg = f"🔒 <b>{name}</b>\n\n"
        if description:
            msg += f"📝 {description}\n\n"
        msg += "💡 هذه ميزة مدفوعة! للاستفادة منها، يرجى ترقية حسابك."
        
        return False, msg
    return True, ""

# ✅ تم نقل جميع handlers الخاصة بالاستبدالات إلى settings_handlers_replacements.py
# هذا لتجنب التعارض ولضمان حفظ entities بشكل صحيح

@router.callback_query(F.data.startswith("settings_links:"))
async def settings_links(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('link_management', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    link_settings = settings_manager.get_setting('link_management')
    
    enabled = link_settings.get('enabled', False)
    mode = link_settings.get('mode', 'remove')
    
    # تحديد نص الزر بناءً على الوضع الحالي
    if mode == 'remove':
        mode_button_text = "الوضع الحالي: 🗑️ حذف الروابط"
        mode_button_callback = f"toggle_link_mode:{task_id}"
    else:
        mode_button_text = "الوضع الحالي: 🚫 حظر الروابط"
        mode_button_callback = f"toggle_link_mode:{task_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_links:{task_id}")],
        [InlineKeyboardButton(text=mode_button_text, callback_data=mode_button_callback)],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    mode_text = "حذف الروابط فقط" if mode == 'remove' else "حظر الرسائل التي تحتوي على روابط"
    
    await callback.message.edit_text(
        f"🔗 <b>إدارة الروابط</b>\n\n"
        f"الحالة: {status}\n"
        f"الوضع: {mode_text}\n\n"
        f"💡 التحكم في الرسائل التي تحتوي على روابط",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_links:"))
async def toggle_links(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('link_management')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} إدارة الروابط")
    await settings_links(callback)

@router.callback_query(F.data.startswith("toggle_link_mode:"))
async def toggle_link_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    link_settings = settings_manager.get_setting('link_management')
    current_mode = link_settings.get('mode', 'remove')
    
    # تبديل الوضع
    new_mode = 'block' if current_mode == 'remove' else 'remove'
    settings_manager.update_setting('link_management', 'mode', new_mode)
    
    mode_text = "حظر الروابط" if new_mode == 'block' else "حذف الروابط"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_links(callback)

@router.callback_query(F.data.startswith("settings_button_filter:"))
async def settings_button_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('button_filter', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    button_filter = settings_manager.get_setting('button_filter')
    
    enabled = button_filter.get('enabled', False)
    mode = button_filter.get('mode', 'block')
    
    # تحديد نص الزر بناءً على الوضع الحالي
    if mode == 'block':
        mode_button_text = "الوضع الحالي: 🚫 حظر الرسائل"
    else:
        mode_button_text = "الوضع الحالي: 🗑️ حذف الأزرار"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_button_filter:{task_id}")],
        [InlineKeyboardButton(text=mode_button_text, callback_data=f"toggle_button_filter_mode:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    mode_text = "حظر الرسائل" if mode == 'block' else "حذف الأزرار"
    
    await callback.message.edit_text(
        f"🚫 <b>فلتر الأزرار الشفافة</b>\n\n"
        f"الحالة: {status}\n"
        f"الوضع: {mode_text}\n\n"
        f"💡 التحكم في الأزرار الإنلاين في الرسائل",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_button_filter:"))
async def toggle_button_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('button_filter')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} فلتر الأزرار")
    await settings_button_filter(callback)

@router.callback_query(F.data.startswith("toggle_button_filter_mode:"))
async def toggle_button_filter_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    button_filter = settings_manager.get_setting('button_filter')
    current_mode = button_filter.get('mode', 'block')
    
    # تبديل الوضع
    new_mode = 'remove' if current_mode == 'block' else 'block'
    settings_manager.update_setting('button_filter', 'mode', new_mode)
    
    mode_text = "حظر الرسائل" if new_mode == 'block' else "حذف الأزرار"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_button_filter(callback)

@router.callback_query(F.data.startswith("button_filter_"))
async def button_filter_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    task_id = int(parts[3].split(":")[1])
    mode = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('button_filter', 'mode', mode)
    
    mode_text = "حظر الرسائل" if mode == 'block' else "حذف الأزرار"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_button_filter(callback)

@router.callback_query(F.data.startswith("settings_forwarded:"))
async def settings_forwarded(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('forwarded_filter', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    forwarded_filter = settings_manager.get_setting('forwarded_filter')
    
    enabled = forwarded_filter.get('enabled', False)
    mode = forwarded_filter.get('mode', 'allow')
    
    # تحديد نص الزر بناءً على الوضع الحالي
    if mode == 'allow':
        mode_button_text = "الوضع الحالي: ✅ السماح"
    else:
        mode_button_text = "الوضع الحالي: 🚫 الحظر"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_forwarded:{task_id}")],
        [InlineKeyboardButton(text=mode_button_text, callback_data=f"toggle_forwarded_mode:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    mode_text = "السماح بالرسائل الموجهة" if mode == 'allow' else "حظر الرسائل الموجهة"
    
    await callback.message.edit_text(
        f"↪️ <b>فلتر الرسائل الموجهة</b>\n\n"
        f"الحالة: {status}\n"
        f"الوضع: {mode_text}\n\n"
        f"💡 التحكم في الرسائل المعاد توجيهها",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_forwarded:"))
async def toggle_forwarded(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('forwarded_filter')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} فلتر الرسائل الموجهة")
    await settings_forwarded(callback)

@router.callback_query(F.data.startswith("toggle_forwarded_mode:"))
async def toggle_forwarded_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    forwarded_filter = settings_manager.get_setting('forwarded_filter')
    current_mode = forwarded_filter.get('mode', 'allow')
    
    # تبديل الوضع
    new_mode = 'block' if current_mode == 'allow' else 'allow'
    settings_manager.update_setting('forwarded_filter', 'mode', new_mode)
    
    mode_text = "الحظر" if new_mode == 'block' else "السماح"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_forwarded(callback)

@router.callback_query(F.data.startswith("forwarded_mode_"))
async def forwarded_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    task_id = int(parts[3].split(":")[1])
    mode = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('forwarded_filter', 'mode', mode)
    
    mode_text = "السماح" if mode == 'allow' else "الحظر"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_forwarded(callback)

@router.callback_query(F.data.startswith("settings_language:"))
async def settings_language(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('language_filter', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    lang_filter = settings_manager.get_setting('language_filter')
    
    enabled = lang_filter.get('enabled', False)
    mode = lang_filter.get('mode', 'allow')
    languages = lang_filter.get('languages', [])
    sensitivity = lang_filter.get('sensitivity', 'full')
    
    lang_names = {'ar': 'عربي', 'en': 'إنجليزي', 'ru': 'روسي', 'tr': 'تركي', 'fa': 'فارسي'}
    selected_langs = [lang_names.get(l, l) for l in languages]
    
    # تحديد نص الزر بناءً على الوضع الحالي
    if mode == 'allow':
        mode_button_text = "الوضع الحالي: ✅ السماح"
    else:
        mode_button_text = "الوضع الحالي: 🚫 الحظر"
    
    # تحديد نص زر الحساسية
    if sensitivity == 'full':
        sensitivity_button_text = "الحساسية: 📊 كامل"
    else:
        sensitivity_button_text = "الحساسية: 📊 جزئي"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_language:{task_id}")],
        [InlineKeyboardButton(text=mode_button_text, callback_data=f"toggle_lang_mode:{task_id}")],
        [InlineKeyboardButton(text="🌐 اختيار اللغات", callback_data=f"select_languages:{task_id}")],
        [InlineKeyboardButton(text=sensitivity_button_text, callback_data=f"toggle_lang_sensitivity:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    mode_text = "السماح" if mode == 'allow' else "الحظر"
    sens_text = "كامل" if sensitivity == 'full' else "جزئي"
    langs_text = ", ".join(selected_langs) if selected_langs else "لم يتم تحديد"
    
    await callback.message.edit_text(
        f"🌐 <b>فلتر اللغة</b>\n\n"
        f"الحالة: {status}\n"
        f"الوضع: {mode_text}\n"
        f"الحساسية: {sens_text}\n"
        f"اللغات: {langs_text}\n\n"
        f"💡 تصفية الرسائل حسب اللغة",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_language:"))
async def toggle_language(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('language_filter')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} فلتر اللغة")
    await settings_language(callback)

@router.callback_query(F.data.startswith("select_languages:"))
async def select_languages(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    current_langs = settings_manager.get_setting('language_filter', 'languages')
    
    languages = [
        ('ar', '🇸🇦 عربي'),
        ('en', '🇬🇧 إنجليزي'),
        ('ru', '🇷🇺 روسي'),
        ('tr', '🇹🇷 تركي'),
        ('fa', '🇮🇷 فارسي'),
        ('de', '🇩🇪 ألماني'),
        ('fr', '🇫🇷 فرنسي'),
        ('es', '🇪🇸 إسباني')
    ]
    
    keyboard_buttons = []
    for i in range(0, len(languages), 2):
        row = []
        for j in range(2):
            if i + j < len(languages):
                lang_code, lang_name = languages[i + j]
                icon = "✅" if lang_code in current_langs else "❌"
                row.append(InlineKeyboardButton(
                    text=f"{icon} {lang_name}",
                    callback_data=f"toggle_lang:{task_id}:{lang_code}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_language:{task_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        "🌐 <b>اختيار اللغات</b>\n\n"
        "اختر اللغات للفلتر:",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_lang:"))
async def toggle_lang(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    task_id = int(parts[1])
    lang_code = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    current_langs = settings_manager.get_setting('language_filter', 'languages')
    
    if lang_code in current_langs:
        current_langs.remove(lang_code)
    else:
        current_langs.append(lang_code)
    
    settings_manager.update_setting('language_filter', 'languages', current_langs)
    
    await callback.answer()
    await select_languages(callback)

@router.callback_query(F.data.startswith("toggle_lang_sensitivity:"))
async def toggle_lang_sensitivity(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    lang_filter = settings_manager.get_setting('language_filter')
    current_sensitivity = lang_filter.get('sensitivity', 'full')
    
    # تبديل الحساسية
    new_sensitivity = 'partial' if current_sensitivity == 'full' else 'full'
    settings_manager.update_setting('language_filter', 'sensitivity', new_sensitivity)
    
    sens_text = "كامل" if new_sensitivity == 'full' else "جزئي"
    await callback.answer(f"✅ تم تغيير الحساسية إلى: {sens_text}")
    await settings_language(callback)

@router.callback_query(F.data.startswith("toggle_lang_mode:"))
async def toggle_lang_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    lang_filter = settings_manager.get_setting('language_filter')
    current_mode = lang_filter.get('mode', 'allow')
    
    # تبديل الوضع
    new_mode = 'block' if current_mode == 'allow' else 'allow'
    settings_manager.update_setting('language_filter', 'mode', new_mode)
    
    mode_text = "الحظر" if new_mode == 'block' else "السماح"
    await callback.answer(f"✅ تم تغيير الوضع إلى: {mode_text}")
    await settings_language(callback)

@router.callback_query(F.data.startswith("lang_mode_"))
async def lang_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    task_id = int(parts[3].split(":")[1])
    mode = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('language_filter', 'mode', mode)
    
    await callback.answer(f"✅ تم تغيير الوضع")
    await settings_language(callback)

@router.callback_query(F.data.startswith("lang_sens_"))
async def lang_sens(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    task_id = int(parts[3].split(":")[1])
    sensitivity = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('language_filter', 'sensitivity', sensitivity)
    
    await callback.answer(f"✅ تم تغيير الحساسية")
    await settings_language(callback)

@router.callback_query(F.data.startswith("cancel_input:"))
async def cancel_input(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    await state.clear()
    await callback.answer("تم الإلغاء")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"task_settings:{task_id}")]
    ])
    
    await callback.message.edit_text("تم إلغاء العملية", reply_markup=keyboard)
