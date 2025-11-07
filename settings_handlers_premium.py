import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager
from timezone_manager import TimezoneManager
from day_filter import DayFilter
from hour_filter import HourFilter
from character_limit_filter import CharacterLimitFilter
from translation_handler import TranslationHandler
from task_statistics_manager import TaskStatistics

logger = logging.getLogger(__name__)
router = Router()

class PremiumSettingsStates(StatesGroup):
    waiting_for_timezone = State()
    waiting_for_char_limit_value = State()
    waiting_for_auto_delete_time = State()
    waiting_for_pin_notification_delay = State()

def check_premium(user_id: int) -> tuple[bool, str, InlineKeyboardMarkup]:
    """التحقق من الاشتراك المدفوع"""
    sub_manager = SubscriptionManager(user_id)
    if not sub_manager.is_premium():
        return False, "🔒 <b>ميزة مدفوعة</b>\n\n💡 هذه ميزة مدفوعة! للاستفادة منها، يرجى ترقية حسابك.", None
    return True, "", None

@router.callback_query(F.data.startswith("settings_auto_pin:"))
async def settings_auto_pin(callback: CallbackQuery, state: FSMContext):
    """إعدادات التثبيت التلقائي"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    auto_pin = settings.get('auto_pin', {})

    enabled = auto_pin.get('enabled', False)
    disable_notification = auto_pin.get('disable_notification', True)
    delete_notification_after = auto_pin.get('delete_notification_after', 5)

    text = "📌 <b>التثبيت التلقائي</b>\n\n"
    text += "يثبت الرسائل الجديدة في القناة الهدف تلقائياً بعد النشر.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        text += f"تعطيل الإشعار: {'نعم' if disable_notification else 'لا'}\n"
        text += f"حذف إشعار التثبيت بعد: {delete_notification_after} ثانية\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_auto_pin:{task_id}")])

    if enabled:
        notif_text = "🔕 تعطيل إشعار التثبيت" if not disable_notification else "🔔 تفعيل إشعار التثبيت"
        keyboard.append([InlineKeyboardButton(text=notif_text, callback_data=f"toggle_pin_notification:{task_id}")])
        keyboard.append([InlineKeyboardButton(text="⏱️ تعيين وقت حذف الإشعار", callback_data=f"set_pin_notification_delay:{task_id}")])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_auto_pin:"))
async def toggle_auto_pin(callback: CallbackQuery):
    """تبديل حالة التثبيت التلقائي"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('auto_pin')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} التثبيت التلقائي")
    await settings_auto_pin(callback, None)

@router.callback_query(F.data.startswith("toggle_pin_notification:"))
async def toggle_pin_notification(callback: CallbackQuery):
    """تبديل حالة إشعار التثبيت"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    auto_pin = settings.get('auto_pin', {})

    current_state = auto_pin.get('disable_notification', True)
    new_state = not current_state

    settings_manager.update_setting('auto_pin', 'disable_notification', new_state)

    status = "تعطيل" if new_state else "تفعيل"
    await callback.answer(f"✅ تم {status} إشعار التثبيت")
    await settings_auto_pin(callback, None)

@router.callback_query(F.data.startswith("set_pin_notification_delay:"))
async def set_pin_notification_delay(callback: CallbackQuery, state: FSMContext):
    """تعيين وقت حذف إشعار التثبيت"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id)
    await state.set_state(PremiumSettingsStates.waiting_for_pin_notification_delay)

    await callback.message.edit_text(
        "⏱️ <b>تعيين وقت حذف إشعار التثبيت</b>\n\n"
        "أرسل عدد الثواني:\n\n"
        "مثال: 5 (سيتم حذف الإشعار بعد 5 ثواني)",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_auto_pin:{task_id}")]
        ])
    )

@router.message(PremiumSettingsStates.waiting_for_pin_notification_delay)
async def process_pin_notification_delay(message: Message, state: FSMContext):
    """معالجة وقت حذف إشعار التثبيت"""
    user_id = message.from_user.id
    data = await state.get_data()
    task_id = data.get('task_id')

    try:
        value = int(message.text.strip())

        if value < 0:
            await message.answer("❌ القيمة يجب ألا تكون سالبة!")
            return

        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.update_setting('auto_pin', 'delete_notification_after', value)

        await state.clear()
        await message.answer(
            f"✅ تم تعيين وقت الحذف: {value} ثانية",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_auto_pin:{task_id}")]
            ])
        )

    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح!")

