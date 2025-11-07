import logging
from typing import Dict
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from user_task_manager import UserTaskManager
from user_channel_manager import UserChannelManager
from forwarding_manager import ForwardingManager
from channel_verification import ChannelVerification
from pending_tasks_manager import PendingTasksManager
import asyncio

logger = logging.getLogger(__name__)

router = Router()

class UserTaskCreationStates(StatesGroup):
    waiting_for_admin_selection = State()
    waiting_for_channel_link = State()
    waiting_for_channel_addition = State()

# قاموس لتتبع مهام timeout
timeout_tasks = {}

# قاموس لتتبع آخر رسالة لوحة تحكم لكل مستخدم
last_control_panel_message: Dict[int, int] = {}

async def delete_last_panel_and_save_new(bot: Bot, user_id: int, new_message_id: int):
    """
    حذف لوحة التحكم السابقة وحفظ الجديدة

    Args:
        bot: Bot instance
        user_id: معرف المستخدم
        new_message_id: معرف الرسالة الجديدة
    """
    global last_control_panel_message

    # حذف الرسالة السابقة إن وجدت
    if user_id in last_control_panel_message:
        old_message_id = last_control_panel_message[user_id]
        try:
            await bot.delete_message(chat_id=user_id, message_id=old_message_id)
            logger.info(f"🗑️ تم حذف اللوحة السابقة {old_message_id} للمستخدم {user_id}")
        except Exception as e:
            logger.debug(f"⚠️ لم يتم حذف الرسالة السابقة {old_message_id}: {e}")

    # حفظ معرف الرسالة الجديدة
    last_control_panel_message[user_id] = new_message_id
    logger.debug(f"💾 تم حفظ اللوحة الجديدة {new_message_id} للمستخدم {user_id}")

async def timeout_waiting_state(user_id: int, state: FSMContext, bot: Bot, timeout_seconds: int):
    """
    إنهاء حالة الانتظار بعد فترة زمنية محددة

    Args:
        user_id: معرف المستخدم
        state: FSMContext
        timeout_seconds: المدة بالثواني قبل الإنهاء
    """
    from channel_detection import users_adding_bot

    try:
        # الانتظار للمدة المحددة
        await asyncio.sleep(timeout_seconds)

        # التحقق من أن المستخدم لا يزال في حالة الانتظار
        current_state = await state.get_state()

        if current_state == UserTaskCreationStates.waiting_for_channel_link.state:
            logger.info(f"⏰ انتهت مدة انتظار المستخدم {user_id} لإضافة القناة")

            # إزالة المستخدم من users_adding_bot
            if user_id in users_adding_bot:
                users_adding_bot.discard(user_id)
                logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot بعد انتهاء المدة")

            # مسح الحالة
            await state.clear()

            # إزالة من timeout_tasks
            if user_id in timeout_tasks:
                del timeout_tasks[user_id]

            # إرسال إشعار للمستخدم
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ إضافة مهمة", callback_data="user_add_task_step1")],
                    [InlineKeyboardButton(text="📋 مهامي", callback_data="user_manage_tasks")]
                ])

                await bot.send_message(
                    user_id,
                    "⏰ <b>انتهت مدة الانتظار</b>\n\n"
                    "انتهت فترة إضافة القناة (5 دقائق).\n"
                    "يمكنك البدء من جديد بالضغط على الزر أدناه.",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"❌ خطأ في إرسال إشعار انتهاء المدة للمستخدم {user_id}: {e}")
    except asyncio.CancelledError:
        # المهمة تم إلغاؤها - هذا طبيعي عندما يتم إنشاء المهمة بنجاح
        logger.info(f"✅ timeout للمستخدم {user_id} تم إلغاؤه بنجاح")
        if user_id in timeout_tasks:
            del timeout_tasks[user_id]
    except Exception as e:
        logger.error(f"❌ خطأ في timeout_waiting_state للمستخدم {user_id}: {e}")
        if user_id in timeout_tasks:
            del timeout_tasks[user_id]

