
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES
from button_parser import ButtonParser

logger = logging.getLogger(__name__)
router = Router()

class ButtonStates(StatesGroup):
    waiting_for_buttons = State()

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

@router.callback_query(F.data.startswith("settings_buttons:"))
async def settings_buttons(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium_feature('inline_buttons', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    button_settings = settings_manager.get_setting('inline_buttons')
    
    enabled = button_settings.get('enabled', False)
    buttons = button_settings.get('buttons', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 تعطيل" if enabled else "🟢 تفعيل",
            callback_data=f"toggle_buttons:{task_id}"
        )],
        [InlineKeyboardButton(text="➕ إضافة أزرار", callback_data=f"add_buttons:{task_id}")],
        [InlineKeyboardButton(text="👁️ معاينة الأزرار", callback_data=f"preview_buttons:{task_id}")],
        [InlineKeyboardButton(text="🗑️ مسح الأزرار", callback_data=f"clear_buttons:{task_id}")],
        [InlineKeyboardButton(text="📖 طرق الإضافة", callback_data=f"button_help:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status_text = "مفعّل ✅" if enabled else "معطّل ❌"
    button_count = sum(len(row) for row in buttons)
    buttons_info = f"\n\n<b>عدد الأزرار:</b> {button_count}" if buttons else "\n\n⚠️ لم يتم إضافة أزرار"
    
    await callback.message.edit_text(
        f"🔘 <b>أزرار إنلاين</b>\n\n"
        f"الحالة: {status_text}{buttons_info}\n\n"
        f"💡 يمكنك إضافة أزرار مخصصة لكل رسالة",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_buttons:"))
async def toggle_buttons(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('inline_buttons')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} الأزرار")
    await settings_buttons(callback, state)

@router.callback_query(F.data.startswith("add_buttons:"))
async def add_buttons(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(ButtonStates.waiting_for_buttons)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    help_text = """🔘 <b>إضافة أزرار إنلاين</b>

📝 <b>طرق الإضافة:</b>

🔹 <b>للأزرار المنفصلة</b> (كل زر في سطر):
نص الزر الأول - رابط الزر الأول
نص الزر الثاني - رابط الزر الثاني

🔹 <b>لعدة أزرار في صف واحد</b> (يفصل بينهم |):
نص الزر - رابط | نص الزر 2 - رابط 2

💡 <b>أمثلة:</b>
زيارة الموقع - https://example.com
اشترك بالقناة - https://t.me/channel
تابعنا - https://twitter.com | دعمنا - https://paypal.com

🎁 <b>أزرار جاهزة:</b>
شارك - Facebook
شارك - Twitter
شارك - WhatsApp
شارك - Telegram

⚡ <b>زر Pop-up:</b>
نص الزر - Popup - نص التنبيه

أرسل الأزرار الآن:"""
    
    await callback.message.edit_text(help_text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.message(ButtonStates.waiting_for_buttons)
async def process_buttons_input(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    try:
        buttons = ButtonParser.parse_buttons_from_text(message.text)
        
        if not buttons:
            await message.answer("❌ لم يتم التعرف على أي أزرار صالحة. يرجى المحاولة مرة أخرى.")
            return
        
        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.set_inline_buttons(buttons)
        
        await message.answer(f"✅ تم حفظ {sum(len(row) for row in buttons)} زر بنجاح!")
        
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁️ معاينة", callback_data=f"preview_buttons:{task_id}")],
            [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data=f"settings_buttons:{task_id}")]
        ])
        
        await message.answer("اختر إجراء:", reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الأزرار: {e}")
        await message.answer("❌ حدث خطأ في معالجة الأزرار. يرجى المحاولة مرة أخرى.")

@router.callback_query(F.data.startswith("preview_buttons:"))
async def preview_buttons(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    button_settings = settings_manager.get_setting('inline_buttons')
    buttons = button_settings.get('buttons', [])
    
    if not buttons:
        await callback.answer("❌ لا توجد أزرار لعرضها", show_alert=True)
        return
    
    preview_markup = ButtonParser.create_preview_markup(buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_buttons:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "👁️ <b>معاينة الأزرار</b>\n\n"
        "هكذا ستظهر الأزرار في الرسائل:",
        parse_mode='HTML',
        reply_markup=preview_markup
    )
    
    await callback.message.reply("للعودة:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("clear_buttons:"))
async def clear_buttons(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.set_inline_buttons([])
    
    await callback.answer("✅ تم مسح جميع الأزرار", show_alert=True)
    await settings_buttons(callback, None)

@router.callback_query(F.data.startswith("button_help:"))
async def button_help(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    
    help_text = """📖 <b>دليل إضافة الأزرار</b>

🔸 <b>صيغة الأزرار:</b>
نص الزر - الرابط أو الإجراء

🔸 <b>أمثلة عملية:</b>

1️⃣ زر واحد في سطر:
<code>زيارة الموقع - https://example.com</code>

2️⃣ زرين في سطر واحد:
<code>Facebook - https://fb.com | Twitter - https://twitter.com</code>

3️⃣ أزرار مشاركة جاهزة:
<code>شارك على فيسبوك - Facebook</code>
<code>شارك على تويتر - Twitter</code>
<code>شارك واتساب - WhatsApp</code>
<code>شارك تلغرام - Telegram</code>

4️⃣ زر Pop-up (تنبيه):
<code>معلومات - Popup - هذا نص التنبيه</code>

⚡ <b>نصائح:</b>
• استخدم | للفصل بين الأزرار في نفس الصف
• استخدم سطر جديد لإنشاء صف جديد
• يمكنك خلط الأنواع المختلفة"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_buttons:{task_id}")]
    ])
    
    await callback.message.edit_text(help_text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("popup:"))
async def handle_popup(callback: CallbackQuery):
    popup_text = callback.data.replace("popup:", "", 1)
    await callback.answer(popup_text, show_alert=True)
