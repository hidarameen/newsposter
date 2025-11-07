
import logging
from typing import Tuple
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES
from user_task_manager import UserTaskManager
from button_parser import ButtonParser

logger = logging.getLogger(__name__)
router = Router()

class SettingsStates(StatesGroup):
    waiting_for_header = State()
    waiting_for_footer = State()
    waiting_for_buttons = State()
    waiting_for_whitelist = State()
    waiting_for_blacklist = State()
    waiting_for_replacement = State()
    waiting_for_language_selection = State()

async def delete_previous_message(callback: CallbackQuery, state: FSMContext):
    """حذف الرسالة السابقة فقط إذا كانت مختلفة عن الرسالة الحالية"""
    try:
        data = await state.get_data()
        last_message_id = data.get('last_settings_message_id')
        current_message_id = callback.message.message_id
        
        # لا تحذف الرسالة إذا كانت هي نفسها الرسالة الحالية
        if last_message_id and last_message_id != current_message_id:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=last_message_id
                )
            except Exception:
                pass
    except Exception:
        pass

def check_premium_feature(feature_key: str, subscription_manager: SubscriptionManager) -> Tuple[bool, str]:
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

@router.callback_query(F.data.startswith("task_settings:"))
async def show_task_settings(callback: CallbackQuery, state: FSMContext):
    """إعادة توجيه إلى لوحة تفاصيل المهمة الموحدة"""
    from user_handlers import view_task_details
    await view_task_details(callback)