@router.callback_query(F.data.startswith("toggle_pin_notification:"))
async def toggle_pin_notification(callback: CallbackQuery):
    """تبديل حالة إشعار التثبيت"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    auto_pin = settings.get('auto_pin', {})

    current_state = auto_pin.get('disable_notification', True)
    new_state = not current_state

    settings_manager.update_setting('auto_pin', 'disable_notification', new_state)

    status = "تعطيل" if new_state else "تفعيل"
    await callback.answer(f"✅ تم {status} إشعار التثبيت")
    await settings_auto_pin(callback, None)

@router.callback_query(F.data.startswith("set_pin_notification_delay:"))
async def set_pin_notification_delay(callback: CallbackQuery, state: FSMContext):
    """تعيين وقت حذف إشعار التثبيت"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id)
    await state.set_state(PremiumSettingsStates.waiting_for_pin_notification_delay)

    await callback.message.edit_text(
        "⏱️ <b>تعيين وقت حذف إشعار التثبيت</b>\n\n"
        "أرسل عدد الثواني:\n\n"
        "مثال: 5 (سيتم حذف الإشعار بعد 5 ثواني)",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_auto_pin:{task_id}")]
        ])
    )

@router.message(PremiumSettingsStates.waiting_for_pin_notification_delay)
async def process_pin_notification_delay(message: Message, state: FSMContext):
    """معالجة وقت حذف إشعار التثبيت"""
    user_id = message.from_user.id
    data = await state.get_data()
    task_id = data.get('task_id')

    try:
        value = int(message.text.strip())

        if value < 0:
            await message.answer("❌ القيمة يجب ألا تكون سالبة!")
            return

        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.update_setting('auto_pin', 'delete_notification_after', value)

        await state.clear()
        await message.answer(
            f"✅ تم تعيين وقت الحذف: {value} ثانية",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_auto_pin:{task_id}")]
            ])
        )

    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح!")

@router.callback_query(F.data.startswith("settings_link_preview:"))
async def settings_link_preview(callback: CallbackQuery):
    """إعدادات معاينة الروابط"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    link_preview = settings.get('link_preview', {})

    enabled = link_preview.get('enabled', False)
    mode = link_preview.get('mode', 'show')

    text = "🔗 <b>معاينة الروابط</b>\n\n"
    text += "التحكم في عرض أو إخفاء معاينة الروابط داخل المنشورات.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        from link_preview_manager import LinkPreviewManager
        text += f"الوضع: {LinkPreviewManager.get_mode_description(mode)}\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_link_preview:{task_id}")])

    if enabled:
        keyboard.append([
            InlineKeyboardButton(
                text="✅ إظهار" if mode == 'show' else "⚪ إظهار",
                callback_data=f"set_link_preview_mode:{task_id}:show"
            ),
            InlineKeyboardButton(
                text="❌ إخفاء" if mode == 'hide' else "⚪ إخفاء",
                callback_data=f"set_link_preview_mode:{task_id}:hide"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_link_preview:"))
async def toggle_link_preview(callback: CallbackQuery):
    """تبديل حالة معاينة الروابط"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('link_preview')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} معاينة الروابط")
    await settings_link_preview(callback)

@router.callback_query(F.data.startswith("set_link_preview_mode:"))
async def set_link_preview_mode(callback: CallbackQuery):
    """تعيين وضع معاينة الروابط"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    mode = parts[2]
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('link_preview', 'mode', mode)

    await callback.answer(f"تم تعيين الوضع: {mode}")
    await settings_link_preview(callback)

@router.callback_query(F.data.startswith("settings_reply_preservation:"))
async def settings_reply_preservation(callback: CallbackQuery):
    """إعدادات الحفاظ على الردود"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    reply_preservation = settings.get('reply_preservation', {})

    enabled = reply_preservation.get('enabled', False)

    text = "💬 <b>الحفاظ على الردود</b>\n\n"
    text += "يحافظ على تسلسل الردود إذا كانت الرسالة ردًا على منشور سابق.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_reply_preservation:{task_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_reply_preservation:"))
