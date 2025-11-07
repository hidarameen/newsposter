from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from storage import UserStorage
from middlewares import AdminPrivateMiddleware
from config import ADMIN_ID
import logging
from aiogram.fsm.storage.memory import MemoryStorage

logger = logging.getLogger(__name__)

async def start_handler(message: Message, state=None):
    from aiogram.fsm.context import FSMContext
    from user_handlers import timeout_tasks, delete_last_panel_and_save_new

    # تجاهل الأوامر في المجموعات
    if message.chat.type in ['group', 'supergroup']:
        return

    user_id = message.from_user.id

    # إغلاق أي FSM state مفتوح
    if state and isinstance(state, FSMContext):
        await state.clear()

    # إلغاء مهمة timeout إن وجدت
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
        del timeout_tasks[user_id]
        logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} عبر /start")

    # إزالة المستخدم من users_adding_bot إن وجد
    try:
        from channel_detection import users_adding_bot
        if user_id in users_adding_bot:
            users_adding_bot.discard(user_id)
            logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot عبر /start")
    except:
        pass

    storage = UserStorage(user_id)

    user_data = storage.load_data()
    is_new_user = not user_data.get('started')
    if is_new_user:
        storage.update_data('started', True)
        storage.update_data('username', message.from_user.username)
        storage.update_data('first_name', message.from_user.first_name)

        from notification_manager import notification_manager
        from stats_manager import stats_manager
        try:
            await notification_manager.notify_new_user(
                message.bot,
                user_id,
                message.from_user.username,
                message.from_user.first_name
            )
            stats_manager.increment_users()
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار المستخدم الجديد: {e}")

    is_admin = ADMIN_ID != 0 and user_id == ADMIN_ID

    # محاولة الحصول على رسالة ترحيب مخصصة
    from welcome_message_manager import welcome_message_manager
    custom_welcome = welcome_message_manager.get_welcome_message()

    if is_admin:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 إدارة المهام الإخبارية", callback_data="user_manage_tasks")],
            [InlineKeyboardButton(text="📢 قنواتي", callback_data="show_my_channels")],
            [InlineKeyboardButton(text="⚙️ مهام التوجيه (مشرف)", callback_data="fwd_list")],
            [InlineKeyboardButton(text="⭐ اشتراكي", callback_data="my_subscription")],
            [InlineKeyboardButton(text="📊 حالة النظام", callback_data="show_system_status")],
            [InlineKeyboardButton(text="❓ مساعدة", callback_data="help_menu")],
            [InlineKeyboardButton(text="المصادر المتاحة", callback_data="available_sources")]
        ])

        welcome_text = f"""
👑 مرحباً {message.from_user.first_name}!

🔹 <b>أنت مشرف البوت</b>

يمكنك إدارة مهام النشر التلقائي والتحكم الكامل بالنظام.

اختر من القائمة أدناه:
"""
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إضافة مهمة إخبارية", callback_data="user_add_task_step1")],
            [InlineKeyboardButton(text="⚙️ إعدادات المهام الإخبارية", callback_data="user_manage_tasks")],
            [InlineKeyboardButton(text="⭐ اشتراكي", callback_data="my_subscription")],
            [InlineKeyboardButton(text="👨‍💻 مطور البوت", url="https://t.me/akm100ye")],
            [InlineKeyboardButton(text="❓ مساعدة", callback_data="help_menu")],
            [InlineKeyboardButton(text="المصادر المتاحة", callback_data="available_sources")]
        ])

        # استخدام الرسالة المخصصة إذا كانت متوفرة
        if custom_welcome:
            welcome_text = custom_welcome.replace('{name}', message.from_user.first_name)
        else:
            welcome_text = f"""
مرحباً {message.from_user.first_name}! 👋

أهلاً بك في بوت النشر التلقائي 📰

🔹 <b>كيف تستخدم البوت؟</b>
1️⃣ أضف البوت كمشرف لقناتك
2️⃣ اضغط على "إضافة مهمة إخبارية"
3️⃣ اختر المصدر وقناتك
4️⃣ ستحصل على نسخ تلقائية من المحتوى

اختر من القائمة أدناه:
"""

    # إرسال رسالة الترحيب وحذف اللوحة السابقة
    sent_message = await message.answer(welcome_text, parse_mode='HTML', reply_markup=keyboard)

    # حفظ معرف الرسالة الجديدة وحذف اللوحة السابقة
    await delete_last_panel_and_save_new(message.bot, user_id, sent_message.message_id)


async def status_handler(message: Message):
    # تجاهل الأوامر في المجموعات
    if message.chat.type in ['group', 'supergroup']:
        return

    import parallel_forwarding_system

    if not parallel_forwarding_system.parallel_system:
        await message.answer("❌ النظام المتوازي غير مفعّل!")
        return

    stats = parallel_forwarding_system.parallel_system.get_stats()

    text = "📊 <b>حالة النظام</b>\n\n"
    text += f"✅ البوت يعمل بشكل صحيح\n"
    text += f"📥 حجم القائمة العامة: {stats['global_queue_size']}\n"
    text += f"🔄 عدد Global Workers: {stats['num_global_workers']}\n"
    text += f"✅ عدد المهام النشطة: {stats['num_active_tasks']}\n"

    await message.answer(text)