@router.callback_query(F.data == "user_manage_tasks")
async def manage_tasks_menu(callback: CallbackQuery):
    from aiogram.exceptions import TelegramBadRequest

    user_id = callback.from_user.id
    task_manager = UserTaskManager(user_id)
    tasks = task_manager.get_all_tasks()

    if not tasks:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إضافة مهمة إخبارية", callback_data="user_add_task_step1")],
            [InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")]
        ])

        try:
            await callback.message.edit_text(
                "📋 <b>المهام الإخبارية</b>\n\n"
                "ليس لديك أي مهام نشر حالياً.\n\n"
                "💡 لإضافة مهمة جديدة، اضغط على \"إضافة مهمة إخبارية\"",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await callback.answer()
        return

    keyboard_buttons = []

    for task_id, task in tasks.items():
        status_icon = "✅" if task.is_active else "⏸️"
        task_name = task.admin_task_name
        button_text = f"{status_icon} {task_name}"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"user_task_view:{task_id}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    try:
        await callback.message.edit_text(
            "📋 <b>المهام الإخبارية</b>\n\n"
            f"لديك <b>{len(tasks)}</b> مهمة نشر.\n\n"
            "اختر مهمة لعرض التفاصيل:",
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

@router.callback_query(F.data == "user_add_task_step1")
async def user_add_task_step1(callback: CallbackQuery, state: FSMContext):
    """الخطوة 1: اختيار المصدر الإخباري"""
    manager = ForwardingManager()
    all_tasks = manager.get_active_tasks()

    from subscription_manager import SubscriptionManager

    user_id = callback.from_user.id
    task_manager = UserTaskManager(user_id)
    sub_manager = SubscriptionManager(user_id)
    can_add = sub_manager.can_add_task(len(task_manager.get_all_tasks()))

    if not can_add:
        await callback.answer(
            "❌ وصلت للحد الأقصى من المهام المجانية (1 مهمة)\n\n⭐ قم ترقية حسابك لإضافة مهام غير محدودة!",
            show_alert=True
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
        ])
        await callback.message.edit_text(
            "⭐ <b>ترقية الحساب</b>\n\n"
            "لقد وصلت للحد الأقصى من المهام المجانية.\n\n"
            "قم بترقية حسابك للحصول على:\n"
            "• مهام نشر غير محدودة\n"
            "• جميع الفلاتر المتقدمة\n"
            "• ميزات التخصيص الكاملة",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return

    if not all_tasks:
        await callback.answer("❌ لا توجد مهام متاحة حالياً", show_alert=True)
        return

    text = """
📰 <b>إضافة مهمة نشر جديدة</b>

<b>الخطوة 1 من 2: اختر المصدر الإخباري</b>

اختر المصدر الإخباري الذي تريد النشر منه:
"""

    keyboard_buttons = []
    for task_id, task in all_tasks.items():
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📢 {task.name}",
                callback_data=f"user_select_admin_task_{task_id}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 إلغاء", callback_data="user_manage_tasks")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_select_admin_task_"))
async def user_select_admin_task(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """الخطوة 2: طلب رابط القناة من المستخدم"""
    task_id = int(callback.data.split("_")[4])

    manager = ForwardingManager()
    task = manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    await state.update_data(
        selected_admin_task_id=task_id,
        selected_admin_task_name=task.name
    )
    await state.set_state(UserTaskCreationStates.waiting_for_channel_link)

    # بدء timeout في الخلفية وحفظ مرجعه
    import asyncio
    timeout_task = asyncio.create_task(timeout_waiting_state(callback.from_user.id, state, bot, 300))  # 5 دقائق
    timeout_tasks[callback.from_user.id] = timeout_task
    logger.info(f"⏰ تم إنشاء timeout task للمستخدم {callback.from_user.id}")

    # الحصول على username البوت لإنشاء رابط إضافة كمشرف
    bot_info = await bot.get_me()
    bot_username = bot_info.username

    # إنشاء رابط مباشر لإضافة البوت كمشرف في القنوات والمجموعات مع جميع الصلاحيات
    add_bot_link = f"https://t.me/{bot_username}?startchannel&startgroup"

    text = f"""
📰 <b>إضافة مهمة نشر جديدة</b>

✅ تم اختيار المصدر: <b>{task.name}</b>

<b>الخطوة 2 من 2:</b> قم بتوجيه رسالة من القناة/المجموعة التي تريد النشر إليها إذا كانت خاصة، أو أرسل رابط القناة/المجموعة بالشكل التالي:

📝 <code>@channel_name</code>
📝 <code>t.me/channel_name</code>

💡 أو اضغط على الزر أدناه لاختيار قناة أو مجموعة مباشرة
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ أضف البوت كمشرف", url=add_bot_link)],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="user_cancel_add_task")]
    ])

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    await callback.answer()

@router.callback_query(F.data == "user_cancel_add_task")
async def user_cancel_add_task(callback: CallbackQuery, state: FSMContext):
    """إلغاء إضافة المهمة"""
    from channel_detection import users_adding_bot

    user_id = callback.from_user.id

    # إلغاء مهمة الـ timeout إن وجدت
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
        del timeout_tasks[user_id]
        logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} عند الإلغاء")

    # إزالة المستخدم من users_adding_bot إذا كان موجوداً
    if user_id in users_adding_bot:
        users_adding_bot.discard(user_id)
        logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot عند الإلغاء")

    await state.clear()
    await callback.answer("تم الإلغاء")
    await manage_tasks_menu(callback)

@router.message(UserTaskCreationStates.waiting_for_channel_link, F.chat_shared)
async def handle_chat_shared(message: Message, state: FSMContext, bot: Bot):
    """معالجة اختيار القناة عبر زر RequestChat"""
    from channel_detection import users_adding_bot

    user_id = message.from_user.id
    chat_shared = message.chat_shared

    logger.info(f"✅ تم استلام chat_shared من المستخدم {user_id}")
    logger.info(f"   request_id: {chat_shared.request_id}")
    logger.info(f"   chat_id: {chat_shared.chat_id}")

    # الحصول على بيانات FSM
    data = await state.get_data()
    admin_task_id = data.get('selected_admin_task_id')
    admin_task_name = data.get('selected_admin_task_name')

    if not admin_task_id or not admin_task_name:
        await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى من البداية.")
        await state.clear()
        return

    # إضافة المستخدم إلى مجموعة users_adding_bot (لتجاهل إشعار channel_detection)
    users_adding_bot.add(user_id)
    logger.info(f"📝 تم إضافة المستخدم {user_id} إلى users_adding_bot")

    channel_id = chat_shared.chat_id

    # إرسال رسالة انتظار
    wait_msg = await message.answer("⏳ جاري التحقق من القناة والصلاحيات...")

    try:
        # التحقق من القناة
        success, error_msg, channel_info = await ChannelVerification.verify_channel_for_task(
            bot, channel_id, user_id
        )

        await wait_msg.delete()

        if success and channel_info:
            # إلغاء مهمة الـ timeout
            if user_id in timeout_tasks:
                timeout_tasks[user_id].cancel()
                del timeout_tasks[user_id]
                logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} بعد نجاح إنشاء المهمة")

            # إنشاء المهمة مباشرة باستخدام الدالة المشتركة
            await create_task_directly(message, state, bot, admin_task_id, admin_task_name, channel_info)

        else:
            # فشل التحقق
            # إزالة المستخدم من المجموعة
            users_adding_bot.discard(user_id)

            await message.answer(
                f"❌ <b>فشل التحقق من القناة</b>\n\n"
                f"📋 <b>السبب:</b> {error_msg}\n\n"
                f"الرجاء التأكد من أن البوت مشرف في القناة مع صلاحية النشر.",
                parse_mode='HTML'
            )
            await state.clear()

    except Exception as e:
        logger.error(f"❌ خطأ في معالجة chat_shared: {e}", exc_info=True)

        # إزالة المستخدم من المجموعة في حالة الخطأ
        users_adding_bot.discard(user_id)

        try:
            await wait_msg.delete()
        except:
            pass
        await message.answer(f"❌ حدث خطأ أثناء معالجة القناة:\n{str(e)}")
        await state.clear()

@router.message(UserTaskCreationStates.waiting_for_channel_link)
async def process_channel_link(message: Message, state: FSMContext, bot: Bot):
    """معالجة رابط القناة المرسل من المستخدم أو رسالة موجهة من القناة"""
    user_id = message.from_user.id

    # التحقق من وجود رسالة موجهة من قناة
    if message.forward_from_chat and message.forward_from_chat.type in ['channel', 'supergroup']:
        channel_id = message.forward_from_chat.id
        channel_title = message.forward_from_chat.title
        channel_username = message.forward_from_chat.username

        logger.info(f"📨 استقبال رسالة موجهة من القناة {channel_id} ({channel_title}) من المستخدم {user_id}")

        # استخدام معلومات القناة المستخرجة من الرسالة الموجهة
        channel_input = str(channel_id)

        data = await state.get_data()
        admin_task_id = data.get('selected_admin_task_id')
        admin_task_name = data.get('selected_admin_task_name')

        if not admin_task_id or not admin_task_name:
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى من البداية.")
            await state.clear()
            return

        wait_msg = await message.answer("⏳ جاري التحقق من القناة...")

        # التحقق من صلاحيات القناة
        success, error_msg, channel_info = await ChannelVerification.verify_channel_for_task(
            bot, channel_id, user_id
        )

        await wait_msg.delete()

        if success and channel_info:
            # إلغاء مهمة الـ timeout
            if user_id in timeout_tasks:
                timeout_tasks[user_id].cancel()
                del timeout_tasks[user_id]
                logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} بعد نجاح إنشاء المهمة")

            await create_task_directly(message, state, bot, admin_task_id, admin_task_name, channel_info)
        else:
            # التحقق من أخطاء البوت
            bot_permission_errors = [
                "البوت ليس مشرفاً",
                "البوت لا يملك صلاحية",
                "البوت غير موجود",
                "member list is inaccessible",
                "خطأ في الوصول للقناة"
            ]

            is_bot_permission_error = any(error in error_msg for error in bot_permission_errors)

            if is_bot_permission_error:
                logger.info(f"🔧 استدعاء create_pending_code مع channel_id={channel_id}")
                await create_pending_code(message, state, bot, admin_task_id, admin_task_name, channel_input, channel_id)
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 إعادة المحاولة", callback_data=f"user_select_admin_task_{admin_task_id}")],
                    [InlineKeyboardButton(text="❌ إلغاء", callback_data="user_cancel_add_task")]
                ])
                await message.answer(
                    f"❌ <b>فشل التحقق من القناة</b>\n\n{error_msg}",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
        return

    # معالجة النص (الرابط أو المعرف)
    if not message.text:
        await message.answer("❌ يرجى إرسال رابط القناة أو توجيه رسالة من القناة.")
        return

    channel_input = message.text.strip()
    logger.info(f"🔍 استقبال رابط من المستخدم {user_id}: {channel_input}")

    data = await state.get_data()
    admin_task_id = data.get('selected_admin_task_id')
    admin_task_name = data.get('selected_admin_task_name')

    logger.info(f"📊 FSM Data: task_id={admin_task_id}, task_name={admin_task_name}")

    if not admin_task_id or not admin_task_name:
        await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى من البداية.")
        await state.clear()
        return

    wait_msg = await message.answer("⏳ جاري التحقق من القناة...")

    if ChannelVerification.is_invite_link(channel_input):
        logger.info(f"رابط دعوة خاص تم اكتشافه من المستخدم {user_id}")
        await wait_msg.delete()
        await create_pending_code(message, state, bot, admin_task_id, admin_task_name, channel_input)
        return

    channel_id = await ChannelVerification.extract_channel_id(bot, channel_input)

    if not channel_id:
        await wait_msg.delete()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 إعادة المحاولة", callback_data=f"user_select_admin_task_{admin_task_id}")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="user_cancel_add_task")]
        ])
        await message.answer(
            "❌ <b>فشل في التعرف على القناة</b>\n\n"
            "الرجاء التأكد من:\n"
            "• صحة الرابط أو username\n"
            "• أن القناة عامة أو أنك أرسلت رابط دعوة صحيح\n"
            "• أن البوت عضو في القناة إذا كانت خاصة",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return

    success, error_msg, channel_info = await ChannelVerification.verify_channel_for_task(
        bot, channel_id, user_id
    )

    await wait_msg.delete()

    if success and channel_info:
        # إلغاء مهمة الـ timeout
        if user_id in timeout_tasks:
            timeout_tasks[user_id].cancel()
            del timeout_tasks[user_id]
            logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} بعد نجاح إنشاء المهمة")

        await create_task_directly(message, state, bot, admin_task_id, admin_task_name, channel_info)
    else:
        # التحقق من أخطاء البوت (ليس مشرفاً، لا يملك صلاحيات، غير موجود)
        bot_permission_errors = [
            "البوت ليس مشرفاً",
            "البوت لا يملك صلاحية",
            "البوت غير موجود",
            "member list is inaccessible",  # خطأ تيليجرام عندما البوت غير مشرف
            "خطأ في الوصول للقناة"
        ]

        is_bot_permission_error = any(error in error_msg for error in bot_permission_errors)

        if is_bot_permission_error:
            # البوت غير مشرف - نطلب من المستخدم إضافته
            logger.info(f"🔧 استدعاء create_pending_code مع channel_id={channel_id}")
            await create_pending_code(message, state, bot, admin_task_id, admin_task_name, channel_input, channel_id)
        else:
            # خطأ آخر (المستخدم ليس مشرفاً، القناة غير موجودة، الخ)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 إعادة المحاولة", callback_data=f"user_select_admin_task_{admin_task_id}")],
                [InlineKeyboardButton(text="❌ إلغاء", callback_data="user_cancel_add_task")]
            ])
            await message.answer(
                f"❌ <b>فشل التحقق من القناة</b>\n\n{error_msg}",
                parse_mode='HTML',
                reply_markup=keyboard
            )

async def create_task_directly(message: Message, state: FSMContext, bot: Bot,
                               admin_task_id: int, admin_task_name: str, channel_info: Dict):
    """إنشاء المهمة مباشرة بعد التحقق من الصلاحيات"""
    from channel_detection import users_adding_bot

    user_id = message.from_user.id
    channel_id = channel_info['id']
    channel_title = channel_info['title']

    # إزالة المستخدم من users_adding_bot
    if user_id in users_adding_bot:
        users_adding_bot.discard(user_id)
        logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot عند إنشاء المهمة")

    task_manager = UserTaskManager(user_id)

    # التحقق من عدم وجود نفس المهمة
    if task_manager.task_exists(admin_task_id, channel_id):
        await state.clear()
        await message.answer(
            "⚠️ <b>المهمة موجودة مسبقاً!</b>\n\n"
            f"لديك مهمة نشطة بالفعل لنفس المصدر والهدف.",
            parse_mode='HTML'
        )
        return

    # إنشاء اسم المهمة بصيغة: اسم مهمة المشرف -> اسم قناة الهدف
    channel_title = channel_info.get('title', 'قناة')
    custom_task_name = f"{admin_task_name} -> {channel_title}"

    # إنشاء المهمة
    user_task_id = task_manager.add_task(
        admin_task_id=admin_task_id,
        admin_task_name=custom_task_name,
        target_channel=channel_info
    )

    channel_manager = UserChannelManager(user_id)
    channel_manager.add_channel(
        channel_id=channel_info['id'],
        title=channel_info['title'],
        username=channel_info.get('username'),
        chat_type=channel_info.get('type', 'channel')
    )

    fm = ForwardingManager()
    all_tasks = fm.get_all_tasks()
    admin_task = all_tasks.get(admin_task_id)

    if admin_task:
        target_channel = {
            'id': channel_info['id'],
            'title': channel_info['title'],
            'username': channel_info.get('username'),
            'user_id': user_id,
            'user_task_id': user_task_id
        }
        admin_task.target_channels.append(target_channel)
        fm.save_tasks(all_tasks)
        logger.info(f"✅ تم إضافة القناة {channel_info['id']} للمهمة الإدارية #{admin_task_id}")

        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()
            logger.info(f"🔄 تم إعادة تحميل النظام المتوازي بعد إضافة مهمة جديدة")

    await state.clear()

    # إرسال إشعار إنشاء المهمة
    from notification_manager import notification_manager
    from stats_manager import stats_manager
    try:
        user_name = message.from_user.first_name
        task_name = f"{admin_task_name} → {channel_info['title']}"
        await notification_manager.notify_task_created(
            message.bot,
            user_id,
            user_name,
            task_name,
            admin_task_name,
            channel_info['title']
        )
        stats_manager.increment_tasks(is_active=True)
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار إنشاء المهمة: {e}")

    # الحصول على عنوان المصدر
    import html
    source_title = "غير محدد"
    if admin_task and admin_task.source_channels:
        source_title = admin_task.source_channels[0].get('title', 'غير محدد')

    # تنظيف النصوص من HTML entities الخاصة
    clean_source_title = html.escape(source_title)
    clean_channel_title = html.escape(channel_info['title'])

    # عرض لوحة التحكم الكاملة مباشرة
    from subscription_manager import SubscriptionManager
    sub_manager = SubscriptionManager(user_id)
    is_premium = sub_manager.is_premium()
    lock_icon = "" if is_premium else " 🔒"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏸️ تعطيل", callback_data=f"user_task_toggle:{user_task_id}")],
        [InlineKeyboardButton(text=f"🎬 فلاتر الوسائط{lock_icon}", callback_data=f"settings_media:{user_task_id}"),
         InlineKeyboardButton(text=f"🔘 أزرار إنلاين{lock_icon}", callback_data=f"settings_buttons:{user_task_id}")],
        [InlineKeyboardButton(text=f"📝 رأس الرسالة{lock_icon}", callback_data=f"settings_header:{user_task_id}"),
         InlineKeyboardButton(text=f"📝 ذيل الرسالة{lock_icon}", callback_data=f"settings_footer:{user_task_id}")],
        [InlineKeyboardButton(text=f"✅ قائمة بيضاء{lock_icon}", callback_data=f"settings_whitelist:{user_task_id}"),
         InlineKeyboardButton(text=f"🚫 قائمة سوداء{lock_icon}", callback_data=f"settings_blacklist:{user_task_id}")],
        [InlineKeyboardButton(text=f"🔄 الاستبدالات{lock_icon}", callback_data=f"settings_replacements:{user_task_id}"),
         InlineKeyboardButton(text=f"🔗 إدارة الروابط{lock_icon}", callback_data=f"settings_links:{user_task_id}")],
        [InlineKeyboardButton(text=f"🚫 فلتر الأزرار{lock_icon}", callback_data=f"settings_button_filter:{user_task_id}"),
         InlineKeyboardButton(text=f"↪️ فلتر الموجهة{lock_icon}", callback_data=f"settings_forwarded:{user_task_id}")],
        [InlineKeyboardButton(text=f"🌐 فلتر اللغة{lock_icon}", callback_data=f"settings_language:{user_task_id}"),
         InlineKeyboardButton(text=f"🎨 تنسيق النص{lock_icon}", callback_data=f"text_format_menu_{user_task_id}")],
        [InlineKeyboardButton(text=f"📌 التثبيت التلقائي{lock_icon}", callback_data=f"settings_auto_pin:{user_task_id}"),
         InlineKeyboardButton(text=f"🔗 معاينة الروابط{lock_icon}", callback_data=f"settings_link_preview:{user_task_id}")],
        [InlineKeyboardButton(text=f"💬 الحفاظ على الردود{lock_icon}", callback_data=f"settings_reply_preservation:{user_task_id}"),
         InlineKeyboardButton(text=f"🗑️ الحذف التلقائي{lock_icon}", callback_data=f"settings_auto_delete:{user_task_id}")],
        [InlineKeyboardButton(text=f"📅 فلتر الأيام{lock_icon}", callback_data=f"settings_day_filter:{user_task_id}"),
         InlineKeyboardButton(text=f"🕒 فلتر الساعات{lock_icon}", callback_data=f"settings_hour_filter:{user_task_id}")],
        [InlineKeyboardButton(text=f"🌍 ترجمة النصوص{lock_icon}", callback_data=f"settings_translation:{user_task_id}"),
         InlineKeyboardButton(text=f"📏 حدود الأحرف{lock_icon}", callback_data=f"settings_character_limit:{user_task_id}")],
        [InlineKeyboardButton(text=f"📊 إحصائيات المهمة", callback_data=f"settings_task_stats:{user_task_id}")],
        [InlineKeyboardButton(text="🧪 اختبار المهمة", callback_data=f"test_task:{user_task_id}"),
         InlineKeyboardButton(text="🗑️ حذف المهمة", callback_data=f"user_task_delete:{user_task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
    ])

    success_message = (
        f"✅ <b>تم إنشاء المهمة بنجاح!</b>\n\n"
        f"📊 <b>الحالة:</b> 🟢 نشطة\n\n"
        f"📍 <b>من → إلى:</b>\n"
        f"  📢 <b>المصدر:</b> {clean_source_title}\n"
        f"  📣 <b>الهدف:</b> {clean_channel_title}\n\n"
        f"🎉 سيتم نسخ المحتوى تلقائياً من المصدر إلى قناتك!\n\n"
        f"💡 يمكنك التحكم في المهمة وتخصيص إعداداتها من الأزرار أدناه:"
    )

    # حذف اللوحة السابقة وإرسال الجديدة
    sent_message = await message.answer(
        success_message,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    # حفظ معرف الرسالة الجديدة
    await delete_last_panel_and_save_new(bot, user_id, sent_message.message_id)

async def create_pending_code(message: Message, state: FSMContext, bot: Bot,
                              admin_task_id: int, admin_task_name: str,
                              channel_input: str, channel_id: int = None):
    """حفظ المهمة في FSM وطلب إضافة البوت"""
    user_id = message.from_user.id

    # حفظ البيانات في FSM
    await state.update_data(
        selected_admin_task_id=admin_task_id,
        selected_admin_task_name=admin_task_name,
        channel_input=channel_input,
        channel_id=channel_id
    )
    await state.set_state(UserTaskCreationStates.waiting_for_channel_addition)

    logger.info(f"✅ تم حفظ المهمة المعلقة في FSM للمستخدم {user_id}:")
    logger.info(f"   - task_id: {admin_task_id}")
    logger.info(f"   - task_name: {admin_task_name}")
    logger.info(f"   - channel_id: {channel_id}")
    logger.info(f"   - channel_input: {channel_input}")
    logger.info(f"   - state: UserTaskCreationStates.waiting_for_channel_addition")

    # حفظ أيضاً في PendingTasksManager كنسخة احتياطية في حال انتهت FSM state
    # هذا يضمن إمكانية إكمال المهمة حتى لو انتهت FSM بعد 5 دقائق
    if channel_id:
        pending_manager = PendingTasksManager()
        code = pending_manager.create_pending_task(
            user_id=user_id,
            channel_id=channel_id,
            admin_task_id=admin_task_id,
            admin_task_name=admin_task_name
        )
        if code:
            logger.info(f"✅ تم حفظ المهمة أيضاً في PendingTasksManager - code={code}")
        else:
            logger.warning(f"⚠️ فشل حفظ المهمة في PendingTasksManager")

    bot_info = await bot.get_me()
    bot_username = bot_info.username
    add_bot_link = f"https://t.me/{bot_username}?startchannel&startgroup"

    text = f"""
⏳ <b>البوت في وضع الانتظار</b>

✅ المصدر المختار: <b>{admin_task_name}</b>

🔄 <b>الحالة:</b> في انتظار إضافة البوت كمشرف في القناة/المجموعة

📝 <b>لإتمام إضافة المهمة، اتبع الخطوات:</b>

1️⃣ اضغط على زر <b>"➕ أضف البوت كمشرف"</b> أدناه
2️⃣ اختر قناتك أو مجموعتك من القائمة
3️⃣ امنح البوت جميع الصلاحيات (سيتم تحديدها تلقائياً)

4️⃣ بعد إضافة البوت، سيتم الكشف التلقائي وإنشاء المهمة فوراً! 🎉

⏰ <b>مدة الانتظار:</b> 5 دقائق

💡 <b>ملاحظة:</b> تأكد من أنك مشرف في القناة/المجموعة أيضاً
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ أضف البوت كمشرف", url=add_bot_link)],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="user_cancel_add_task")]
    ])

    # حذف اللوحة السابقة وإرسال الجديدة
    sent_message = await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

    # حفظ معرف الرسالة الجديدة
    await delete_last_panel_and_save_new(bot, user_id, sent_message.message_id)