async def toggle_reply_preservation(callback: CallbackQuery):
    """تبديل حالة الحفاظ على الردود"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('reply_preservation')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} الحفاظ على الردود")
    await settings_reply_preservation(callback)

@router.callback_query(F.data.startswith("settings_auto_delete:"))
async def settings_auto_delete(callback: CallbackQuery):
    """إعدادات الحذف التلقائي"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    auto_delete = settings.get('auto_delete', {})

    enabled = auto_delete.get('enabled', False)
    delay_value = auto_delete.get('delay_value', 60)
    delay_unit = auto_delete.get('delay_unit', 'minutes')

    unit_names = {
        'seconds': 'ثانية',
        'minutes': 'دقيقة',
        'hours': 'ساعة',
        'days': 'يوم'
    }

    text = "🗑️ <b>الحذف التلقائي</b>\n\n"
    text += "يحذف الرسائل في القناة الهدف بعد وقت محدد من النشر.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        text += f"الوقت: {delay_value} {unit_names.get(delay_unit, delay_unit)}\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_auto_delete:{task_id}")])

    if enabled:
        keyboard.append([InlineKeyboardButton(text="⏱️ تعيين الوقت", callback_data=f"set_auto_delete_time:{task_id}")])
        keyboard.append([
            InlineKeyboardButton(
                text=f"{'✅' if delay_unit == 'seconds' else '⚪'} ثواني",
                callback_data=f"set_auto_delete_unit:{task_id}:seconds"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if delay_unit == 'minutes' else '⚪'} دقائق",
                callback_data=f"set_auto_delete_unit:{task_id}:minutes"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text=f"{'✅' if delay_unit == 'hours' else '⚪'} ساعات",
                callback_data=f"set_auto_delete_unit:{task_id}:hours"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if delay_unit == 'days' else '⚪'} أيام",
                callback_data=f"set_auto_delete_unit:{task_id}:days"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_auto_delete:"))
async def toggle_auto_delete(callback: CallbackQuery):
    """تبديل حالة الحذف التلقائي"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('auto_delete')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} الحذف التلقائي")
    await settings_auto_delete(callback)

@router.callback_query(F.data.startswith("settings_day_filter:"))
async def settings_day_filter(callback: CallbackQuery):
    """إعدادات فلتر الأيام"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    day_filter = settings.get('day_filter', {})

    enabled = day_filter.get('enabled', False)
    mode = day_filter.get('mode', 'allow')
    days = day_filter.get('days', [])

    text = "📅 <b>فلتر الأيام</b>\n\n"
    text += "تحديد أيام النشر المسموح بها أو المحظورة.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        text += f"الوضع: {DayFilter.get_mode_description(mode)}\n"
        if days:
            day_names = [DayFilter.DAYS_AR.get(d, str(d)) for d in days]
            text += f"الأيام: {', '.join(day_names)}\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_day_filter:{task_id}")])

    if enabled:
        # زر واحد للتبديل بين السماح والحظر
        mode_text = "✅ السماح" if mode == 'allow' else "🚫 الحظر"
        keyboard.append([
            InlineKeyboardButton(
                text=f"الوضع الحالي: {mode_text}",
                callback_data=f"toggle_day_filter_mode:{task_id}"
            )
        ])

        # أزرار الأيام
        for i in range(0, 7, 2):
            row = []
            for j in range(2):
                if i + j < 7:
                    day = i + j
                    day_name = DayFilter.DAYS_AR[day]
                    icon = "✅" if day in days else "⚪"
                    row.append(InlineKeyboardButton(
                        text=f"{icon} {day_name}",
                        callback_data=f"toggle_day:{task_id}:{day}"
                    ))
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("set_auto_delete_time:"))
async def set_auto_delete_time(callback: CallbackQuery, state: FSMContext):
    """تعيين وقت الحذف التلقائي"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id)
    await state.set_state(PremiumSettingsStates.waiting_for_auto_delete_time)

    await callback.message.edit_text(
        "⏱️ <b>تعيين وقت الحذف التلقائي</b>\n\n"
        "أرسل عدد الوحدات الزمنية:\n\n"
        "مثال: 5 (سيتم الحذف بعد 5 من الوحدة المختارة)",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_auto_delete:{task_id}")]
        ])
    )

@router.message(PremiumSettingsStates.waiting_for_auto_delete_time)
async def process_auto_delete_time(message: Message, state: FSMContext):
    """معالجة وقت الحذف التلقائي"""
    user_id = message.from_user.id
    data = await state.get_data()
    task_id = data.get('task_id')

    try:
        value = int(message.text.strip())

        if value <= 0:
            await message.answer("❌ القيمة يجب أن تكون أكبر من صفر!")
            return

        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.update_setting('auto_delete', 'delay_value', value)

        await state.clear()
        await message.answer(
            f"✅ تم تعيين الوقت: {value} ثانية",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_auto_delete:{task_id}")]
            ])
        )

    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح!")

@router.callback_query(F.data.startswith("set_auto_delete_unit:"))
async def set_auto_delete_unit(callback: CallbackQuery):
    """تعيين وحدة الوقت للحذف التلقائي"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    unit = parts[2]
    user_id = callback.from_user.id

    unit_names = {
        'seconds': 'ثانية',
        'minutes': 'دقيقة',
        'hours': 'ساعة',
        'days': 'يوم'
    }

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('auto_delete', 'delay_unit', unit)

    await callback.answer(f"✅ تم تعيين الوحدة: {unit_names.get(unit, unit)}")
    await settings_auto_delete(callback)

