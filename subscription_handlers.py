
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from subscription_manager import SubscriptionManager, PLAN_PRICES, PREMIUM_FEATURES

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "upgrade_account")
async def show_upgrade_plans(callback: CallbackQuery):
    user_id = callback.from_user.id
    sub_manager = SubscriptionManager(user_id)
    
    can_trial = sub_manager.can_use_trial()
    
    text = """🔒 <b>ترقية الحساب - الميزات المدفوعة</b>

🎁 <b>المميزات المدفوعة:</b>

"""
    
    for feature_info in PREMIUM_FEATURES.values():
        text += f"{feature_info['icon']} {feature_info['name']}\n"
    
    text += "\n♾️ مهام نشر غير محدودة\n\n💰 <b>الخطط المتاحة:</b>\n"
    
    keyboard_buttons = []
    
    for plan_key, plan_info in PLAN_PRICES.items():
        price_per_month = plan_info['price'] / (plan_info['duration_days'] / 30)
        text += f"\n💎 <b>{plan_info['name']}</b>: ${plan_info['price']}"
        text += f" (${price_per_month:.1f}/شهر)\n"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"💎 {plan_info['name']} - ${plan_info['price']}",
                callback_data=f"subscribe_{plan_key}"
            )
        ])
    
    if can_trial:
        text += "\n\n🎁 <b>تجربة مجانية!</b>\n"
        text += "احصل على 7 أيام تجريبية مجانية لتجربة جميع المميزات!\n"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="🎁 تجربة مجانية (7 أيام)",
                callback_data="start_trial"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("subscribe_"))
async def process_subscription(callback: CallbackQuery):
    from config import ADMIN_ID
    
    user_id = callback.from_user.id
    plan_key = callback.data.split("_")[1]
    
    if plan_key not in PLAN_PRICES:
        await callback.answer("خطة غير صالحة", show_alert=True)
        return
    
    plan_info = PLAN_PRICES[plan_key]
    
    subscription_message = f"""مرحباً! 👋

أرغب في الاشتراك في الخطة التالية:

📦 الخطة: {plan_info['name']}
⏰ المدة: {plan_info['duration_days']} يوم
💰 السعر: ${plan_info['price']}

🆔 معرف المستخدم: {user_id}
🔑 كود الخطة: {plan_key}

أرجو تفعيل اشتراكي، وشكراً! ✨"""
    
    text = f"""📋 <b>تفاصيل الاشتراك</b>

الخطة: <b>{plan_info['name']}</b>
المدة: <b>{plan_info['duration_days']} يوم</b>
السعر: <b>${plan_info['price']}</b>

📞 <b>للاشتراك:</b>
اضغط على الزر أدناه للتواصل مع الإدارة وإتمام عملية الدفع.

معرف المستخدم: <code>{user_id}</code>
الخطة المطلوبة: <code>{plan_key}</code>

سيتم تفعيل حسابك فوراً بعد تأكيد الدفع! ✨
"""
    
    keyboard_buttons = []
    
    # إرسال مباشر إلى @akm100ye
    import urllib.parse
    encoded_message = urllib.parse.quote(subscription_message)
    share_url = f"https://t.me/akm100ye?text={encoded_message}"
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="📩 إرسال طلب اشتراك",
            url=share_url
        )
    ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 رجوع للخطط", callback_data="upgrade_account")])
    keyboard_buttons.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="back_to_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("copy_subscription_msg:"))
async def copy_subscription_message(callback: CallbackQuery):
    user_id = callback.from_user.id
    plan_key = callback.data.split(":")[1]
    
    if plan_key not in PLAN_PRICES:
        await callback.answer("خطة غير صالحة", show_alert=True)
        return
    
    plan_info = PLAN_PRICES[plan_key]
    
    subscription_message = f"""مرحباً! 👋

أرغب في الاشتراك في الخطة التالية:

📦 الخطة: {plan_info['name']}
⏰ المدة: {plan_info['duration_days']} يوم
💰 السعر: ${plan_info['price']}

🆔 معرف المستخدم: {user_id}
🔑 كود الخطة: {plan_key}

أرجو تفعيل اشتراكي، وشكراً! ✨"""
    
    await callback.bot.send_message(
        chat_id=user_id,
        text=f"📋 <b>رسالة طلب الاشتراك:</b>\n\n{subscription_message}\n\n<i>انسخ هذه الرسالة وأرسلها للإدارة</i>",
        parse_mode='HTML'
    )
    await callback.answer("✅ تم إرسال الرسالة لك في الخاص!", show_alert=True)