@router.callback_query(F.data == "how_to_add_task")
async def how_to_add_task_callback(callback: CallbackQuery):
    manager = ForwardingManager()
    all_tasks = manager.get_active_tasks()

    text = """
📝 <b>كيفية إضافة مهمة نشر جديدة</b>

<b>📌 الخطوات البسيطة:</b>

1️⃣ <b>أضف البوت كمشرف لقناتك</b>
   • افتح قناتك أو مجموعتك
   • اذهب إلى إعدادات المشرفين
   • أضف البوت كمشرف

2️⃣ <b>اختر اسم المهمة من القائمة أدناه</b>

"""

    if not all_tasks:
        text += "❌ <b>لا توجد مهام نشطة حالياً</b>\n"
        text += "تواصل مع المشرف لإنشاء مهام جديدة."
    else:
        text += "<b>📰 المهام المتاحة حالياً:</b>\n\n"

        for task_id, task in all_tasks.items():
            text += f"▫️ <b>{task.name}</b>\n"

            if task.source_channels:
                source_titles = ", ".join([ch.get('title', 'قناة')[:15] for ch in task.source_channels[:2]])
                if len(task.source_channels) > 2:
                    source_titles += f" +{len(task.source_channels) - 2}"
                text += f"   📢 المصدر: {source_titles}\n"

            text += f"   💬 <b>أرسل في قناتك:</b>\n"
            text += f"   <code>تفعيل {task.name}</code>\n\n"

        text += "\n<b>3️⃣ افتح قناتك وأرسل الأمر</b>\n"
        text += "• انسخ الأمر من الأعلى\n"
        text += "• الصقه وأرسله في قناتك\n\n"

        text += "<b>4️⃣ استلم التأكيد</b>\n"
        text += "• ستصلك رسالة تأكيد في الخاص\n"
        text += "• سيبدأ النشر التلقائي فوراً!"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_task_view:"))