@router.callback_query(F.data.startswith("toggle_day_filter:"))
async def toggle_day_filter(callback: CallbackQuery):
    """تبديل حالة فلتر الأيام"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('day_filter')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} فلتر الأيام")
    await settings_day_filter(callback)


@router.callback_query(F.data.startswith("toggle_day_filter_mode:"))
async def toggle_day_filter_mode(callback: CallbackQuery):
    """تبديل وضع فلتر الأيام بين السماح والحظر"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    day_filter = settings.get('day_filter', {})

    current_mode = day_filter.get('mode', 'allow')
    new_mode = 'block' if current_mode == 'allow' else 'allow'

    settings_manager.update_setting('day_filter', 'mode', new_mode)

    mode_text = "السماح" if new_mode == 'allow' else "الحظر"
    await callback.answer(f"✅ تم التبديل إلى وضع: {mode_text}")
    await settings_day_filter(callback)


@router.callback_query(F.data.startswith("change_source_lang:"))
async def change_source_lang(callback: CallbackQuery):
    """تغيير اللغة المصدر"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    from translation_handler import TranslationHandler

    keyboard = []
    common_langs = TranslationHandler.get_common_languages()

    # إضافة خيار الكشف التلقائي
    keyboard.append([InlineKeyboardButton(
        text="🔍 كشف تلقائي",
        callback_data=f"set_source_lang:{task_id}:auto"
    )])

    # إضافة اللغات الشائعة
    lang_buttons = []
    for code, name in list(common_langs.items())[:10]:
        lang_buttons.append(InlineKeyboardButton(
            text=name,
            callback_data=f"set_source_lang:{task_id}:{code}"
        ))
        if len(lang_buttons) == 2:
            keyboard.append(lang_buttons)
            lang_buttons = []

    if lang_buttons:
        keyboard.append(lang_buttons)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_translation:{task_id}")])

    await callback.message.edit_text(
        "🌐 <b>اختر اللغة المصدر</b>\n\n"
        "اختر اللغة التي تريد الترجمة منها:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("change_target_lang:"))
async def change_target_lang(callback: CallbackQuery):
    """تغيير اللغة الهدف"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    from translation_handler import TranslationHandler

    keyboard = []
    common_langs = TranslationHandler.get_common_languages()

    # إضافة اللغات الشائعة
    lang_buttons = []
    for code, name in list(common_langs.items())[:12]:
        lang_buttons.append(InlineKeyboardButton(
            text=name,
            callback_data=f"set_target_lang:{task_id}:{code}"
        ))
        if len(lang_buttons) == 2:
            keyboard.append(lang_buttons)
            lang_buttons = []

    if lang_buttons:
        keyboard.append(lang_buttons)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_translation:{task_id}")])

    await callback.message.edit_text(
        "🎯 <b>اختر اللغة الهدف</b>\n\n"
        "اختر اللغة التي تريد الترجمة إليها:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("set_source_lang:"))
async def set_source_lang(callback: CallbackQuery):
    """تعيين اللغة المصدر"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    lang_code = parts[2]
    user_id = callback.from_user.id

    from translation_handler import TranslationHandler

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('translation', 'source_lang', lang_code)

    lang_name = TranslationHandler.get_language_name(lang_code)
    await callback.answer(f"✅ تم تعيين اللغة المصدر: {lang_name}")
    await settings_translation(callback)

@router.callback_query(F.data.startswith("set_target_lang:"))
async def set_target_lang(callback: CallbackQuery):
    """تعيين اللغة الهدف"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    lang_code = parts[2]
    user_id = callback.from_user.id

    from translation_handler import TranslationHandler

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('translation', 'target_lang', lang_code)

    lang_name = TranslationHandler.get_language_name(lang_code)
    await callback.answer(f"✅ تم تعيين اللغة الهدف: {lang_name}")
    await settings_translation(callback)


@router.callback_query(F.data.startswith("toggle_day:"))
async def toggle_day(callback: CallbackQuery):
    """تبديل يوم محدد"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    day = int(parts[2])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    day_filter = settings.get('day_filter', {})

    DayFilter.toggle_day(day_filter, day)
    settings_manager.update_setting('day_filter', 'days', day_filter['days'])

    await callback.answer()
    await settings_day_filter(callback)

@router.callback_query(F.data.startswith("settings_task_stats:"))
async def settings_task_stats(callback: CallbackQuery):
    """عرض إحصائيات المهمة"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    stats = TaskStatistics(user_id, task_id)
    text = stats.get_formatted_summary()

    keyboard = [
        [InlineKeyboardButton(text="🔄 تحديث", callback_data=f"settings_task_stats:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ]

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("settings_hour_filter:"))
async def settings_hour_filter(callback: CallbackQuery):
    """إعدادات فلتر الساعات"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    hour_filter = settings.get('hour_filter', {})

    enabled = hour_filter.get('enabled', False)
    mode = hour_filter.get('mode', 'allow')
    hours = hour_filter.get('hours', [])

    text = "🕒 <b>فلتر الساعات</b>\n\n"
    text += "تحديد ساعات النشر المسموح بها أو المحظورة.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        text += f"الوضع: {HourFilter.get_mode_description(mode)}\n"
        if hours:
            sorted_hours = sorted(hours)
            hour_texts = [f"{h}:00" for h in sorted_hours]
            text += f"الساعات المحددة: {', '.join(hour_texts)}\n"

    keyboard = []

    # زر التفعيل/التعطيل
    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_hour_filter:{task_id}")])

    if enabled:
        # الحصول على timezone المستخدم
        tz_manager = TimezoneManager(user_id)
        current_tz = tz_manager.get_timezone()
        tz_display = TimezoneManager.COMMON_TIMEZONES.get(current_tz, current_tz)
        
        text += f"⏰ المنطقة الزمنية: {tz_display}\n"
        
        # زر تغيير المنطقة الزمنية
        keyboard.append([InlineKeyboardButton(text="⏰ تغيير المنطقة الزمنية", callback_data=f"settings_timezone:{task_id}")])
        
        # زر واحد للتبديل بين السماح والحظر
        mode_text = "✅ السماح" if mode == 'allow' else "🚫 الحظر"
        keyboard.append([
            InlineKeyboardButton(
                text=f"الوضع الحالي: {mode_text}",
                callback_data=f"toggle_hour_filter_mode:{task_id}"
            )
        ])
        
        # أزرار تفعيل الكل / تعطيل الكل
        keyboard.append([
            InlineKeyboardButton(text="✅ تفعيل الكل", callback_data=f"enable_all_hours:{task_id}"),
            InlineKeyboardButton(text="❌ تعطيل الكل", callback_data=f"disable_all_hours:{task_id}")
        ])

        # لوحة أزرار اختيار الساعات (0-23) - 6 ساعات في كل صف
        for i in range(0, 24, 6):
            row = []
            for j in range(6):
                if i + j < 24:
                    hour = i + j
                    icon = "✅" if hour in hours else "⚪"
                    row.append(InlineKeyboardButton(
                        text=f"{icon} {hour}",
                        callback_data=f"toggle_hour:{task_id}:{hour}"
                    ))
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_hour_filter:"))
async def toggle_hour_filter(callback: CallbackQuery):
    """تبديل حالة فلتر الساعات"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('hour_filter')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} فلتر الساعات")
    await settings_hour_filter(callback)

@router.callback_query(F.data.startswith("toggle_hour_filter_mode:"))
async def toggle_hour_filter_mode(callback: CallbackQuery):
    """تبديل وضع فلتر الساعات بين السماح والحظر"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    hour_filter = settings.get('hour_filter', {})

    current_mode = hour_filter.get('mode', 'allow')
    new_mode = 'block' if current_mode == 'allow' else 'allow'

    settings_manager.update_setting('hour_filter', 'mode', new_mode)

    mode_text = "السماح" if new_mode == 'allow' else "الحظر"
    await callback.answer(f"✅ تم التبديل إلى وضع: {mode_text}")
    await settings_hour_filter(callback)

@router.callback_query(F.data.startswith("toggle_hour:"))
async def toggle_hour(callback: CallbackQuery):
    """تبديل ساعة محددة"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    hour = int(parts[2])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    hour_filter = settings.get('hour_filter', {})

    HourFilter.toggle_hour(hour_filter, hour)
    settings_manager.update_setting('hour_filter', 'hours', hour_filter['hours'])

    await callback.answer()
    await settings_hour_filter(callback)

@router.callback_query(F.data.startswith("enable_all_hours:"))
async def enable_all_hours(callback: CallbackQuery):
    """تفعيل جميع الساعات"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    all_hours = list(range(24))
    settings_manager.update_setting('hour_filter', 'hours', all_hours)

    await callback.answer("✅ تم تفعيل جميع الساعات")
    await settings_hour_filter(callback)

@router.callback_query(F.data.startswith("disable_all_hours:"))
async def disable_all_hours(callback: CallbackQuery):
    """تعطيل جميع الساعات"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('hour_filter', 'hours', [])

    await callback.answer("❌ تم تعطيل جميع الساعات")
    await settings_hour_filter(callback)

@router.callback_query(F.data.startswith("settings_translation:"))
async def settings_translation(callback: CallbackQuery):
    """إعدادات الترجمة"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    translation = settings.get('translation', {})

    enabled = translation.get('enabled', False)
    source_lang = translation.get('source_lang', 'auto')
    target_lang = translation.get('target_lang', 'ar')

    text = "🌍 <b>ترجمة النصوص</b>\n\n"
    text += "ترجمة النصوص من لغة إلى أخرى أو من جميع اللغات إلى لغة محددة.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        source_name = TranslationHandler.get_language_name(source_lang)
        target_name = TranslationHandler.get_language_name(target_lang)
        text += f"من: {source_name}\n"
        text += f"إلى: {target_name}\n"

    keyboard = []

    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_translation:{task_id}")])

    if enabled:
        keyboard.append([InlineKeyboardButton(text="🌐 تغيير اللغة المصدر", callback_data=f"change_source_lang:{task_id}")])
        keyboard.append([InlineKeyboardButton(text="🎯 تغيير اللغة الهدف", callback_data=f"change_target_lang:{task_id}")])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("set_min_chars:"))
async def set_min_chars(callback: CallbackQuery, state: FSMContext):
    """تعيين الحد الأدنى للأحرف"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id, setting_type='min_chars')
    await state.set_state(PremiumSettingsStates.waiting_for_char_limit_value)

    await callback.message.edit_text(
        "📏 <b>تعيين الحد الأدنى للأحرف</b>\n\n"
        "أرسل عدد الأحرف المطلوب:\n\n"
        "أو اضغط إلغاء للعودة.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_character_limit:{task_id}")]
        ])
    )

