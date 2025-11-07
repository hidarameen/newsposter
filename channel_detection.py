import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from user_channel_manager import UserChannelManager
from user_task_manager import UserTaskManager
from forwarding_manager import ForwardingManager

logger = logging.getLogger(__name__)

router = Router()

# قاموس لتتبع مالكي القنوات
channel_owner_map = {}

# مجموعة لتتبع المستخدمين الذين في عملية إضافة مهمة (لتجاهل الإشعارات)
users_adding_bot = set()

async def find_channel_owner(chat_id: int) -> Optional[int]:
    """
    البحث عن مالك القناة في ملفات جميع المستخدمين

    Args:
        chat_id: معرف القناة

    Returns:
        معرف المستخدم المالك أو None
    """
    import os
    from config import USERS_DATA_DIR

    try:
        # البحث في مجلدات جميع المستخدمين
        for user_dir in os.listdir(USERS_DATA_DIR):
            if not user_dir.isdigit():
                continue

            user_id = int(user_dir)
            channel_manager = UserChannelManager(user_id)

            if channel_manager.channel_exists(chat_id):
                logger.info(f"✅ تم العثور على مالك القناة {chat_id}: المستخدم {user_id}")
                return user_id

        logger.warning(f"⚠️ لم يتم العثور على مالك للقناة {chat_id} في أي ملف مستخدم")
        return None
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن مالك القناة {chat_id}: {e}")
        return None