async def view_task_details(callback: CallbackQuery):
    from aiogram.exceptions import TelegramBadRequest
    from subscription_manager import SubscriptionManager
    import html

    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    task_manager = UserTaskManager(user_id)
    task = task_manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة", show_alert=True)
        return

    status_text = "🟢 نشطة" if task.is_active else "⏸️ معطلة"

    # استخدام اسم المهمة من قاعدة البيانات
    task_name = str(task.admin_task_name)
    target_title = str(task.target_channel.get('title', 'غير محدد') if task.target_channel else 'غير محدد')
    created_date = str(task.created_at[:10] if task.created_at else 'غير محدد')

    text = (
        f"📰 <b>تفاصيل المهمة</b>\n\n"
        f"📊 <b>الحالة:</b> {status_text}\n\n"
        f"📍 <b>اسم المهمة:</b> {html.escape(task_name)}\n"
        f"📣 <b>القناة:</b> {html.escape(target_title)}\n\n"
        f"📅 <b>تاريخ الإنشاء:</b> {created_date}"
    )

    toggle_text = "▶️ تفعيل" if not task.is_active else "⏸️ تعطيل"

    # التحقق من الاشتراك المدفوع
    sub_manager = SubscriptionManager(user_id)
    is_premium = sub_manager.is_premium()
    lock_icon = "" if is_premium else " 🔒"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"user_task_toggle:{task_id}")],
        [InlineKeyboardButton(text=f"🎬 فلاتر الوسائط{lock_icon}", callback_data=f"settings_media:{task_id}"),
         InlineKeyboardButton(text=f"🔘 أزرار إنلاين{lock_icon}", callback_data=f"settings_buttons:{task_id}")],
        [InlineKeyboardButton(text=f"📝 رأس الرسالة{lock_icon}", callback_data=f"settings_header:{task_id}"),
         InlineKeyboardButton(text=f"📝 ذيل الرسالة{lock_icon}", callback_data=f"settings_footer:{task_id}")],
        [InlineKeyboardButton(text=f"✅ قائمة بيضاء{lock_icon}", callback_data=f"settings_whitelist:{task_id}"),
         InlineKeyboardButton(text=f"🚫 قائمة سوداء{lock_icon}", callback_data=f"settings_blacklist:{task_id}")],
        [InlineKeyboardButton(text=f"🔄 الاستبدالات{lock_icon}", callback_data=f"settings_replacements:{task_id}"),
         InlineKeyboardButton(text=f"🔗 إدارة الروابط{lock_icon}", callback_data=f"settings_links:{task_id}")],
        [InlineKeyboardButton(text=f"🚫 فلتر الأزرار{lock_icon}", callback_data=f"settings_button_filter:{task_id}"),
         InlineKeyboardButton(text=f"↪️ فلتر الموجهة{lock_icon}", callback_data=f"settings_forwarded:{task_id}")],
        [InlineKeyboardButton(text=f"🌐 فلتر اللغة{lock_icon}", callback_data=f"settings_language:{task_id}"),
         InlineKeyboardButton(text=f"🎨 تنسيق النص{lock_icon}", callback_data=f"text_format_menu_{task_id}")],
        [InlineKeyboardButton(text=f"📌 التثبيت التلقائي{lock_icon}", callback_data=f"settings_auto_pin:{task_id}"),
         InlineKeyboardButton(text=f"🔗 معاينة الروابط{lock_icon}", callback_data=f"settings_link_preview:{task_id}")],
        [InlineKeyboardButton(text=f"💬 الحفاظ على الردود{lock_icon}", callback_data=f"settings_reply_preservation:{task_id}"),
         InlineKeyboardButton(text=f"🗑️ الحذف التلقائي{lock_icon}", callback_data=f"settings_auto_delete:{task_id}")],
        [InlineKeyboardButton(text=f"📅 فلتر الأيام{lock_icon}", callback_data=f"settings_day_filter:{task_id}"),
         InlineKeyboardButton(text=f"🕒 فلتر الساعات{lock_icon}", callback_data=f"settings_hour_filter:{task_id}")],
        [InlineKeyboardButton(text=f"🌍 ترجمة النصوص{lock_icon}", callback_data=f"settings_translation:{task_id}"),
         InlineKeyboardButton(text=f"📏 حدود الأحرف{lock_icon}", callback_data=f"settings_character_limit:{task_id}")],
        [InlineKeyboardButton(text=f"📊 إحصائيات المهمة", callback_data=f"settings_task_stats:{task_id}")],
        [InlineKeyboardButton(text="🧪 اختبار المهمة", callback_data=f"test_task:{task_id}"),
         InlineKeyboardButton(text="🗑️ حذف المهمة", callback_data=f"user_task_delete:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
    ])

    try:
        await callback.message.edit_text(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            #الرسالة لم تتغير، فقط نجيب على الاستعلام
            pass
        else:
            raise

    await callback.answer()

@router.callback_query(F.data.startswith("user_task_toggle:"))
async def toggle_task(callback: CallbackQuery, bot: Bot):
    from subscription_manager import SubscriptionManager

    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    task_manager = UserTaskManager(user_id)
    task = task_manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة", show_alert=True)
        return

    # إذا كانت المهمة معطلة والمستخدم يريد تفعيلها
    if not task.is_active:
        # 1. التحقق من الاشتراك
        sub_manager = SubscriptionManager(user_id)
        active_tasks = task_manager.get_active_tasks()
        active_count = len(active_tasks)

        if not sub_manager.can_add_task(active_count):
            await callback.answer(
                "❌ وصلت للحد الأقصى من المهام النشطة (1 مهمة)\n\n⭐ قم ترقية حسابك لتفعيل مهام غير محدودة!",
                show_alert=True
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"user_task_view:{task_id}")]
            ])

            await callback.message.edit_text(
                "⭐ <b>ترقية الحساب</b>\n\n"
                "لقد وصلت للحد الأقصى من المهام النشطة.\n\n"
                "قم بترقية حسابك للحصول على:\n"
                "• مهام نشر غير محدودة ✅\n"
                "• جميع الفلاتر المتقدمة 🎯\n"
                "• ميزات التخصيص الكاملة 🎨\n\n"
                "💡 يمكنك تعطيل مهمة أخرى لتفعيل هذه المهمة",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return

        # 2. التحقق من صلاحيات البوت في القناة
        from channel_verification import ChannelVerification
        target_channel_id = task.target_channel['id']

        success, error_msg, channel_info = await ChannelVerification.verify_channel_for_task(
            bot, target_channel_id, user_id
        )

        if not success:
            await callback.answer(
                f"❌ لا يمكن تفعيل المهمة!\n\n{error_msg}",
                show_alert=True
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"user_task_view:{task_id}")]
            ])

            await callback.message.edit_text(
                f"⚠️ <b>فشل تفعيل المهمة</b>\n\n"
                f"{error_msg}\n\n"
                f"💡 تأكد من:\n"
                f"• البوت مشرف في القناة\n"
                f"• لديه صلاحية النشر والتعديل",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return

    new_status = task_manager.toggle_task(task_id)

    # تحديث المهمة الإدارية بناءً على حالة التفعيل/التعطيل
    from forwarding_manager import ForwardingManager
    fm = ForwardingManager()
    all_tasks = fm.get_all_tasks()
    admin_task = all_tasks.get(task.admin_task_id)

    if admin_task:
        modified = False

        if new_status:
            # التفعيل: إضافة القناة للمهمة الإدارية إذا لم تكن موجودة
            target_exists = any(
                target['id'] == task.target_channel['id'] and
                target.get('user_id') == user_id and
                target.get('user_task_id') == task_id
                for target in admin_task.target_channels
            )

            if not target_exists:
                target_channel = {
                    'id': task.target_channel['id'],
                    'title': task.target_channel['title'],
                    'username': task.target_channel.get('username'),
                    'user_id': user_id,
                    'user_task_id': task_id
                }
                admin_task.target_channels.append(target_channel)
                logger.info(f"✅ تم إضافة القناة {task.target_channel['id']} للمهمة الإدارية #{task.admin_task_id}")
                modified = True
        else:
            # التعطيل: حذف القناة من المهمة الإدارية
            initial_count = len(admin_task.target_channels)
            admin_task.target_channels = [
                target for target in admin_task.target_channels
                if not (target['id'] == task.target_channel['id'] and
                       target.get('user_id') == user_id and
                       target.get('user_task_id') == task_id)
            ]

            removed_count = initial_count - len(admin_task.target_channels)
            if removed_count > 0:
                logger.info(f"⏸️ تم حذف القناة {task.target_channel['id']} من المهمة الإدارية #{task.admin_task_id}")
                modified = True

        # حفظ التعديلات وإعادة تحميل النظام
        if modified:
            fm.save_tasks(all_tasks)

            import parallel_forwarding_system
            if parallel_forwarding_system.parallel_system:
                await parallel_forwarding_system.parallel_system.reload_tasks()
                logger.info(f"🔄 تم إعادة تحميل النظام المتوازي بعد تغيير حالة المهمة")

    if new_status is None: # Handle cases where toggle_task might return None on error
        await callback.answer("❌ حدث خطأ أثناء تغيير حالة المهمة", show_alert=True)
        return

    status_text = "تفعيل" if new_status else "تعطيل"
    await callback.answer(f"✅ تم {status_text} المهمة", show_alert=True)

    from notification_manager import notification_manager
    from stats_manager import stats_manager
    try:
        user_name = callback.from_user.first_name
        # Get admin_task name again in case it was None initially
        admin_task_name_for_notif = 'غير محدد'
        if admin_task:
            admin_task_name_for_notif = admin_task.name
        task_name = f"{admin_task_name_for_notif} → {task.target_channel.get('title', 'غير محدد')}"
        await notification_manager.notify_task_toggled(
            bot,
            user_id,
            user_name,
            task_name,
            new_status
        )
        stats_manager.toggle_task(not new_status, new_status)
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار تغيير حالة المهمة: {e}")

    await view_task_details(callback)


@router.callback_query(F.data.startswith("user_task_delete:"))
async def delete_task_confirmation(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"user_task_delete_confirm_{task_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data=f"user_task_view:{task_id}")
        ]
    ])

    await callback.message.edit_text(
        "⚠️ <b>تأكيد الحذف</b>\n\n"
        "هل أنت متأكد من حذف هذه المهمة؟\n"
        "لن يتم نسخ المحتوى إلى قناتك بعد الحذف.",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("user_task_delete_confirm_"))