@router.callback_query(F.data.startswith("set_max_chars:"))
async def set_max_chars(callback: CallbackQuery, state: FSMContext):
    """تعيين الحد الأقصى للأحرف"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id, setting_type='max_chars')
    await state.set_state(PremiumSettingsStates.waiting_for_char_limit_value)

    await callback.message.edit_text(
        "📏 <b>تعيين الحد الأقصى للأحرف</b>\n\n"
        "أرسل عدد الأحرف المطلوب:\n\n"
        "أو اضغط إلغاء للعودة.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_character_limit:{task_id}")]
        ])
    )

@router.message(PremiumSettingsStates.waiting_for_char_limit_value)
async def process_char_limit_value(message: Message, state: FSMContext):
    """معالجة قيمة حد الأحرف"""
    user_id = message.from_user.id
    data = await state.get_data()
    task_id = data.get('task_id')
    setting_type = data.get('setting_type')

    try:
        # إذا كان النوع range، نتوقع صيغة "min-max"
        if setting_type == 'range':
            parts = message.text.strip().split('-')
            if len(parts) != 2:
                await message.answer("❌ صيغة خاطئة! استخدم: الحد_الأدنى-الحد_الأقصى (مثل: 5-120)")
                return

            min_value = int(parts[0].strip())
            max_value = int(parts[1].strip())

            if min_value <= 0 or max_value <= 0:
                await message.answer("❌ القيم يجب أن تكون أكبر من صفر!")
                return

            if min_value >= max_value:
                await message.answer("❌ الحد الأدنى يجب أن يكون أقل من الحد الأقصى!")
                return

            if max_value > 4096:
                await message.answer("❌ الحد الأقصى يجب ألا يتجاوز 4096 حرف!")
                return

            settings_manager = TaskSettingsManager(user_id, task_id)
            settings_manager.update_setting('character_limit', 'min_chars', min_value)
            settings_manager.update_setting('character_limit', 'max_chars', max_value)

            await state.clear()
            await message.answer(
                f"✅ تم تعيين النطاق: {min_value} - {max_value} حرف",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_character_limit:{task_id}")]
                ])
            )
        else:
            # للحد الأدنى أو الأقصى فقط
            value = int(message.text.strip())

            if value <= 0:
                await message.answer("❌ القيمة يجب أن تكون أكبر من صفر!")
                return

            if value > 4096:
                await message.answer("❌ القيمة يجب ألا تتجاوز 4096 حرف!")
                return

            settings_manager = TaskSettingsManager(user_id, task_id)
            settings_manager.update_setting('character_limit', setting_type, value)

            await state.clear()

            label = "الحد الأدنى" if setting_type == 'min_chars' else "الحد الأقصى"
            await message.answer(
                f"✅ تم تعيين {label}: {value} حرف",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_character_limit:{task_id}")]
                ])
            )

    except ValueError:
        await message.answer("❌ يرجى إدخال أرقام صحيحة!")


    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_translation:{task_id}")])

    if enabled:
        keyboard.append([InlineKeyboardButton(text="🌐 تغيير اللغة المصدر", callback_data=f"change_source_lang:{task_id}")])
        keyboard.append([InlineKeyboardButton(text="🎯 تغيير اللغة الهدف", callback_data=f"change_target_lang:{task_id}")])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_translation:"))
async def toggle_translation(callback: CallbackQuery):
    """تبديل حالة الترجمة"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('translation')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} الترجمة")
    await settings_translation(callback)