@router.callback_query(F.data == "start_trial")
async def start_trial(callback: CallbackQuery):
    user_id = callback.from_user.id
    sub_manager = SubscriptionManager(user_id)
    
    if not sub_manager.can_use_trial():
        await callback.answer("❌ لقد استخدمت التجربة المجانية من قبل", show_alert=True)
        return
    
    sub_manager.activate_subscription('premium', 7, is_trial=True)
    
    text = """🎉 <b>تم تفعيل التجربة المجانية!</b>

✅ تم تفعيل جميع المميزات المدفوعة لمدة 7 أيام

🎁 <b>يمكنك الآن:</b>
• إضافة عدد غير محدود من مهام النشر
• استخدام جميع الفلاتر المتقدمة
• تخصيص رسائلك بالكامل
• وأكثر بكثير!

⏰ <b>مدة التجربة:</b> 7 أيام
📅 <b>تنتهي في:</b> {تاريخ انتهاء الصلاحية}

💡 استمتع بجميع المميزات الآن!
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ جرب المميزات الآن", callback_data="user_manage_tasks")],
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer("🎉 تم التفعيل بنجاح!", show_alert=True)

@router.callback_query(F.data == "my_subscription")
async def show_my_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    sub_manager = SubscriptionManager(user_id)
    
    plan_details = sub_manager.get_plan_details()
    
    if plan_details['is_active']:
        plan_emoji = "🎁" if plan_details['is_trial'] else "🔒"
        plan_text = "تجريبي" if plan_details['is_trial'] else plan_details['plan']
        
        text = f"""{plan_emoji} <b>اشتراكك النشط</b>

📋 <b>الخطة:</b> {plan_text}
✅ <b>الحالة:</b> نشط
⏰ <b>الأيام المتبقية:</b> {plan_details['days_remaining']} يوم
📅 <b>ينتهي في:</b> {plan_details['end_date'][:10]}

🎁 <b>المميزات المفعلة:</b>
"""
        
        for feature_info in PREMIUM_FEATURES.values():
            text += f"  ✅ {feature_info['icon']} {feature_info['name']}\n"
        
        keyboard_buttons = []
        
        if plan_details['is_trial']:
            keyboard_buttons.append([
                InlineKeyboardButton(text="⬇️ التحويل للخطة المجانية", callback_data="downgrade_to_free")
            ])
        
        if plan_details['days_remaining'] <= 7:
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔄 تجديد الاشتراك", callback_data="upgrade_account")
            ])
        
    else:
        text = """📋 <b>اشتراكك</b>

الخطة: <b>مجانية</b>

🔓 <b>المميزات المتاحة:</b>
  ✅ مهمة نشر واحدة
  ✅ فلاتر الوسائط الأساسية

🔒 <b>المميزات المقفلة:</b>
"""
        
        for feature_info in list(PREMIUM_FEATURES.values())[:6]:
            text += f"  🔒 {feature_info['icon']} {feature_info['name']}\n"
        
        text += "\n💡 قم بترقية حسابك للحصول على جميع المميزات!"
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")]
        ]
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "downgrade_to_free")
async def downgrade_to_free_confirm(callback: CallbackQuery):
    """تأكيد التحويل للخطة المجانية"""
    logger.info(f"User {callback.from_user.id} clicked downgrade_to_free button")
    
    text = """⚠️ <b>تأكيد التحويل للخطة المجانية</b>

هل أنت متأكد من رغبتك في التحويل للخطة المجانية؟

🔻 <b>سيتم:</b>
• إيقاف التجربة المجانية فوراً
• تعطيل جميع المميزات المدفوعة
• تعطيل جميع المهام ماعدا مهمة واحدة
• تعطيل الفلاتر والإعدادات المتقدمة

⚠️ <b>تنبيه:</b> هذا الإجراء لا يمكن التراجع عنه!

💡 يمكنك دائماً الترقية للخطة المدفوعة لاحقاً."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ نعم، أريد التحويل", callback_data="downgrade_to_free_confirmed"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="my_subscription")
        ]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "downgrade_to_free_confirmed")
async def downgrade_to_free_confirmed(callback: CallbackQuery):
    """تنفيذ التحويل للخطة المجانية"""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} confirmed downgrade to free plan")
    
    try:
        sub_manager = SubscriptionManager(user_id)
        sub_manager.disable_active_premium_features()
        sub_manager.deactivate_premium_features()
        logger.info(f"Successfully downgraded user {user_id} to free plan")
    except Exception as e:
        logger.error(f"Error downgrading user {user_id}: {e}", exc_info=True)
        await callback.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى", show_alert=True)
        return
    
    text = """✅ <b>تم التحويل للخطة المجانية</b>

🔓 تم تحويل حسابك بنجاح إلى الخطة المجانية.

📋 <b>الخطة الحالية:</b> مجانية

✅ <b>المميزات المتاحة:</b>
  ✅ مهمة نشر واحدة
  ✅ فلاتر الوسائط الأساسية

💡 يمكنك الترقية للخطة المدفوعة في أي وقت للحصول على جميع المميزات!"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer("✅ تم التحويل للخطة المجانية", show_alert=True)