async def confirm_delete_user_task(callback: CallbackQuery, bot: Bot):
    task_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    task_manager = UserTaskManager(user_id)
    task = task_manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    # حفظ معلومات المهمة قبل الحذف
    target_channel_id = task.target_channel['id']
    admin_task_id = task.admin_task_id

    # حفظ اسم المهمة لل notification
    from forwarding_manager import ForwardingManager
    fm_temp = ForwardingManager()
    all_tasks_temp = fm_temp.get_all_tasks()
    admin_task_temp = all_tasks_temp.get(admin_task_id)
    task_name_for_notif = f"{admin_task_temp.name if admin_task_temp else 'غير محدد'} → {task.target_channel.get('title', 'غير محدد')}"
    was_active = task.is_active

    # حذف مهمة المستخدم
    task_manager.delete_task(task_id)

    # إرسال إشعار الحذف
    from notification_manager import notification_manager
    from stats_manager import stats_manager
    try:
        user_name = callback.from_user.first_name
        await notification_manager.notify_task_deleted(
            bot,
            user_id,
            user_name,
            task_name_for_notif
        )
        stats_manager.decrement_tasks(was_active)
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار حذف المهمة: {e}")

    # حذف ملف إعدادات المهمة
    import os
    from config import USERS_DATA_DIR
    settings_file = os.path.join(USERS_DATA_DIR, str(user_id), f'task_{task_id}_settings.json')
    if os.path.exists(settings_file):
        try:
            os.remove(settings_file)
            logger.info(f"🗑️ تم حذف ملف الإعدادات: {settings_file}")
        except Exception as e:
            logger.error(f"❌ خطأ في حذف ملف الإعدادات: {e}")

    # حذف معلومات القناة من user_channels
    from user_channel_manager import UserChannelManager
    channel_manager = UserChannelManager(user_id)
    channel_manager.remove_channel(target_channel_id)
    logger.info(f"🗑 تم حذف معلومات القناة {target_channel_id} من ملفات المستخدم {user_id}")

    # حذف القناة من المهمة الإدارية
    from forwarding_manager import ForwardingManager
    fm = ForwardingManager()
    all_tasks = fm.get_all_tasks()
    admin_task = all_tasks.get(admin_task_id)

    if admin_task:
        # حذف جميع التكرارات للهدف بنفس المستخدم
        initial_count = len(admin_task.target_channels)
        admin_task.target_channels = [
            target for target in admin_task.target_channels
            if not (target['id'] == task.target_channel['id'] and
                   target.get('user_id') == user_id)
        ]

        removed_count = initial_count - len(admin_task.target_channels)
        if removed_count > 0:
            logger.info(f"🗑 تم حذف {removed_count} هدف مكرر من المهمة الإدارية #{admin_task_id}")

        fm.save_tasks(all_tasks)

        # إعادة تحميل النظام المتوازي
        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()
            logger.info(f"🔄 تم حذف قناة المستخدم {user_id} من المهمة #{admin_task_id} وإعادة تحميل النظام")

    await callback.answer("✅ تم حذف المهمة بنجاح!", show_alert=True)

    # العودة لقائمة المهام
    tasks = task_manager.get_all_tasks()

    if not tasks:
        text = "📋 <b>لا توجد مهام حالياً</b>\n\nلإضافة مهمة جديدة، اضغط على \"إضافة مهمة إخبارية\" من القائمة الرئيسية."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")]
        ])
    else:
        text = "📋 <b>مهام النشر الإخبارية</b>\n\n"
        keyboard_buttons = []

        for tid, t in tasks.items():
            status = "🟢" if t.is_active else "🔴"
            source_title = t.source_channel.get('title', 'غير محدد') if t.source_channel else 'غير محدد'
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {source_title} → {t.target_channel['title']}",
                    callback_data=f"user_task_view:{tid}"
                )
            ])

        keyboard_buttons.append([InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "user_back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "show_my_channels")
async def show_channels_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    channel_manager = UserChannelManager(user_id)
    channels = channel_manager.get_all_channels()

    if not channels:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")]
        ])

        await callback.message.edit_text(
            "📢 <b>قنواتي</b>\n\n"
            "ليس لديك أي قنوات محفوظة حالياً.\n\n"
            "عند إضافة البوت كمشرف لأي قناة، سيتم حفظها تلقائياً.",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await callback.answer()
        return

    text = "📢 <b>قنواتي المحفوظة</b>\n\n"

    for channel_id, channel in channels.items():
        text += f"• <b>{channel['title']}</b>\n"
        text += f"  🆔 <code>{channel_id}</code>\n"
        text += f"  📝 النوع: {channel['type']}\n"
        if channel.get('username'):
            text += f"  🔗 @{channel['username']}\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "show_system_status")
async def show_status_callback(callback: CallbackQuery):
    import parallel_forwarding_system

    if not parallel_forwarding_system.parallel_system:
        await callback.answer("❌ النظام المتوازي غير مفعّل!", show_alert=True)
        return

    stats = parallel_forwarding_system.parallel_system.get_stats()

    text = "📊 <b>حالة النظام</b>\n\n"
    text += f"✅ البوت يعمل بشكل صحيح\n"
    text += f"📥 حجم القائمة العامة: {stats['global_queue_size']}\n"
    text += f"🔄 عدد Global Workers: {stats['num_global_workers']}\n"
    text += f"✅ عدد المهام النشطة: {stats['num_active_tasks']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_start")