@router.callback_query(F.data.startswith("settings_character_limit:"))
async def settings_character_limit(callback: CallbackQuery):
    """إعدادات فلتر حدود الأحرف"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    is_premium, error_msg, _ = check_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
        )
        return

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    char_limit = settings.get('character_limit', {})

    enabled = char_limit.get('enabled', False)
    mode = char_limit.get('mode', 'max')
    min_chars = char_limit.get('min_chars', 10)
    max_chars = char_limit.get('max_chars', 1000)

    text = "📏 <b>فلتر حدود الأحرف</b>\n\n"
    text += "نشر أو حظر الرسائل بناءً على عدد الأحرف.\n\n"
    text += f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}\n"

    if enabled:
        mode_descriptions = {
            'min': f"📏 حد أدنى فقط ({min_chars} حرف)",
            'max': f"📏 حد أقصى فقط ({max_chars} حرف)",
            'range': f"📏 نطاق محدد ({min_chars} - {max_chars} حرف)"
        }
        text += f"الوضع: {mode_descriptions.get(mode, mode)}\n"

    keyboard = []

    # زر التفعيل/التعطيل
    toggle_text = "🔴 تعطيل" if enabled else "🟢 تفعيل"
    keyboard.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_character_limit:{task_id}")])

    if enabled:
        # زر الوضع الحالي للتبديل بين الأوضاع
        mode_names = {
            'min': 'حد أدنى فقط',
            'max': 'حد أقصى فقط',
            'range': 'نطاق محدد'
        }
        keyboard.append([
            InlineKeyboardButton(
                text=f"الوضع الحالي: {mode_names.get(mode, mode)}",
                callback_data=f"toggle_char_limit_mode:{task_id}"
            )
        ])

        # أزرار التعيين حسب الوضع
        if mode == 'min':
            keyboard.append([InlineKeyboardButton(text="📝 تعيين الحد الأدنى", callback_data=f"set_min_chars:{task_id}")])
        elif mode == 'max':
            keyboard.append([InlineKeyboardButton(text="📝 تعيين الحد الأقصى", callback_data=f"set_max_chars:{task_id}")])
        elif mode == 'range':
            keyboard.append([InlineKeyboardButton(text="📝 إدخال النطاق", callback_data=f"set_char_range:{task_id}")])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_character_limit:"))
async def toggle_character_limit(callback: CallbackQuery):
    """تبديل حالة فلتر حدود الأحرف"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    new_state = settings_manager.toggle_feature('character_limit')

    await callback.answer(f"{'تم تفعيل' if new_state else 'تم تعطيل'} فلتر حدود الأحرف")
    await settings_character_limit(callback)