async def info_handler(message: Message):
    # تجاهل الأوامر في المجموعات
    if message.chat.type in ['group', 'supergroup']:
        return

    user_id = message.from_user.id
    storage = UserStorage(user_id)
    user_data = storage.load_data()

    info_text = f"""
📊 معلوماتك:

🆔 معرف المستخدم: {user_id}
👤 الاسم: {user_data.get('first_name', 'غير محدد')}
🔗 اسم المستخدم: @{user_data.get('username', 'غير محدد')}
✅ مسجل منذ: {user_data.get('started', False)}
"""
    await message.answer(info_text)

async def back_to_start_handler(callback: CallbackQuery):
    """العودة إلى القائمة الرئيسية"""
    user_id = callback.from_user.id
    is_admin = ADMIN_ID != 0 and user_id == ADMIN_ID

    # محاولة الحصول على رسالة ترحيب مخصصة
    from welcome_message_manager import welcome_message_manager
    custom_welcome = welcome_message_manager.get_welcome_message()

    if is_admin:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 إدارة المهام الإخبارية", callback_data="user_manage_tasks")],
            [InlineKeyboardButton(text="📢 قنواتي", callback_data="show_my_channels")],
            [InlineKeyboardButton(text="⚙️ مهام التوجيه (مشرف)", callback_data="fwd_list")],
            [InlineKeyboardButton(text="⭐ اشتراكي", callback_data="my_subscription")],
            [InlineKeyboardButton(text="📊 حالة النظام", callback_data="show_system_status")],
            [InlineKeyboardButton(text="❓ مساعدة", callback_data="help_menu")],
            [InlineKeyboardButton(text="المصادر المتاحة", callback_data="available_sources")]
        ])

        welcome_text = f"""
👑 مرحباً {callback.from_user.first_name}!

🔹 <b>أنت مشرف البوت</b>

يمكنك إدارة مهام النشر التلقائي والتحكم الكامل بالنظام.

اختر من القائمة أدناه:
"""
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إضافة مهمة إخبارية", callback_data="user_add_task_step1")],
            [InlineKeyboardButton(text="⚙️ إعدادات المهام الإخبارية", callback_data="user_manage_tasks")],
            [InlineKeyboardButton(text="⭐ اشتراكي", callback_data="my_subscription")],
            [InlineKeyboardButton(text="👨‍💻 مطور البوت", url="https://t.me/akm100ye")],
            [InlineKeyboardButton(text="❓ مساعدة", callback_data="help_menu")],
            [InlineKeyboardButton(text="المصادر المتاحة", callback_data="available_sources")]
        ])

        # استخدام الرسالة المخصصة إذا كانت متوفرة
        if custom_welcome:
            welcome_text = custom_welcome.replace('{name}', callback.from_user.first_name)
        else:
            welcome_text = f"""
مرحباً {callback.from_user.first_name}! 👋

أهلاً بك في بوت النشر التلقائي 📰

🔹 <b>كيف تستخدم البوت؟</b>
1️⃣ أضف البوت كمشرف لقناتك
2️⃣ اضغط على "إضافة مهمة إخبارية"
3️⃣ اختر المصدر وقناتك
4️⃣ ستحصل على نسخ تلقائية من المحتوى

اختر من القائمة أدناه:
"""

    await callback.message.edit_text(welcome_text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

def register_handlers(dp: Dispatcher):
    from user_handlers import router as user_router
    from channel_detection import router as channel_router
    from activation_handler import router as activation_router
    from forwarding_handlers import router as forwarding_router
    from media_handler import router as media_router
    from settings_handlers import router as settings_router
    from settings_handlers_footer import router as footer_router
    from settings_handlers_buttons import router as buttons_router
    from settings_handlers_other import router as other_router
    from settings_handlers_text_format import router as text_format_router
    from settings_handlers_words import router as words_router
    from settings_handlers_replacements import router as replacements_router
    from settings_handlers_premium import router as premium_router
    from subscription_handlers import router as subscription_router
    from admin_handlers import router as admin_router
    from test_task_handler import router as test_task_router
    from help_handlers import router as help_router
    from sources_handlers import router as sources_router

    dp.message.register(start_handler, Command("start"))
    dp.message.register(info_handler, Command("info"))
    dp.message.register(status_handler, Command("status"))

    # تسجيل handler العودة للرئيسية
    dp.callback_query.register(back_to_start_handler, F.data == "back_to_start")

    dp.include_router(help_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(settings_router)
    dp.include_router(footer_router)
    dp.include_router(buttons_router)
    dp.include_router(other_router)
    dp.include_router(premium_router)
    dp.include_router(text_format_router)
    dp.include_router(words_router)
    dp.include_router(replacements_router)
    dp.include_router(subscription_router)
    dp.include_router(test_task_router)
    dp.include_router(channel_router)
    dp.include_router(activation_router)
    dp.include_router(sources_router)

    forwarding_router.message.middleware(AdminPrivateMiddleware())
    forwarding_router.callback_query.middleware(AdminPrivateMiddleware())
    dp.include_router(forwarding_router)

    dp.include_router(media_router)

    logger.info("✅ All handlers registered successfully")