async def back_to_start_menu(callback: CallbackQuery, state: FSMContext):
    from config import ADMIN_ID
    from channel_detection import users_adding_bot

    user_id = callback.from_user.id

    # إغلاق أي FSM state مفتوح
    await state.clear()

    # إلغاء مهمة timeout إن وجدت
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
        del timeout_tasks[user_id]
        logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} عند العودة للقائمة الرئيسية")

    # إزالة المستخدم من users_adding_bot إن وجد
    if user_id in users_adding_bot:
        users_adding_bot.discard(user_id)
        logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot عند العودة للقائمة الرئيسية")

    is_admin = ADMIN_ID != 0 and user_id == ADMIN_ID

    if is_admin:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 إدارة المهام الإخبارية", callback_data="user_manage_tasks")],
            [InlineKeyboardButton(text="📢 قنواتي", callback_data="show_my_channels")],
            [InlineKeyboardButton(text="⚙️ مهام التوجيه (مشرف)", callback_data="fwd_list")],
            [InlineKeyboardButton(text="📊 حالة النظام", callback_data="show_system_status")]
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
            [InlineKeyboardButton(text="📰 المصادر المتاحة", callback_data="available_sources")],
            [InlineKeyboardButton(text="⭐ اشتراكي", callback_data="my_subscription")],
            [InlineKeyboardButton(text="👨‍💻 مطور البوت", url="https://t.me/akm100ye")],
            [InlineKeyboardButton(text="❓ مساعدة", callback_data="help_menu")]
        ])

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