@router.callback_query(F.data.startswith("toggle_char_limit_mode:"))
async def toggle_char_limit_mode(callback: CallbackQuery):
    """التبديل بين أوضاع فلتر حدود الأحرف"""
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    char_limit = settings.get('character_limit', {})

    current_mode = char_limit.get('mode', 'max')

    # التبديل بين الأوضاع: max -> min -> range -> max
    mode_cycle = {'max': 'min', 'min': 'range', 'range': 'max'}
    new_mode = mode_cycle.get(current_mode, 'max')

    settings_manager.update_setting('character_limit', 'mode', new_mode)

    mode_names = {
        'min': 'حد أدنى فقط',
        'max': 'حد أقصى فقط',
        'range': 'نطاق محدد'
    }
    await callback.answer(f"✅ تم التبديل إلى: {mode_names.get(new_mode, new_mode)}")
    await settings_character_limit(callback)

@router.callback_query(F.data.startswith("set_char_range:"))
async def set_char_range(callback: CallbackQuery, state: FSMContext):
    """تعيين نطاق الأحرف"""
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id, setting_type='range')
    await state.set_state(PremiumSettingsStates.waiting_for_char_limit_value)

    await callback.message.edit_text(
        "📏 <b>تعيين نطاق الأحرف</b>\n\n"
        "أرسل النطاق بالصيغة التالية:\n"
        "<code>الحد_الأدنى-الحد_الأقصى</code>\n\n"
        "مثال: <code>5-120</code> (من 5 إلى 120 حرف)\n\n"
        "أو اضغط إلغاء للعودة.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"settings_character_limit:{task_id}")]
        ])
    )