@router.my_chat_member()
async def handle_my_chat_member(event: ChatMemberUpdated, bot: Bot, state: FSMContext):
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    chat_id = event.chat.id
    chat_type = event.chat.type
    action_user_id = event.from_user.id

    logger.info(f"🔔 ===== HANDLER TRIGGERED ===== 🔔")
    logger.info(f"🔄 تغيير حالة البوت في {chat_id} ({chat_type}): {old_status} -> {new_status}")
    logger.info(f"👤 المستخدم الذي نفذ الإجراء: {action_user_id}")
    logger.info(f"📍 Current FSM context: chat={event.chat.id}, user={event.from_user.id}")

    # سجل تفصيلي للصلاحيات - دائماً
    new_member = event.new_chat_member
    old_member = event.old_chat_member

    logger.info(f"📋 صلاحيات البوت القديمة:")
    logger.info(f"  - status: {old_status}")
    logger.info(f"  - can_post_messages: {getattr(old_member, 'can_post_messages', 'غير محدد')}")
    logger.info(f"  - can_edit_messages: {getattr(old_member, 'can_edit_messages', 'غير محدد')}")
    logger.info(f"  - can_delete_messages: {getattr(old_member, 'can_delete_messages', 'غير محدد')}")

    logger.info(f"📋 صلاحيات البوت الجديدة:")
    logger.info(f"  - status: {new_status}")
    logger.info(f"  - can_post_messages: {getattr(new_member, 'can_post_messages', 'غير محدد')}")
    logger.info(f"  - can_edit_messages: {getattr(new_member, 'can_edit_messages', 'غير محدد')}")
    logger.info(f"  - can_delete_messages: {getattr(new_member, 'can_delete_messages', 'غير محدد')}")
    logger.info(f"  - can_send_messages: {getattr(new_member, 'can_send_messages', 'غير محدد')}")

    # حالة: إضافة البوت للمرة الأولى
    if new_status in ['administrator', 'member'] and old_status not in ['administrator', 'member']:
        logger.info(f"🎯 === HANDLER: إضافة البوت للمرة الأولى ===")
        logger.info(f"✅ تم إضافة البوت إلى {chat_id} بواسطة المستخدم {action_user_id}")

        # تحديث المستخدم كمالك للقناة (سيستبدل المالك القديم إن وجد)
        if chat_id in channel_owner_map:
            old_owner = channel_owner_map[chat_id]
            if old_owner != action_user_id:
                logger.info(f"🔄 تحديث مالك القناة {chat_id} من {old_owner} إلى {action_user_id}")

        channel_owner_map[chat_id] = action_user_id
        user_id = action_user_id

        channel_manager = UserChannelManager(user_id)
        chat = await bot.get_chat(chat_id)

        # تتبع القناة/المجموعة في نظام التتبع العام
        from channels_tracker import channels_tracker
        channels_tracker.add_or_update_channel(
            chat_id=chat_id,
            title=chat.title or "قناة بدون اسم",
            username=chat.username,
            chat_type=chat.type,
            added_by=action_user_id
        )

        # التحقق مما إذا كانت القناة موجودة مسبقاً
        is_new_channel = not channel_manager.channel_exists(chat_id)

        # حفظ القناة إذا لم تكن موجودة
        if is_new_channel:
            channel_manager.add_channel(
                channel_id=chat_id,
                title=chat.title or "قناة بدون اسم",
                username=chat.username,
                chat_type=chat.type
            )
            logger.info(f"💾 تم حفظ القناة {chat_id} للمستخدم {user_id}")

            # إرسال إشعار إضافة البوت للقناة
            from notification_manager import notification_manager
            try:
                await notification_manager.notify_bot_added_to_channel(
                    bot,
                    chat_id,
                    chat.title or "قناة بدون اسم",
                    action_user_id,
                    event.from_user.first_name
                )
            except Exception as e:
                logger.error(f"خطأ في إرسال إشعار إضافة البوت: {e}")
        else:
            logger.info(f"ℹ️ القناة {chat_id} موجودة مسبقاً للمستخدم {user_id} - تم تحديث الصلاحيات فقط")

        # التحقق من حالة FSM - هل المستخدم في عملية إضافة مهمة؟
        # ⚠️ IMPORTANT: نحتاج للحصول على FSM state من private chat المستخدم، وليس من القناة

        # إنشاء storage key للمستخدم (private chat)
        user_storage_key = StorageKey(
            bot_id=bot.id,
            chat_id=user_id,  # استخدام user_id كـ chat_id للـ private chat
            user_id=user_id
        )

        # الحصول على FSM context الخاص بالمستخدم
        user_state_ctx = FSMContext(
            storage=state.storage,
            key=user_storage_key
        )

        user_state = await user_state_ctx.get_state()
        data = await user_state_ctx.get_data()

        logger.info(f"🔍 حالة FSM للمستخدم {user_id}: {user_state}")
        logger.info(f"🔍 بيانات FSM المحفوظة: {data}")

        # متغير لتتبع ما إذا كان المستخدم في عملية إضافة مهمة
        is_in_task_creation_process = False
        admin_task_id = None
        admin_task_name = None

        # التحقق من FSM state - إذا كان في حالة انتظار
        task_creation_states = [
            "UserTaskCreationStates:waiting_for_channel_link",
            "UserTaskCreationStates:waiting_for_channel_addition"
        ]

        if user_state in task_creation_states:
            is_in_task_creation_process = True
            logger.info(f"✅ المستخدم في حالة FSM لإنشاء مهمة: {user_state}")
            # الحصول على بيانات المهمة من FSM
            admin_task_id = data.get('selected_admin_task_id')
            admin_task_name = data.get('selected_admin_task_name')
            logger.info(f"📋 بيانات من FSM: admin_task_id={admin_task_id}, admin_task_name={admin_task_name}")

        # التحقق من PendingTasksManager (نسخة احتياطية إذا انتهت FSM state)
        logger.info(f"🔍 التحقق من PendingTasksManager...")
        logger.info(f"   is_in_task_creation_process={is_in_task_creation_process}")
        logger.info(f"   admin_task_id={admin_task_id}")
        logger.info(f"   admin_task_name={admin_task_name}")

        if not is_in_task_creation_process or not admin_task_id or not admin_task_name:
            from pending_tasks_manager import PendingTasksManager
            pending_manager = PendingTasksManager()
            logger.info(f"🔍 البحث عن pending task للقناة {chat_id} والمستخدم {user_id}...")
            pending_result = pending_manager.get_pending_by_channel(chat_id, user_id)

            if pending_result:
                code, pending_task = pending_result
                admin_task_id = pending_task['admin_task_id']
                admin_task_name = pending_task['admin_task_name']
                is_in_task_creation_process = True
                logger.info(f"✅ تم العثور على مهمة معلقة في PendingTasksManager - code={code}")
                logger.info(f"   admin_task_id={admin_task_id}, admin_task_name={admin_task_name}")
            else:
                logger.info(f"❌ لم يتم العثور على pending task في PendingTasksManager")
                if not is_in_task_creation_process:
                    logger.info(f"✅✅✅ المستخدم ليس في عملية إضافة مهمة - سيتم إرسال الإشعار العام")
                else:
                    logger.warning(f"⚠️ المستخدم في FSM state لكن بدون بيانات admin_task")
        else:
            logger.info(f"ℹ️ تم تخطي PendingTasksManager - البيانات موجودة من FSM")

        # إذا كان المستخدم في عملية إضافة مهمة (أو كان فيها قبل timeout)
        if is_in_task_creation_process and admin_task_id and admin_task_name:
            logger.info(f"✅ تم اكتشاف عملية إضافة مهمة - admin_task_id={admin_task_id}")

            # المستخدم في عملية إضافة مهمة - سنضيفها تلقائياً
            channel_input = data.get('channel_input')
            expected_channel_id = data.get('channel_id')

            if user_state != "UserTaskCreationStates:waiting_for_channel_addition":
                logger.info(f"⚠️ FSM State منتهي (timeout) لكن البيانات موجودة - سنستخدمها لإكمال المهمة")

            logger.info(f"📋 بيانات FSM: admin_task_id={admin_task_id}, expected_channel_id={expected_channel_id}, actual_channel_id={chat_id}")

            # التحقق من أن القناة المضاف إليها البوت هي نفس القناة المنتظرة
            if expected_channel_id and expected_channel_id != chat_id:
                logger.warning(f"⚠️ القناة المضافة ({chat_id}) لا تطابق القناة المنتظرة ({expected_channel_id})")
                return

            if not admin_task_id or not admin_task_name:
                logger.error(f"❌ بيانات FSM غير كاملة للمستخدم {user_id}")
                return

            logger.info(f"🎯 البوت تمت إضافته كمشرف في القناة {chat_id} - سيتم إكمال إنشاء المهمة تلقائياً")

            # التحقق من صلاحيات البوت والمستخدم في القناة
            from channel_verification import ChannelVerification

            success, error_msg, channel_info = await ChannelVerification.verify_channel_for_task(
                bot, chat_id, user_id
            )

            if not success or not channel_info:
                logger.error(f"❌ فشل التحقق من القناة: {error_msg}")
                # إرسال إشعار للمستخدم
                try:
                    await bot.send_message(
                        user_id,
                        f"❌ <b>فشل إكمال المهمة</b>\n\n{error_msg}\n\n"
                        f"يرجى التأكد من منح البوت جميع الصلاحيات المطلوبة.",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"❌ فشل إرسال رسالة الخطأ: {e}")
                return

            # إنشاء المهمة مباشرة
            from user_task_manager import UserTaskManager

            task_manager = UserTaskManager(user_id)

            # التحقق من عدم وجود نفس المهمة
            if task_manager.task_exists(admin_task_id, chat_id):
                logger.warning(f"⚠️ المهمة موجودة مسبقاً")
                await state.clear()
                try:
                    await bot.send_message(
                        user_id,
                        "⚠️ <b>المهمة موجودة مسبقاً!</b>\n\n"
                        f"لديك بالفعل مهمة نشر من هذا المصدر إلى هذه القناة.",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"❌ فشل إرسال رسالة: {e}")
                return

            # الحصول على عنوان المصدر
            from forwarding_manager import ForwardingManager
            manager = ForwardingManager()
            task = manager.get_task(admin_task_id)
            source_title = "غير محدد"
            if task and task.source_channels:
                source_title = task.source_channels[0].get('title', 'غير محدد')

            # إنشاء اسم مخصص للمهمة
            custom_task_name = f"{admin_task_name} -> {channel_info['title']}"

            # إنشاء المهمة
            user_task_id = task_manager.add_task(
                admin_task_id=admin_task_id,
                admin_task_name=custom_task_name,
                target_channel=channel_info
            )

            logger.info(f"✅ تم إنشاء المهمة {user_task_id} للمستخدم {user_id} بنجاح عبر channel_detection")

            # إضافة القناة للمهمة الإدارية
            all_tasks = manager.get_all_tasks()
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
                manager.save_tasks(all_tasks)
                logger.info(f"✅ تم إضافة القناة {chat_id} للمهمة الإدارية #{admin_task_id}")

                # إعادة تحميل النظام المتوازي
                import parallel_forwarding_system
                if parallel_forwarding_system.parallel_system:
                    await parallel_forwarding_system.parallel_system.reload_tasks()
                    logger.info(f"🔄 تم إعادة تحميل النظام المتوازي")

            # تنظيف الحالة
            await state.clear()

            # تنظيف النصوص من HTML entities الخاصة
            import html
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

            try:
                sent_message = await bot.send_message(
                    user_id,
                    success_message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                logger.info(f"📤 تم إرسال رسالة النجاح للمستخدم {user_id}")

                # حذف اللوحة السابقة وحفظ الجديدة
                from user_handlers import delete_last_panel_and_save_new
                await delete_last_panel_and_save_new(bot, user_id, sent_message.message_id)

            except Exception as e:
                logger.error(f"❌ خطأ في إرسال رسالة النجاح: {e}")

            # تنظيف users_adding_bot إذا كان المستخدم موجوداً فيه
            if user_id in users_adding_bot:
                users_adding_bot.discard(user_id)
                logger.info(f"🗑️ تم إزالة المستخدم {user_id} من users_adding_bot بعد إنشاء المهمة")

            # إلغاء timeout task إذا كان موجوداً
            try:
                from user_handlers import timeout_tasks
                if user_id in timeout_tasks:
                    timeout_task = timeout_tasks[user_id]
                    if not timeout_task.done():
                        timeout_task.cancel()
                        logger.info(f"✅ تم إلغاء timeout task للمستخدم {user_id} بعد نجاح إنشاء المهمة")
                    del timeout_tasks[user_id]
            except Exception as e:
                logger.warning(f"⚠️ خطأ في إلغاء timeout task: {e}")

            # حذف المهمة المعلقة من PendingTasksManager إذا كانت موجودة
            from pending_tasks_manager import PendingTasksManager
            pending_manager = PendingTasksManager()
            pending_result = pending_manager.get_pending_by_channel(chat_id, user_id)
            if pending_result:
                code, _ = pending_result
                pending_manager.delete_pending_task(code)
                logger.info(f"🗑️ تم حذف المهمة المعلقة {code} بعد إكمالها بنجاح")

            logger.info(f"🎊 اكتملت عملية إنشاء المهمة تلقائياً بنجاح!")
            return

        # إذا كان المستخدم في عملية إضافة مهمة لكن لا يوجد admin_task_id
        # هذا يعني أن البيانات غير مكتملة - نعتبر أنه ليس في عملية إضافة مهمة
        if is_in_task_creation_process and (not admin_task_id or not admin_task_name):
            logger.warning(f"⚠️ المستخدم {user_id} في حالة task creation لكن بدون بيانات admin_task - سنرسل الإشعار العام")
            is_in_task_creation_process = False
            # تنظيف users_adding_bot
            if user_id in users_adding_bot:
                users_adding_bot.discard(user_id)

        # إرسال الإشعار العام فقط إذا لم يكن المستخدم في عملية إضافة مهمة
        if not is_in_task_creation_process:
            logger.info(f"🎯🎯🎯 سيتم إرسال الإشعار العام للمستخدم {user_id}")
            # إرسال الإشعار في جميع الحالات (قناة جديدة أو موجودة)
            try:
                logger.info(f"🔍 فحص نوع القناة: {chat_type}")
                if chat_type in ['group', 'supergroup', 'channel']:
                    logger.info(f"✅✅✅ نوع القناة صحيح: {chat_type} - سيتم إرسال الإشعار")

                    # التحقق من صلاحيات البوت قبل إرسال الإشعار
                    from channel_verification import ChannelVerification
                    bot_has_perms, bot_error = await ChannelVerification.check_bot_permissions(bot, chat_id)

                    if not bot_has_perms:
                        # البوت ليس مشرفاً - إرسال تنبيه
                        logger.info(f"⚠️ البوت ليس مشرفاً في {chat_id} - إرسال تنبيه للمستخدم")
                        bot_info = await bot.get_me()
                        chat_type_ar = 'المجموعة' if chat_type in ['group', 'supergroup'] else 'القناة'

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📋 مهامي", callback_data="user_manage_tasks")]
                        ])

                        notification_message = f"⚠️ <b>تم إضافة البوت إلى {chat_type_ar} \"{chat.title}\"</b>\n\n"
                        notification_message += f"📢 {chat_type_ar}: <b>{chat.title}</b>\n"
                        notification_message += f"🆔 المعرف: <code>{chat_id}</code>\n\n"
                        notification_message += f"❌ <b>البوت حالياً عضو عادي فقط!</b>\n\n"
                        notification_message += f"لتفعيل النشر التلقائي، يجب:\n"
                        notification_message += f"1️⃣ رفع البوت @{bot_info.username} كمشرف\n"
                        notification_message += f"2️⃣ منحه صلاحية {'النشر' if chat_type == 'channel' else 'إرسال الرسائل'}\n\n"
                        notification_message += f"بعد ذلك سيتم تفعيل النشر تلقائياً! 🎉"
                    else:
                        # البوت مشرف - إرسال إشعار النجاح
                        logger.info(f"✅ البوت مشرف في {chat_id} - إرسال إشعار النجاح")
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📰 اختيار مصدر", callback_data=f"choose_source_for_channel:{chat_id}")],
                            [InlineKeyboardButton(text="📋 مهامي", callback_data="user_manage_tasks")]
                        ])

                        chat_type_ar = 'قناتك' if chat_type == 'channel' else 'مجموعتك'
                        notification_message = f"✅ <b>تم إضافة {chat_type_ar} \"{chat.title}\" بنجاح!</b>\n\n"
                        notification_message += f"📢 {'القناة' if chat_type == 'channel' else 'المجموعة'}: <b>{chat.title}</b>\n"
                        notification_message += f"🆔 المعرف: <code>{chat_id}</code>\n\n"

                        if is_new_channel:
                            notification_message += f"لتفعيل النشر في {chat_type_ar}، قم باختيار مصدر للنشر منه:"

                    try:
                        await bot.send_message(
                            user_id,
                            notification_message,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        logger.info(f"📤 ✅ تم إرسال إشعار إضافة القناة للمستخدم {user_id}")
                    except Exception as send_error:
                        # معالجة حالة عدم قدرة البوت على إرسال رسالة للمستخدم
                        error_message = str(send_error)
                        if "Forbidden" in error_message or "bot was blocked" in error_message:
                            logger.warning(f"⚠️ المستخدم {user_id} لم يبدأ محادثة مع البوت أو قام بحظره")
                        else:
                            logger.error(f"❌ خطأ في إرسال الرسالة للمستخدم {user_id}: {send_error}")
                else:
                    logger.warning(f"⚠️ نوع القناة غير مدعوم: {chat_type}")
            except Exception as e:
                logger.error(f"❌ خطأ في معالجة إرسال الإشعار للمستخدم {user_id}: {e}", exc_info=True)
        else:
            logger.info(f"ℹ️ المستخدم {user_id} في عملية إضافة مهمة - لن يتم إرسال الإشعار العام")

        # تنظيف users_adding_bot في جميع الحالات
        if user_id in users_adding_bot:
            users_adding_bot.discard(user_id)
            logger.info(f"🗑️ تم تنظيف users_adding_bot للمستخدم {user_id}")

        # الانتهاء من معالجة الإضافة - عدم متابعة للشروط الأخرى
        return

    # حالة: إزالة الإشراف من البوت في المجموعات (administrator -> member)
    if old_status == 'administrator' and new_status == 'member' and chat_type in ['group', 'supergroup']:
        logger.info(f"🎯 === HANDLER: إزالة الإشراف من البوت في المجموعة ===")
        logger.info(f"⚠️ تم إزالة الإشراف من البوت في {chat_id}")

        # الحصول على المالك الفعلي للقناة من channel_owner_map
        owner_user_id = channel_owner_map.get(chat_id)

        if not owner_user_id:
            logger.warning(f"⚠️ لم يتم العثور على مالك للمجموعة {chat_id} في channel_owner_map")
            owner_user_id = await find_channel_owner(chat_id)
            if not owner_user_id:
                logger.error(f"❌ تعذر العثور على مالك المجموعة {chat_id}")
                return

        logger.info(f"📌 مالك المجموعة: {owner_user_id}")

        # حذف القناة من channel_owner_map
        if chat_id in channel_owner_map:
            del channel_owner_map[chat_id]
            logger.info(f"🗑 تم حذف المجموعة {chat_id} من channel_owner_map")

        # معالجة إيقاف المهام وإرسال الإشعار
        await handle_bot_removed_from_channel(bot, owner_user_id, chat_id, event.chat, "admin_removed")
        return

    # حالة: إزالة البوت من القناة
    if new_status in ['left', 'kicked']:
        logger.info(f"🎯 === HANDLER: إزالة البوت من القناة ===")
        logger.info(f"❌ تم إزالة البوت من {chat_id}")

        # تحديث حالة القناة في نظام التتبع
        from channels_tracker import channels_tracker
        channels_tracker.mark_as_removed(chat_id)

        # الحصول على المالك الفعلي للقناة من channel_owner_map
        owner_user_id = channel_owner_map.get(chat_id)

        if not owner_user_id:
            logger.warning(f"⚠️ لم يتم العثور على مالك للقناة {chat_id} في channel_owner_map")
            # محاولة البحث في ملفات جميع المستخدمين
            owner_user_id = await find_channel_owner(chat_id)
            if not owner_user_id:
                logger.error(f"❌ تعذر العثور على مالك القناة {chat_id}")
                return

        logger.info(f"📌 مالك القناة: {owner_user_id}")

        # حذف القناة من channel_owner_map
        if chat_id in channel_owner_map:
            del channel_owner_map[chat_id]
            logger.info(f"🗑 تم حذف القناة {chat_id} من channel_owner_map")

        # معالجة إيقاف المهام وإرسال الإشعار
        removal_type = "left" if new_status == "left" else "kicked"
        await handle_bot_removed_from_channel(bot, owner_user_id, chat_id, event.chat, removal_type)
        return

    # حالة: تقييد صلاحيات البوت (status = restricted) - معاملته كإزالة إشراف
    if new_status == 'restricted' and old_status == 'administrator':
        logger.info(f"🎯 === HANDLER: تقييد البوت (فقد الإشراف) ===")
        logger.info(f"⚠️ تم تقييد البوت وفقد صلاحيات الإشراف في {chat_id}")

        # الحصول على المالك الفعلي للقناة
        owner_user_id = channel_owner_map.get(chat_id)

        if not owner_user_id:
            logger.warning(f"⚠️ لم يتم العثور على مالك للقناة {chat_id} في channel_owner_map")
            owner_user_id = await find_channel_owner(chat_id)
            if not owner_user_id:
                logger.error(f"❌ تعذر العثور على مالك القناة {chat_id}")
                return

        logger.info(f"📌 مالك القناة: {owner_user_id}")

        # حذف القناة من channel_owner_map
        if chat_id in channel_owner_map:
            del channel_owner_map[chat_id]
            logger.info(f"🗑 تم حذف القناة {chat_id} من channel_owner_map")

        # معالجة إيقاف المهام وإرسال الإشعار (نفس معاملة إزالة الإشراف)
        await handle_bot_removed_from_channel(bot, owner_user_id, chat_id, event.chat, "restricted")
        return

    # حالة: ترقية البوت من member إلى administrator
    if new_status == 'administrator' and old_status == 'member':
        logger.info(f"🎯 === HANDLER: ترقية البوت من member إلى administrator ===")
        logger.info(f"✅ تمت ترقية البوت إلى مشرف في {chat_id}")

        # الحصول على المالك الفعلي للقناة
        owner_user_id = channel_owner_map.get(chat_id)

        if not owner_user_id:
            logger.warning(f"⚠️ لم يتم العثور على مالك للقناة/المجموعة {chat_id} في channel_owner_map")
            owner_user_id = await find_channel_owner(chat_id)
            if not owner_user_id:
                logger.error(f"❌ تعذر العثور على مالك القناة/المجموعة {chat_id}")
                return

        logger.info(f"📌 مالك القناة/المجموعة: {owner_user_id}")

        # الحصول على معلومات القناة/المجموعة
        chat = await bot.get_chat(chat_id)
        chat_type = chat.type
        chat_type_ar = 'قناتك' if chat_type == 'channel' else 'مجموعتك'

        # إرسال إشعار النجاح للمستخدم
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📰 اختيار مصدر", callback_data=f"choose_source_for_channel:{chat_id}")],
                [InlineKeyboardButton(text="📋 مهامي", callback_data="user_manage_tasks")]
            ])

            notification_message = f"✅ <b>تم إضافة {chat_type_ar} \"{chat.title}\" بنجاح!</b>\n\n"
            notification_message += f"📢 {'القناة' if chat_type == 'channel' else 'المجموعة'}: <b>{chat.title}</b>\n"
            notification_message += f"🆔 المعرف: <code>{chat_id}</code>\n\n"
            notification_message += f"🎉 <b>تمت ترقية البوت إلى مشرف بنجاح!</b>\n\n"
            notification_message += f"لتفعيل النشر في {chat_type_ar}، قم باختيار مصدر للنشر منه:"

            await bot.send_message(
                owner_user_id,
                notification_message,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            logger.info(f"📤 ✅ تم إرسال إشعار ترقية البوت للمستخدم {owner_user_id}")
        except Exception as send_error:
            error_message = str(send_error)
            if "Forbidden" in error_message or "bot was blocked" in error_message:
                logger.warning(f"⚠️ المستخدم {owner_user_id} لم يبدأ محادثة مع البوت أو قام بحظره")
            else:
                logger.error(f"❌ خطأ في إرسال الرسالة للمستخدم {owner_user_id}: {send_error}")

        return

    # حالة: تغيير صلاحيات البوت أثناء البقاء كـ administrator
    if new_status == 'administrator' and old_status == 'administrator':
        logger.info(f"🎯 === HANDLER: تغيير صلاحيات البوت (administrator -> administrator) ===")
        # الحصول على المالك الفعلي للقناة
        owner_user_id = channel_owner_map.get(chat_id)

        if not owner_user_id:
            logger.warning(f"⚠️ لم يتم العثور على مالك للقناة {chat_id} في channel_owner_map")
            owner_user_id = await find_channel_owner(chat_id)
            if not owner_user_id:
                logger.error(f"❌ تعذر العثور على مالك القناة {chat_id}")
                return

        logger.info(f"📌 مالك القناة: {owner_user_id}")

        # التحقق من تغيير الصلاحيات أثناء البقاء في نفس الحالة (administrator)
        new_member = event.new_chat_member
        old_member = event.old_chat_member

        restricted_permissions = []
        restored_permissions = []

        # فحص جميع الصلاحيات المهمة
        permissions_to_check = [
            ('can_post_messages', 'نشر الرسائل'),
            ('can_edit_messages', 'تعديل الرسائل'),
            ('can_delete_messages', 'حذف الرسائل'),
        ]

        for attr, label in permissions_to_check:
            old_value = getattr(old_member, attr, None)
            new_value = getattr(new_member, attr, None)

            # إذا كانت None، نعتبرها True (صلاحيات كاملة)
            if old_value is None:
                old_value = True
            if new_value is None:
                new_value = True

            # تقييد صلاحية
            if old_value and not new_value:
                restricted_permissions.append(label)
                logger.info(f"🚫 تم تقييد صلاحية {label} للبوت في {chat_id}")

            # استعادة صلاحية
            elif not old_value and new_value:
                restored_permissions.append(label)
                logger.info(f"✅ تمت استعادة صلاحية {label} للبوت في {chat_id}")

        logger.info(f"🔍 ملخص التغييرات - تقييد: {restricted_permissions} | استعادة: {restored_permissions}")

        # التحقق من تقييد الصلاحيات
        if restricted_permissions:
            await handle_permissions_restricted(bot, owner_user_id, chat_id, event.chat, restricted_permissions)

        # التحقق من استعادة الصلاحيات
        elif restored_permissions:
            await handle_permissions_restored(bot, owner_user_id, chat_id, event.chat, restored_permissions)

async def handle_permissions_restricted(bot: Bot, user_id: int, chat_id: int, chat, restricted_permissions: list):
    """معالجة تقييد صلاحيات النشر والتعديل - تعطيل المهمة"""
    import os
    from config import USERS_DATA_DIR

    # تحديث حالة القناة في نظام التتبع
    from channels_tracker import channels_tracker
    channels_tracker.mark_as_restricted(chat_id)

    permissions_text = " و ".join(restricted_permissions)
    logger.info(f"🔍 معالجة تقييد صلاحيات ({permissions_text}) في القناة {chat_id} للمستخدم {user_id}")

    # البحث عن مهام المستخدم المرتبطة بهذه القناة
    task_manager = UserTaskManager(user_id)
    all_tasks = task_manager.get_all_tasks()

    tasks_found = []
    for task_id, task in all_tasks.items():
        if task.target_channel['id'] == chat_id and task.is_active:
            tasks_found.append((task_id, task))

    if not tasks_found:
        logger.info(f"ℹ️ لا توجد مهام نشطة مرتبطة بالقناة {chat_id}")
        return

    # تعطيل المهام مؤقتاً
    fm = ForwardingManager()
    all_admin_tasks = fm.get_all_tasks()
    admin_tasks_modified = False

    for task_id, task in tasks_found:
        logger.info(f"⏸️ إيقاف مؤقت للمهمة #{task_id}")

        # تعطيل المهمة (لا نحذف الملفات هنا لأنها مؤقتة)
        task_manager.update_task_status(task_id, False)

        # حذف من المهمة الإدارية مؤقتاً
        admin_task = all_admin_tasks.get(task.admin_task_id)
        if admin_task:
            for idx in range(len(admin_task.target_channels) - 1, -1, -1):
                target = admin_task.target_channels[idx]
                if target['id'] == chat_id and target.get('user_id') == user_id:
                    admin_task.target_channels.pop(idx)
                    admin_tasks_modified = True
                    logger.info(f"⏸️ تم إزالة القناة مؤقتاً من المهمة الإدارية #{task.admin_task_id}")
                    break

    # حفظ التعديلات
    if admin_tasks_modified:
        fm.save_tasks(all_admin_tasks)

        # إعادة تحميل النظام
        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()

    # إرسال إشعار للمشرف
    from notification_manager import notification_manager
    try:
        await notification_manager.notify_bot_restricted(
            bot,
            chat_id,
            chat.title or "غير معروف"
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار تقييد البوت: {e}")

    # إرسال إشعار للمستخدم
    try:
        permissions_text = " و ".join(restricted_permissions)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📰 مهامي", callback_data="user_manage_tasks")]
        ])

        await bot.send_message(
            user_id,
            f"⚠️ <b>تنبيه: تم تقييد الصلاحيات</b>\n\n"
            f"📢 القناة: <b>{chat.title or 'غير معروف'}</b>\n"
            f"🆔 المعرف: <code>{chat_id}</code>\n\n"
            f"🚫 <b>الصلاحيات المقيدة:</b> {permissions_text}\n"
            f"❌ <b>تم تعطيل {len(tasks_found)} مهمة</b>\n\n"
            f"💡 <b>لإعادة تفعيل المهام:</b>\n"
            f"1️⃣ افتح إعدادات المشرفين في القناة\n"
            f"2️⃣ امنح البوت الصلاحيات التالية:\n"
            f"   • ✅ نشر الرسائل (إجباري)\n"
            f"   • ✅ تعديل الرسائل (إجباري)\n"
            f"3️⃣ ستتم إعادة تفعيل المهام تلقائياً",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        logger.info(f"✅ تم إرسال إشعار تقييد الصلاحيات للمستخدم {user_id}")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال إشعار للمستخدم {user_id}: {e}")

async def handle_bot_removed_from_channel(bot: Bot, user_id: int, chat_id: int, chat, removal_type: str):
    """معالجة حذف البوت من القناة - حذف المهام والإشعار"""
    import os
    from config import USERS_DATA_DIR

    logger.info(f"🔍 معالجة إزالة البوت من القناة {chat_id} للمستخدم {user_id}")

    # البحث عن جميع مهام المستخدم المرتبطة بهذه القناة
    task_manager = UserTaskManager(user_id)
    all_tasks = task_manager.get_all_tasks()

    tasks_to_delete = []
    for task_id, task in all_tasks.items():
        if task.target_channel['id'] == chat_id:
            tasks_to_delete.append((task_id, task))

    if not tasks_to_delete:
        logger.info(f"ℹ️ لا توجد مهام مرتبطة بالقناة {chat_id}")
        return

    fm = ForwardingManager()
    all_admin_tasks = fm.get_all_tasks()
    admin_tasks_modified = False

    # حذف جميع المهام المرتبطة
    for task_id, task in tasks_to_delete:
        logger.info(f"🗑 حذف مهمة المستخدم #{task_id} المرتبطة بالقناة {chat_id}")

        # حذف ملف إعدادات المهمة
        settings_file = os.path.join(USERS_DATA_DIR, str(user_id), f'task_{task_id}_settings.json')
        if os.path.exists(settings_file):
            try:
                os.remove(settings_file)
                logger.info(f"🗑️ تم حذف ملف الإعدادات: {settings_file}")
            except Exception as e:
                logger.error(f"❌ خطأ في حذف ملف الإعدادات: {e}")

        # حذف من المهام الإدارية - حذف جميع التكرارات
        admin_task = all_admin_tasks.get(task.admin_task_id)
        if admin_task:
            # حذف جميع التكرارات للهدف بنفس المستخدم
            initial_count = len(admin_task.target_channels)
            admin_task.target_channels = [
                target for target in admin_task.target_channels
                if not (target['id'] == chat_id and target.get('user_id') == user_id)
            ]

            removed_count = initial_count - len(admin_task.target_channels)
            if removed_count > 0:
                admin_tasks_modified = True
                logger.info(f"🗑 تم حذف {removed_count} هدف مكرر من المهمة الإدارية #{task.admin_task_id}")

        # حذف المهمة
        task_manager.delete_task(task_id)

    # حذف معلومات القناة
    from user_channel_manager import UserChannelManager
    channel_manager = UserChannelManager(user_id)
    channel_manager.remove_channel(chat_id)
    logger.info(f"🗑 تم حذف معلومات القناة {chat_id} من ملفات المستخدم")

    # حفظ المهام الإدارية إذا تم التعديل
    if admin_tasks_modified:
        fm.save_tasks(all_admin_tasks)

        # إعادة تحميل النظام المتوازي
        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()
            logger.info(f"🔄 تم إعادة تحميل النظام المتوازي")

    # إرسال إشعار للمشرف
    from notification_manager import notification_manager
    try:
        await notification_manager.notify_bot_removed(
            bot,
            chat_id,
            chat.title or "غير معروف"
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار حذف البوت: {e}")

    # إرسال إشعار للمستخدم
    if removal_type == "left":
        removal_text = "تمت إزالة"
        action_text = "قم بإضافة البوت للقناة مرة أخرى"
    elif removal_type == "kicked":
        removal_text = "تم طرد"
        action_text = "قم بإضافة البوت للقناة مرة أخرى"
    elif removal_type == "restricted":
        removal_text = "تم تقييد"
        action_text = "قم بمنح البوت صلاحيات الإشراف في المجموعة"
    else:  # admin_removed
        removal_text = "تمت إزالة صلاحيات الإشراف من"
        action_text = "قم بمنح البوت صلاحيات الإشراف في المجموعة"

    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📰 مهامي", callback_data="user_manage_tasks")]
        ])

        await bot.send_message(
            user_id,
            f"⚠️ <b>تنبيه: {removal_text} البوت من القناة/المجموعة</b>\n\n"
            f"📢 القناة/المجموعة: <b>{chat.title or 'غير معروف'}</b>\n"
            f"🆔 المعرف: <code>{chat_id}</code>\n\n"
            f"🗑 <b>تم حذف {len(tasks_to_delete)} مهمة مرتبطة بهذه القناة/المجموعة تلقائياً</b>\n\n"
            f"💡 لإعادة تفعيل المهام، {action_text} واختر المصدر المناسب.",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        logger.info(f"✅ تم إرسال إشعار للمستخدم {user_id}")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال إشعار للمستخدم {user_id}: {e}")

async def handle_permissions_restored(bot: Bot, user_id: int, chat_id: int, chat, restored_permissions: list):
    """معالجة استعادة صلاحيات النشر والتعديل - إعادة تفعيل المهمة"""
    permissions_text = " و ".join(restored_permissions)
    logger.info(f"🔍 معالجة استعادة صلاحيات ({permissions_text}) في القناة {chat_id} للمستخدم {user_id}")

    # البحث عن مهام المستخدم المرتبطة بهذه القناة
    task_manager = UserTaskManager(user_id)
    all_tasks = task_manager.get_all_tasks()

    tasks_found = []
    for task_id, task in all_tasks.items():
        if task.target_channel['id'] == chat_id and not task.is_active:
            tasks_found.append((task_id, task))

    if not tasks_found:
        logger.info(f"ℹ️ لا توجد مهام معطلة مرتبطة بالقناة {chat_id}")
        return

    # إعادة تفعيل المهام
    fm = ForwardingManager()
    all_admin_tasks = fm.get_all_tasks()
    admin_tasks_modified = False

    for task_id, task in tasks_found:
        logger.info(f"✅ إعادة تفعيل المهمة #{task_id}")

        # تفعيل المهمة
        task_manager.update_task_status(task_id, True)

        # إضافة للمهمة الإدارية
        admin_task = all_admin_tasks.get(task.admin_task_id)
        if admin_task:
            # التحقق من عدم وجود الهدف بنفس المستخدم والمهمة مسبقاً
            target_exists = any(
                target['id'] == chat_id and
                target.get('user_id') == user_id and
                target.get('user_task_id') == task_id
                for target in admin_task.target_channels
            )

            if not target_exists:
                admin_target = {
                    'id': chat_id,
                    'title': task.target_channel['title'],
                    'username': task.target_channel.get('username'),
                    'user_id': user_id,
                    'user_task_id': task_id
                }
                admin_task.target_channels.append(admin_target)
                admin_tasks_modified = True
                logger.info(f"✅ تمت إضافة القناة للمهمة الإدارية #{task.admin_task_id}")
            else:
                logger.info(f"ℹ️ الهدف موجود بالفعل في المهمة الإدارية")

    # حفظ التعديلات
    if admin_tasks_modified:
        fm.save_tasks(all_admin_tasks)

        # إعادة تحميل النظام
        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()

    # إرسال إشعار
    try:
        permissions_text = " و ".join(restored_permissions)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📰 مهامي", callback_data="user_manage_tasks")]
        ])

        await bot.send_message(
            user_id,
            f"✅ <b>تم استعادة الصلاحيات</b>\n\n"
            f"📢 القناة: <b>{chat.title or 'غير معروف'}</b>\n"
            f"🆔 المعرف: <code>{chat_id}</code>\n\n"
            f"✅ <b>الصلاحيات المستعادة:</b> {permissions_text}\n"
            f"🎉 <b>تمت إعادة تفعيل {len(tasks_found)} مهمة تلقائياً</b>\n\n"
            f"🚀 سيتم استئناف نسخ المنشورات الآن!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        logger.info(f"✅ تم إرسال إشعار استعادة الصلاحيات للمستخدم {user_id}")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال إشعار للمستخدم {user_id}: {e}")

