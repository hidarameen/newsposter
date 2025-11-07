
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES

logger = logging.getLogger(__name__)
router = Router()

class WordFilterStates(StatesGroup):
    waiting_for_whitelist = State()
    waiting_for_blacklist = State()
    waiting_for_replacement_old = State()
    waiting_for_replacement_new = State()

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

@router.callback_query(F.data.startswith("settings_whitelist:"))
async def settings_whitelist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('whitelist', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    whitelist_settings = settings_manager.get_setting('whitelist_words')
    
    enabled = whitelist_settings.get('enabled', False)
    words = whitelist_settings.get('words', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_whitelist:{task_id}")],
        [InlineKeyboardButton(text="➕ إضافة كلمات", callback_data=f"add_whitelist:{task_id}")],
        [InlineKeyboardButton(text="📋 عرض القائمة", callback_data=f"show_whitelist:{task_id}")],
        [InlineKeyboardButton(text="🗑️ مسح القائمة", callback_data=f"clear_whitelist:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    word_count = f"\n\n<b>عدد الكلمات:</b> {len(words)}" if words else "\n\n⚠️ القائمة فارغة"
    
    await callback.message.edit_text(
        f"✅ <b>القائمة البيضاء</b>\n\n"
        f"الحالة: {status}{word_count}\n\n"
        f"💡 يسمح فقط بالرسائل التي تحتوي على هذه الكلمات",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_whitelist:"))
async def toggle_whitelist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('whitelist_words')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} القائمة البيضاء")
    await settings_whitelist(callback)

@router.callback_query(F.data.startswith("add_whitelist:"))
async def add_whitelist(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(WordFilterStates.waiting_for_whitelist)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "✅ <b>إضافة كلمات للقائمة البيضاء</b>\n\n"
        "أرسل الكلمات (كل كلمة في سطر أو مفصولة بفواصل)\n\n"
        "مثال:\nأخبار\nعاجل\nمهم",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.message(WordFilterStates.waiting_for_whitelist)
async def process_whitelist_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    words = [w.strip() for w in message.text.replace(',', '\n').split('\n') if w.strip()]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    for word in words:
        settings_manager.add_whitelist_word(word)
    
    await message.answer(f"✅ تم إضافة {len(words)} كلمة للقائمة البيضاء")
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_whitelist:{task_id}")]
    ])
    await message.answer("اضغط للعودة:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_whitelist:"))
async def show_whitelist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    words = settings_manager.get_setting('whitelist_words', 'words')
    
    if not words:
        await callback.answer("القائمة فارغة", show_alert=True)
        return
    
    text = "✅ <b>القائمة البيضاء:</b>\n\n" + "\n".join([f"  • {w}" for w in words])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_whitelist:{task_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("clear_whitelist:"))
async def clear_whitelist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.clear_whitelist()
    
    await callback.answer("✅ تم مسح القائمة البيضاء", show_alert=True)
    await settings_whitelist(callback)

@router.callback_query(F.data.startswith("settings_blacklist:"))
async def settings_blacklist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('blacklist', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    blacklist_settings = settings_manager.get_setting('blacklist_words')
    
    enabled = blacklist_settings.get('enabled', False)
    words = blacklist_settings.get('words', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_blacklist:{task_id}")],
        [InlineKeyboardButton(text="➕ إضافة كلمات", callback_data=f"add_blacklist:{task_id}")],
        [InlineKeyboardButton(text="📋 عرض القائمة", callback_data=f"show_blacklist:{task_id}")],
        [InlineKeyboardButton(text="🗑️ مسح القائمة", callback_data=f"clear_blacklist:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    word_count = f"\n\n<b>عدد الكلمات:</b> {len(words)}" if words else "\n\n⚠️ القائمة فارغة"
    
    await callback.message.edit_text(
        f"🚫 <b>القائمة السوداء</b>\n\n"
        f"الحالة: {status}{word_count}\n\n"
        f"💡 يحظر الرسائل التي تحتوي على هذه الكلمات",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_blacklist:"))
async def toggle_blacklist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('blacklist_words')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} القائمة السوداء")
    await settings_blacklist(callback)

@router.callback_query(F.data.startswith("add_blacklist:"))
async def add_blacklist(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(WordFilterStates.waiting_for_blacklist)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "🚫 <b>إضافة كلمات للقائمة السوداء</b>\n\n"
        "أرسل الكلمات المحظورة (كل كلمة في سطر أو مفصولة بفواصل)\n\n"
        "مثال:\nإعلان\nدعاية\nترويج",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.message(WordFilterStates.waiting_for_blacklist)
async def process_blacklist_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    words = [w.strip() for w in message.text.replace(',', '\n').split('\n') if w.strip()]
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    for word in words:
        settings_manager.add_blacklist_word(word)
    
    await message.answer(f"✅ تم إضافة {len(words)} كلمة للقائمة السوداء")
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_blacklist:{task_id}")]
    ])
    await message.answer("اضغط للعودة:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_blacklist:"))
async def show_blacklist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    words = settings_manager.get_setting('blacklist_words', 'words')
    
    if not words:
        await callback.answer("القائمة فارغة", show_alert=True)
        return
    
    text = "🚫 <b>القائمة السوداء:</b>\n\n" + "\n".join([f"  • {w}" for w in words])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_blacklist:{task_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("clear_blacklist:"))
async def clear_blacklist(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.clear_blacklist()
    
    await callback.answer("✅ تم مسح القائمة السوداء", show_alert=True)
    await settings_blacklist(callback)