@router.callback_query(F.data.startswith("settings_media:"))
async def settings_media_filters(callback: CallbackQuery, state: FSMContext):
    await delete_previous_message(callback, state)
    
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    # التحقق من الاشتراك المدفوع
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium_feature('media_filters', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        sent_message = await callback.message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await state.update_data(last_settings_message_id=sent_message.message_id)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    media_settings = settings_manager.get_setting('media_filters')
    
    enabled = media_settings.get('enabled', False)
    allowed_types = media_settings.get('allowed_types', [])
    
    all_types = ['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note', 'animation', 'sticker']
    type_names = {
        'text': '📝 رسالة نصية',
        'photo': '🖼️ صور',
        'video': '🎥 فيديو',
        'document': '📄 مستندات',
        'audio': '🎵 صوت',
        'voice': '🎤 تسجيل صوتي',
        'video_note': '⭕ فيديو دائري',
        'animation': '🎞️ GIF',
        'sticker': '🎭 ملصقات'
    }
    
    keyboard_buttons = []
    
    toggle_text = "🔴 تعطيل الفلتر" if enabled else "🟢 تفعيل الفلتر"
    keyboard_buttons.append([InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_media:{task_id}")])
    
    if enabled:
        for i in range(0, len(all_types), 2):
            row = []
            for j in range(2):
                if i + j < len(all_types):
                    media_type = all_types[i + j]
                    is_allowed = media_type in allowed_types
                    icon = "✅" if is_allowed else "❌"
                    row.append(InlineKeyboardButton(
                        text=f"{icon} {type_names[media_type]}",
                        callback_data=f"toggle_media_type:{task_id}:{media_type}"
                    ))
            keyboard_buttons.append(row)
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="✅ تفعيل الكل", callback_data=f"media_all_on:{task_id}"),
            InlineKeyboardButton(text="❌ تعطيل الكل", callback_data=f"media_all_off:{task_id}")
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    status_text = "مفعّل ✅" if enabled else "معطّل ❌"
    allowed_text = ""
    if enabled:
        allowed_names = [type_names[t] for t in allowed_types]
        allowed_text = "\n\n<b>الوسائط المسموحة:</b>\n" + "\n".join([f"  • {n}" for n in allowed_names]) if allowed_names else "\n\n⚠️ لم يتم تحديد أي نوع وسائط"
    
    sent_message = await callback.message.edit_text(
        f"📹 <b>فلاتر الوسائط</b>\n\n"
        f"الحالة: {status_text}{allowed_text}\n\n"
        f"💡 حدد أنواع الوسائط المسموحة للنشر:",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await state.update_data(last_settings_message_id=sent_message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_media:"))
async def toggle_media_filter(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('media_filters')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} فلتر الوسائط")
    await settings_media_filters(callback, state)

@router.callback_query(F.data.startswith("toggle_media_type:"))
async def toggle_media_type(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    task_id = int(parts[1])
    media_type = parts[2]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    media_settings = settings_manager.get_setting('media_filters')
    allowed_types = media_settings.get('allowed_types', [])
    
    if media_type in allowed_types:
        allowed_types.remove(media_type)
    else:
        allowed_types.append(media_type)
    
    settings_manager.update_setting('media_filters', 'allowed_types', allowed_types)
    
    await callback.answer()
    await settings_media_filters(callback, state)

@router.callback_query(F.data.startswith("media_all_on:"))
async def media_all_on(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    all_types = ['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note', 'animation', 'sticker']
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('media_filters', 'allowed_types', all_types)
    
    await callback.answer("✅ تم تفعيل جميع أنواع الوسائط")
    await settings_media_filters(callback, state)

@router.callback_query(F.data.startswith("media_all_off:"))
async def media_all_off(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.update_setting('media_filters', 'allowed_types', [])
    
    await callback.answer("❌ تم تعطيل جميع أنواع الوسائط")
    await settings_media_filters(callback, state)

@router.callback_query(F.data.startswith("settings_header:"))
async def settings_header(callback: CallbackQuery, state: FSMContext):
    await delete_previous_message(callback, state)
    
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium_feature('header_footer', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        sent_message = await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await state.update_data(last_settings_message_id=sent_message.message_id)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    header_settings = settings_manager.get_setting('header')
    
    enabled = header_settings.get('enabled', False)
    current_header = header_settings.get('text', '')
    current_header_entities = header_settings.get('entities', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 تعطيل" if enabled else "🟢 تفعيل",
            callback_data=f"toggle_header:{task_id}"
        )],
        [InlineKeyboardButton(text="✏️ تعديل النص", callback_data=f"edit_header:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status_text = "مفعّل ✅" if enabled else "معطّل ❌"
    
    # عرض النص مع التنسيقات
    if current_header:
        from entity_handler import EntityHandler
        formatted_header = EntityHandler.entities_to_html(current_header, current_header_entities)
        header_preview = f"\n\n<b>النص الحالي:</b>\n{formatted_header}"
    else:
        header_preview = "\n\n⚠️ لم يتم تعيين نص"
    
    sent_message = await callback.message.edit_text(
        f"📝 <b>رأس الرسالة (Header)</b>\n\n"
        f"الحالة: {status_text}{header_preview}\n\n"
        f"💡 سيتم إضافة هذا النص في بداية كل رسالة",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await state.update_data(last_settings_message_id=sent_message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_header:"))
async def toggle_header(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('header')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} رأس الرسالة")
    await settings_header(callback, state)

@router.callback_query(F.data.startswith("edit_header:"))
async def edit_header(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(SettingsStates.waiting_for_header)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "📝 <b>تعديل رأس الرسالة</b>\n\n"
        "أرسل النص الذي تريد إضافته في بداية كل رسالة.\n\n"
        "💡 يمكنك استخدام التنسيقات (عريض، مائل، رابط، إلخ)",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await callback.answer()

@router.message(SettingsStates.waiting_for_header)
async def process_header_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    from entity_handler import EntityHandler
    import logging
    
    logger = logging.getLogger(__name__)
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    
    # تحويل entities مع تمرير النص للتأكد من صحة التحويل
    entities = EntityHandler.entities_to_dict(message.entities, message.text)
    
    logger.info(f"💾 حفظ هيدر - النص: '{message.text}'")
    logger.info(f"💾 حفظ هيدر - عدد entities: {len(entities) if entities else 0}")
    if entities:
        for e in entities:
            logger.info(f"   Entity: {e}")
    
    settings_manager.set_header(message.text, entities)
    
    # التحقق من الحفظ
    saved_header = settings_manager.get_setting('header')
    logger.info(f"✅ تم الحفظ - entities المحفوظة: {len(saved_header.get('entities', [])) if saved_header else 0}")
    
    await message.answer("✅ تم حفظ رأس الرسالة بنجاح!")
    
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_header:{task_id}")]
    ])
    
    await message.answer("اضغط للعودة:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("settings_footer:"))
async def settings_footer(callback: CallbackQuery, state: FSMContext):
    await delete_previous_message(callback, state)
    
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium_feature('header_footer', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        sent_message = await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await state.update_data(last_settings_message_id=sent_message.message_id)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    footer_settings = settings_manager.get_setting('footer')
    
    enabled = footer_settings.get('enabled', False)
    current_footer = footer_settings.get('text', '')
    current_footer_entities = footer_settings.get('entities', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 تعطيل" if enabled else "🟢 تفعيل",
            callback_data=f"toggle_footer:{task_id}"
        )],
        [InlineKeyboardButton(text="✏️ تعديل النص", callback_data=f"edit_footer:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status_text = "مفعّل ✅" if enabled else "معطّل ❌"
    
    # عرض النص مع التنسيقات
    if current_footer:
        from entity_handler import EntityHandler
        formatted_footer = EntityHandler.entities_to_html(current_footer, current_footer_entities)
        footer_preview = f"\n\n<b>النص الحالي:</b>\n{formatted_footer}"
    else:
        footer_preview = "\n\n⚠️ لم يتم تعيين نص"
    
    sent_message = await callback.message.edit_text(
        f"📝 <b>ذيل الرسالة (Footer)</b>\n\n"
        f"الحالة: {status_text}{footer_preview}\n\n"
        f"💡 سيتم إضافة هذا النص في نهاية كل رسالة",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await state.update_data(last_settings_message_id=sent_message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_footer:"))
async def toggle_footer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('footer')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} ذيل الرسالة")
    await settings_footer(callback, state)

@router.callback_query(F.data.startswith("edit_footer:"))
async def edit_footer(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(SettingsStates.waiting_for_footer)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "📝 <b>تعديل ذيل الرسالة</b>\n\n"
        "أرسل النص الذي تريد إضافته في نهاية كل رسالة.\n\n"
        "💡 يمكنك استخدام التنسيقات (عريض، مائل، رابط، إلخ)",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await callback.answer()

@router.message(SettingsStates.waiting_for_footer)
async def process_footer_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    from entity_handler import EntityHandler
    import logging
    
    logger = logging.getLogger(__name__)
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    
    # تحويل entities مع تمرير النص للتأكد من صحة التحويل
    entities = EntityHandler.entities_to_dict(message.entities, message.text)
    
    logger.info(f"💾 حفظ فوتر - النص: '{message.text}'")
    logger.info(f"💾 حفظ فوتر - عدد entities: {len(entities) if entities else 0}")
    if entities:
        for e in entities:
            logger.info(f"   Entity: {e}")
    
    settings_manager.set_footer(message.text, entities)
    
    # التحقق من الحفظ
    saved_footer = settings_manager.get_setting('footer')
    logger.info(f"✅ تم الحفظ - entities المحفوظة: {len(saved_footer.get('entities', [])) if saved_footer else 0}")
    
    await message.answer("✅ تم حفظ ذيل الرسالة بنجاح!")
    
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_footer:{task_id}")]
    ])
    
    await message.answer("اضغط للعودة:", reply_markup=keyboard)

from typing import Tuple