async def auto_create_user_task(bot: Bot, user_id: int, chat_id: int, chat, admin_task_id: int, admin_task_name: str):
    """إنشاء المهمة تلقائياً عند إضافة البوت"""
    logger.info(f"🎯 بدء إنشاء مهمة تلقائية للمستخدم {user_id} - المهمة #{admin_task_id}")

    manager = ForwardingManager()
    admin_task = manager.get_task(admin_task_id)

    if not admin_task:
        logger.error(f"❌ المهمة الإدارية #{admin_task_id} غير موجودة!")
        await bot.send_message(
            user_id,
            "❌ حدث خطأ: المهمة المحددة غير موجودة!",
            parse_mode='HTML'
        )
        return

    # التحقق من أن القناة غير مضافة مسبقاً
    is_already_target = any(
        target.get('id') == chat_id
        for target in admin_task.target_channels
    )

    if is_already_target:
        logger.info(f"⚠️ القناة {chat_id} مضافة بالفعل للمهمة #{admin_task_id}")
        await bot.send_message(
            user_id,
            f"ℹ️ <b>القناة مفعلة مسبقاً</b>\n\n"
            f"القناة <b>{chat.title}</b> مفعلة بالفعل للمهمة: <b>{admin_task_name}</b>",
            parse_mode='HTML'
        )
        return

    # الحصول على معلومات القناة المصدر
    if not admin_task.source_channels:
        logger.error(f"❌ المهمة #{admin_task_id} ليس لها قنوات مصدر!")
        return

    source_channel = admin_task.source_channels[0]

    # إنشاء معلومات القناة الهدف
    target_channel = {
        'id': chat_id,
        'title': chat.title,
        'username': chat.username
    }

    # إضافة المهمة للمستخدم
    user_task_manager = UserTaskManager(user_id)
    new_task_id = user_task_manager.add_task(
        admin_task_id=admin_task_id,
        admin_task_name=admin_task_name,
        target_channel=target_channel
    )

    # إضافة القناة للأهداف في المهمة الإدارية مع معلومات المستخدم
    admin_target_channel = {
        'id': chat_id,
        'title': chat.title,
        'username': chat.username,
        'user_id': user_id,
        'user_task_id': new_task_id
    }
    admin_task.target_channels.append(admin_target_channel)
    all_tasks = manager.get_all_tasks()
    manager.save_tasks(all_tasks)

    # إعادة تحميل النظام المتوازي
    import parallel_forwarding_system
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    logger.info(f"✅ تم إنشاء المهمة #{new_task_id} للمستخدم {user_id} بنجاح!")

    # إرسال إشعار للمستخدم
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 عرض المهمة", callback_data=f"user_task_view:{new_task_id}")],
        [InlineKeyboardButton(text="📰 مهامي", callback_data="user_manage_tasks")]
    ])

    await bot.send_message(
        user_id,
        f"🎉 <b>تم تفعيل المهمة بنجاح!</b>\n\n"
        f"✅ <b>المهمة:</b> {admin_task_name}\n"
        f"📢 <b>المصدر:</b> {source_channel['title']}\n"
        f"📣 <b>الهدف:</b> {chat.title}\n\n"
        f"🚀 سيتم نسخ جميع المنشورات من المصدر إلى قناتك تلقائياً!",
        parse_mode='HTML',
        reply_markup=keyboard
    )