@router.callback_query(F.data.startswith("choose_source_for_channel:"))
async def choose_source_for_channel(callback: CallbackQuery, bot: Bot):
    """عرض قائمة مهام المشرف للاختيار منها لقناة معينة"""
    user_id = callback.from_user.id
    channel_id = int(callback.data.split(":")[1])

    # التحقق من أن القناة موجودة
    channel_manager = UserChannelManager(user_id)
    if not channel_manager.channel_exists(channel_id):
        await callback.answer("❌ القناة غير موجودة!", show_alert=True)
        return

    channel_info = channel_manager.get_channel(channel_id)

    # التحقق من الاشتراك
    from subscription_manager import SubscriptionManager
    task_manager = UserTaskManager(user_id)
    sub_manager = SubscriptionManager(user_id)
    can_add = sub_manager.can_add_task(len(task_manager.get_all_tasks()))

    if not can_add:
        await callback.answer(
            "❌ وصلت للحد الأقصى من المهام المجانية (1 مهمة)\n\n⭐ قم ترقية حسابك لإضافة مهام غير محدودة!",
            show_alert=True
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
        ])
        await callback.message.edit_text(
            "⭐ <b>ترقية الحساب</b>\n\n"
            "لقد وصلت للحد الأقصى من المهام المجانية.\n\n"
            "قم بترقية حسابك للحصول على:\n"
            "• مهام نشر غير محدودة\n"
            "• جميع الفلاتر المتقدمة\n"
            "• ميزات التخصيص الكاملة",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return

    # الحصول على مهام المشرف النشطة
    manager = ForwardingManager()
    all_tasks = manager.get_active_tasks()

    if not all_tasks:
        await callback.answer("❌ لا توجد مهام متاحة حالياً", show_alert=True)
        return

    # إنشاء الأزرار
    keyboard_buttons = []

    text = f"""
📰 <b>اختر مصدر النشر</b>

📢 القناة: <b>{channel_info.get('title', 'غير معروف')}</b>

اختر المصدر الإخباري الذي تريد النشر منه:
"""

    for task_id, task in all_tasks.items():
        # التحقق من أن المهمة غير مضافة مسبقاً
        task_exists = task_manager.task_exists(task_id, channel_id)

        source_info = ""
        if task.source_channels:
            source_titles = ", ".join([ch.get('title', 'قناة')[:15] for ch in task.source_channels[:2]])
            if len(task.source_channels) > 2:
                source_titles += f" +{len(task.source_channels) - 2}"
            source_info = f" ({source_titles})"

        button_prefix = "✅ " if task_exists else "📢 "
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{button_prefix}{task.name}{source_info}",
                callback_data=f"select_task_for_channel:{task_id}:{channel_id}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_task_for_channel:"))