@router.callback_query(F.data.startswith("settings_timezone:"))
async def settings_timezone(callback: CallbackQuery):
    """عرض قائمة المناطق الزمنية المتاحة"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    tz_manager = TimezoneManager(user_id)
    current_tz = tz_manager.get_timezone()
    
    text = "⏰ <b>اختر المنطقة الزمنية</b>\n\n"
    text += f"المنطقة الحالية: {TimezoneManager.COMMON_TIMEZONES.get(current_tz, current_tz)}\n\n"
    text += "اختر المنطقة الزمنية المناسبة لموقعك:"
    
    keyboard = []
    
    # إضافة المناطق الزمنية الشائعة
    for tz_code, tz_name in TimezoneManager.COMMON_TIMEZONES.items():
        icon = "✅" if tz_code == current_tz else "⚪"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} {tz_name}",
                callback_data=f"set_timezone:{task_id}:{tz_code}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_hour_filter:{task_id}")])
    
    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("set_timezone:"))
async def set_timezone(callback: CallbackQuery):
    """تعيين المنطقة الزمنية"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    timezone = parts[2]
    user_id = callback.from_user.id
    
    tz_manager = TimezoneManager(user_id)
    success = tz_manager.set_timezone(timezone)
    
    if success:
        tz_name = TimezoneManager.COMMON_TIMEZONES.get(timezone, timezone)
        await callback.answer(f"✅ تم تعيين المنطقة الزمنية: {tz_name}")
    else:
        await callback.answer("❌ فشل تعيين المنطقة الزمنية")
    
    await settings_hour_filter(callback)