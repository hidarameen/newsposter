
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES

logger = logging.getLogger(__name__)
router = Router()

class FooterStates(StatesGroup):
    waiting_for_footer = State()

def check_premium_feature(feature_key: str, subscription_manager: SubscriptionManager):
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

@router.callback_query(F.data.startswith("settings_footer:"))
async def settings_footer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium_feature('header_footer', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
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
    
    await callback.message.edit_text(
        f"📝 <b>ذيل الرسالة (Footer)</b>\n\n"
        f"الحالة: {status_text}{footer_preview}\n\n"
        f"💡 سيتم إضافة هذا النص في نهاية كل رسالة",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
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
    
    await state.set_state(FooterStates.waiting_for_footer)
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

@router.message(FooterStates.waiting_for_footer)
async def process_footer_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    from entity_handler import EntityHandler
    
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