async def select_task_for_channel(callback: CallbackQuery, bot: Bot):
    """إنشاء مهمة جديدة من مهمة المشرف إلى قناة المستخدم"""
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        admin_task_id = int(parts[1])
        channel_id = int(parts[2])

        logger.info(f"🔍 بدء إنشاء مهمة: user={user_id}, admin_task={admin_task_id}, channel={channel_id}")

        # الحصول على معلومات المهمة الإدارية
        manager = ForwardingManager()
        admin_task = manager.get_task(admin_task_id)

        if not admin_task:
            logger.error(f"❌ المهمة الإدارية {admin_task_id} غير موجودة")
            await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
            return

        # الحصول على معلومات القناة
        channel_manager = UserChannelManager(user_id)
        if not channel_manager.channel_exists(channel_id):
            logger.error(f"❌ القناة {channel_id} غير موجودة للمستخدم {user_id}")
            await callback.answer("❌ القناة غير موجودة!", show_alert=True)
            return

        channel_info = channel_manager.get_channel(channel_id)
        if not channel_info:
            logger.error(f"❌ فشل الحصول على معلومات القناة {channel_id}")
            await callback.answer("❌ فشل الحصول على معلومات القناة!", show_alert=True)
            return

        logger.info(f"📢 معلومات القناة: {channel_info.get('title', 'غير معروف')}")

        # التحقق من أن المهمة غير موجودة مسبقاً
        task_manager = UserTaskManager(user_id)
        if task_manager.task_exists(admin_task_id, channel_id):
            logger.warning(f"⚠️ المهمة موجودة مسبقاً: admin_task={admin_task_id}, channel={channel_id}")
            await callback.answer("⚠️ هذه المهمة مفعلة بالفعل لهذه القناة!", show_alert=True)
            return

        # التحقق من صلاحيات البوت في القناة
        bot_has_perms, bot_error = await ChannelVerification.check_bot_permissions(bot, channel_id)

        if not bot_has_perms:
            logger.error(f"❌ البوت لا يملك صلاحيات في القناة {channel_id}: {bot_error}")
            await callback.answer(
                f"❌ {bot_error}\n\nيرجى منح البوت صلاحيات النشر في القناة",
                show_alert=True
            )
            return

        # إنشاء اسم مخصص للمهمة
        channel_title = channel_info.get('title', 'قناة')
        custom_task_name = f"{admin_task.name} --< {channel_title}"

        logger.info(f"📝 إنشاء المهمة: {custom_task_name}")

        # إنشاء المهمة
        target_channel = {
            'id': channel_id,
            'title': channel_title,
            'username': channel_info.get('username')
        }

        task_id = task_manager.add_task(
            admin_task_id=admin_task_id,
            admin_task_name=custom_task_name,
            target_channel=target_channel
        )

        logger.info(f"✅ تم إنشاء مهمة المستخدم #{task_id}")

        # إضافة القناة للمهمة الإدارية
        all_tasks = manager.get_all_tasks()
        admin_task = all_tasks.get(admin_task_id)

        if admin_task:
            target_channel_admin = {
                'id': channel_id,
                'title': channel_title,
                'username': channel_info.get('username'),
                'user_id': user_id,
                'user_task_id': task_id
            }
            admin_task.target_channels.append(target_channel_admin)
            manager.save_tasks(all_tasks)
            logger.info(f"✅ تم إضافة القناة {channel_id} للمهمة الإدارية #{admin_task_id}")

            # إعادة تحميل النظام المتوازي
            import parallel_forwarding_system
            if parallel_forwarding_system.parallel_system:
                await parallel_forwarding_system.parallel_system.reload_tasks()
                logger.info(f"🔄 تم إعادة تحميل النظام المتوازي")

        # الحصول على عنوان المصدر
        source_title = 'المصدر'
        if admin_task.source_channels and len(admin_task.source_channels) > 0:
            source_title = admin_task.source_channels[0].get('title', 'المصدر')

        # تنظيف النصوص من HTML entities الخاصة
        import html
        clean_task_name = html.escape(custom_task_name)
        clean_source_title = html.escape(source_title)
        clean_channel_title = html.escape(channel_title)

        # عرض لوحة التحكم الكاملة
        from subscription_manager import SubscriptionManager
        sub_manager = SubscriptionManager(user_id)
        is_premium = sub_manager.is_premium()
        lock_icon = "" if is_premium else " 🔒"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏸️ تعطيل", callback_data=f"user_task_toggle:{task_id}")],
            [InlineKeyboardButton(text=f"🎬 فلاتر الوسائط{lock_icon}", callback_data=f"settings_media:{task_id}"),
             InlineKeyboardButton(text=f"🔘 أزرار إنلاين{lock_icon}", callback_data=f"settings_buttons:{task_id}")],
            [InlineKeyboardButton(text=f"📝 رأس الرسالة{lock_icon}", callback_data=f"settings_header:{task_id}"),
             InlineKeyboardButton(text=f"📝 ذيل الرسالة{lock_icon}", callback_data=f"settings_footer:{task_id}")],
            [InlineKeyboardButton(text=f"✅ قائمة بيضاء{lock_icon}", callback_data=f"settings_whitelist:{task_id}"),
             InlineKeyboardButton(text=f"🚫 قائمة سوداء{lock_icon}", callback_data=f"settings_blacklist:{task_id}")],
            [InlineKeyboardButton(text=f"🔄 الاستبدالات{lock_icon}", callback_data=f"settings_replacements:{task_id}"),
             InlineKeyboardButton(text=f"🔗 إدارة الروابط{lock_icon}", callback_data=f"settings_links:{task_id}")],
            [InlineKeyboardButton(text=f"🚫 فلتر الأزرار{lock_icon}", callback_data=f"settings_button_filter:{task_id}"),
             InlineKeyboardButton(text=f"↪️ فلتر الموجهة{lock_icon}", callback_data=f"settings_forwarded:{task_id}")],
            [InlineKeyboardButton(text=f"🌐 فلتر اللغة{lock_icon}", callback_data=f"settings_language:{task_id}"),
             InlineKeyboardButton(text=f"🎨 تنسيق النص{lock_icon}", callback_data=f"text_format_menu_{task_id}")],
            [InlineKeyboardButton(text=f"📌 التثبيت التلقائي{lock_icon}", callback_data=f"settings_auto_pin:{task_id}"),
             InlineKeyboardButton(text=f"🔗 معاينة الروابط{lock_icon}", callback_data=f"settings_link_preview:{task_id}")],
            [InlineKeyboardButton(text=f"💬 الحفاظ على الردود{lock_icon}", callback_data=f"settings_reply_preservation:{task_id}"),
             InlineKeyboardButton(text=f"🗑️ الحذف التلقائي{lock_icon}", callback_data=f"settings_auto_delete:{task_id}")],
            [InlineKeyboardButton(text=f"📅 فلتر الأيام{lock_icon}", callback_data=f"settings_day_filter:{task_id}"),
             InlineKeyboardButton(text=f"🕒 فلتر الساعات{lock_icon}", callback_data=f"settings_hour_filter:{task_id}")],
            [InlineKeyboardButton(text=f"🌍 ترجمة النصوص{lock_icon}", callback_data=f"settings_translation:{task_id}"),
             InlineKeyboardButton(text=f"📏 حدود الأحرف{lock_icon}", callback_data=f"settings_character_limit:{task_id}")],
            [InlineKeyboardButton(text=f"📊 إحصائيات المهمة", callback_data=f"settings_task_stats:{task_id}")],
            [InlineKeyboardButton(text="🧪 اختبار المهمة", callback_data=f"test_task:{task_id}"),
             InlineKeyboardButton(text="🗑️ حذف المهمة", callback_data=f"user_task_delete:{task_id}")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="user_manage_tasks")]
        ])

        success_message = (
            f"✅ <b>تم إنشاء المهمة بنجاح!</b>\n\n"
            f"📊 <b>الحالة:</b> 🟢 نشطة\n\n"
            f"📍 <b>من → إلى:</b>\n"
            f"  📢 <b>المصدر:</b> {clean_source_title}\n"
            f"  📣 <b>الهدف:</b> {clean_channel_title}\n\n"
            f"🎉 سيتم نسخ المحتوى تلقائياً من المصدر إلى قناتك!\n\n"
            f"💡 يمكنك التحكم في المهمة وتخصيص إعداداتها من الأزرار أدناه:"
        )

        logger.info(f"📤 إرسال رسالة النجاح للمستخدم {user_id}")

        await callback.message.edit_text(
            success_message,
            parse_mode='HTML',
            reply_markup=keyboard
        )

        await callback.answer("✅ تم إنشاء المهمة بنجاح!", show_alert=False)

        logger.info(f"🎉 اكتملت عملية إنشاء المهمة بنجاح!")

    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء المهمة: {e}", exc_info=True)
        await callback.answer(f"❌ حدث خطأ: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("test_task:"))
async def test_task_handler(callback: CallbackQuery, bot: Bot):
    """اختبار المهمة - جلب آخر 3 رسائل من المصدر"""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])

    logger.info(f"🧪 بدء اختبار المهمة #{task_id} للمستخدم {user_id}")

    task_manager = UserTaskManager(user_id)
    task = task_manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة", show_alert=True)
        return

    # التحقق من وجود قناة مصدر
    if not task.source_channel:
        await callback.answer("❌ لا يوجد مصدر محدد لهذه المهمة", show_alert=True)
        return

    source_channel_id = task.source_channel.get('id')
    source_title = task.source_channel.get('title', 'القناة المصدر')
    target_title = task.target_channel.get('title', 'قناتك')

    await callback.answer()

    try:
        # إرسال رسالة انتظار
        wait_msg = await callback.message.answer(
            "🧪 <b>جاري اختبار المهمة...</b>\n\n"
            "⏳ يتم جلب آخر 3 رسائل من المصدر...",
            parse_mode='HTML'
        )

        # جلب آخر 3 رسائل من القناة
        message_ids = []

        # محاولة جلب آخر 500 رسالة للعثور على 3 رسائل صالحة
        for msg_id in range(1, 501):
            if len(message_ids) >= 3:
                break

            try:
                # محاولة الوصول للرسالة عن طريق copy_message
                copied = await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=source_channel_id,
                    message_id=msg_id
                )

                # حذف النسخة المؤقتة
                await bot.delete_message(user_id, copied.message_id)

                # إضافة معرف الرسالة للقائمة
                message_ids.insert(0, msg_id)  # إضافة في البداية للحصول على الأحدث
                logger.info(f"✅ وجدنا رسالة صالحة: ID {msg_id}")

            except Exception:
                # الرسالة غير موجودة أو لا نملك صلاحية
                continue

        if not message_ids:
            await wait_msg.edit_text(
                f"❌ <b>لم نتمكن من جلب رسائل للاختبار</b>\n\n"
                f"الأسباب المحتملة:\n"
                f"• القناة المصدر فارغة أو لا توجد رسائل\n"
                f"• البوت ليس مشرفاً في قناة المصدر\n\n"
                f"💡 <b>للاختبار:</b>\n"
                f"1. تأكد أن البوت مشرف في قناة المصدر\n"
                f"2. فعّل المهمة وانتظر رسالة جديدة",
                parse_mode='HTML'
            )
            return

        # حذف رسالة الانتظار
        await wait_msg.delete()

        # إرسال آخر 3 رسائل مباشرة (بدون معالجة)
        for msg_id in message_ids[:3]:  # أخذ آخر 3 رسائل فقط
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=source_channel_id,
                    message_id=msg_id
                )
                logger.info(f"📤 تم إرسال الرسالة #{msg_id} للمستخدم {user_id}")

            except Exception as e:
                logger.error(f"❌ خطأ في إرسال الرسالة #{msg_id}: {e}")
                continue

        # إرسال رسالة النجاح مع زر العودة
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"user_task_view:{task_id}")]
        ])

        success_msg = (
            f"✅ <b>المهمة تعمل بنجاح!</b>\n\n"
            f"📢 <b>المصدر:</b> {source_title}\n"
            f"📣 <b>الهدف:</b> {target_title}\n\n"
            f"🎯 <b>سيتم التوجيه التلقائي إلى قناتك عند نشر أول رسالة في المصدر</b>\n\n"
            f"📨 تم جلب آخر {len(message_ids)} رسائل كمثال أعلاه ⬆️"
        )

        sent_message = await callback.message.answer(
            success_msg,
            parse_mode='HTML',
            reply_markup=keyboard
        )

        # حفظ معرف الرسالة الجديدة وحذف اللوحة السابقة
        await delete_last_panel_and_save_new(bot, user_id, sent_message.message_id)

        logger.info(f"✅ تم إكمال اختبار المهمة #{task_id} بنجاح للمستخدم {user_id}")

    except Exception as e:
        logger.error(f"❌ خطأ في اختبار المهمة: {e}", exc_info=True)
        try:
            await callback.message.answer(
                f"❌ <b>فشل الاختبار</b>\n\n"
                f"حدث خطأ أثناء اختبار المهمة:\n{str(e)}",
                parse_mode='HTML'
            )
        except:
            pass
@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, bot: Bot):
    """أمر عام لإلغاء أي حالة انتظار"""
    from channel_detection import users_adding_bot

    user_id = message.from_user.id
    current_state = await state.get_state()

    if current_state is None:
        await message.answer(
            "❌ لا توجد عملية جارية للإلغاء",
            parse_mode='HTML'
        )
        return

    # إغلاق FSM state
    await state.clear()

    # إلغاء مهمة timeout إن وجدت
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
        del timeout_tasks[user_id]
        logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} عبر /cancel")

    # إزالة المستخدم من users_adding_bot إن وجد
    if user_id in users_adding_bot:
        users_adding_bot.discard(user_id)
        logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot عبر /cancel")

    # إرسال رسالة التأكيد وحذف اللوحة السابقة
    sent_message = await message.answer(
        "✅ <b>تم إلغاء العملية الحالية</b>\n\n"
        "يمكنك البدء من جديد.",
        parse_mode='HTML'
    )

    # حذف اللوحة السابقة وحفظ الجديدة
    await delete_last_panel_and_save_new(bot, user_id, sent_message.message_id)
