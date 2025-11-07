import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from user_channel_manager import UserChannelManager
from user_task_manager import UserTaskManager
from forwarding_manager import ForwardingManager
from user_tracker import UserTracker
import re

logger = logging.getLogger(__name__)

router = Router()
user_tracker = UserTracker()




async def is_user_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

async def process_activation(message: Message, bot: Bot):
    """معالجة أمر التفعيل"""
    logger.info(f"🔍 بدء معالجة رسالة من {message.chat.type}: {message.chat.id}")

    if not message.text:
        logger.info(f"⚠️ الرسالة لا تحتوي على نص")
        return

    logger.info(f"📝 النص: {message.text}")

    sender = message.from_user
    sender_user_id = None
    
    # في المجموعات، المستخدم يرسل بـ from_user
    if sender:
        sender_user_id = sender.id
        logger.info(f"👤 المرسل: {sender_user_id} ({sender.first_name})")
    elif message.sender_chat:
        # محاولة تحديد المشرف المناسب
        try:
            # 1. محاولة الحصول على الشخص الذي أضاف البوت من السجل
            from channel_detection import channel_owner_map
            bot_adder_id = channel_owner_map.get(message.chat.id)

            # 2. الحصول على قائمة المشرفين
            admins = await bot.get_chat_administrators(message.chat.id)
            bot_info = await bot.get_me()

            # جمع معرفات المشرفين الإنسان فقط
            admin_ids = [
                admin.user.id 
                for admin in admins 
                if not admin.user.is_bot and admin.user.id != bot_info.id
            ]

            if not admin_ids:
                logger.warning(f"⚠️ لم يتم العثور على مشرفين في القناة {message.chat.id}")
                return

            sender_user_id = None

            # 3. التحقق من الشخص الذي أضاف البوت
            if bot_adder_id and bot_adder_id in admin_ids:
                # التحقق إذا كان موجود في قائمة المستخدمين
                if user_tracker.is_user_tracked(bot_adder_id):
                    sender_user_id = bot_adder_id
                    logger.info(f"✅ تم اختيار {sender_user_id} (الشخص الذي أضاف البوت وموجود في قائمة المستخدمين)")
                else:
                    logger.info(f"ℹ️ الشخص الذي أضاف البوت ({bot_adder_id}) غير موجود في قائمة المستخدمين")

            # 4. إذا لم نجد، نبحث عن أي مشرف تفاعل مع البوت
            if not sender_user_id:
                sender_user_id = user_tracker.get_most_recent_user(admin_ids)
                if sender_user_id:
                    logger.info(f"✅ تم اختيار المشرف {sender_user_id} (آخر تفاعل مع البوت)")

            # 5. إذا لم يتفاعل أي مشرف مع البوت
            if not sender_user_id:
                error_msg = (
                    f"⚠️ <b>يجب التفاعل مع البوت أولاً</b>\n\n"
                    f"لم يتفاعل أي من مشرفي القناة مع البوت.\n\n"
                    f"📝 الرجاء إرسال أي رسالة للبوت أولاً بالضغط على /start في المحادثة الخاصة مع البوت، ثم إعادة المحاولة."
                )
                try:
                    # محاولة إرسال الرسالة في القناة
                    import asyncio
                    notice = await bot.send_message(message.chat.id, error_msg, parse_mode='HTML')
                    await asyncio.sleep(5)
                    try:
                        await bot.delete_message(message.chat.id, message.message_id)
                        await bot.delete_message(message.chat.id, notice.message_id)
                    except:
                        pass
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال رسالة في القناة: {e}")

                logger.warning(f"⚠️ لم يتفاعل أي مشرف مع البوت في القناة {message.chat.id}")
                return

        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات المشرفين: {e}")
            return
    
    if not sender_user_id:
        logger.warning(f"⚠️ لم يتم تحديد المرسل")
        return

    text = message.text.strip()

    match = re.match(r'^تفعيل\s+(.+)$', text, re.IGNORECASE)
    if not match:
        return

    task_name = match.group(1).strip()
    user_id = sender_user_id
    chat_id = message.chat.id

    if message.chat.type in ['group', 'supergroup']:
        is_admin = await is_user_admin(bot, chat_id, user_id)
        if not is_admin:
            logger.info(f"⚠️ المستخدم {user_id} ليس مشرفاً في المجموعة {chat_id}")
            return

    manager = ForwardingManager()
    all_tasks = manager.get_all_tasks()

    admin_task = None
    admin_task_id = None
    for tid, task in all_tasks.items():
        if task.name.lower() == task_name.lower():
            admin_task = task
            admin_task_id = tid
            break

    if not admin_task or admin_task_id is None:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"❌ <b>المهمة غير موجودة</b>\n\n"
                f"لم يتم العثور على مهمة باسم: <b>{task_name}</b>",
                parse_mode='HTML'
            )
        return

    if not admin_task.is_active:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"⚠️ <b>المهمة غير نشطة</b>\n\n"
                f"المهمة <b>{task_name}</b> معطلة حالياً.",
                parse_mode='HTML'
            )
        return

    channel_manager = UserChannelManager(user_id)
    if not channel_manager.channel_exists(chat_id):
        chat = await bot.get_chat(chat_id)
        channel_manager.add_channel(
            channel_id=chat_id,
            title=chat.title or "قناة بدون اسم",
            username=chat.username,
            chat_type=chat.type
        )

    user_task_manager = UserTaskManager(user_id)

    # التحقق من وجود المهمة في ملفات المستخدم
    user_tasks = user_task_manager.get_all_tasks()
    orphan_user_task_id = None

    for task_id, task in user_tasks.items():
        if task.admin_task_id == admin_task_id and task.target_channel['id'] == chat_id:
            # وجدنا مهمة مستخدم مطابقة - نتحقق من وجودها في المهمة الإدارية
            target_exists_in_admin = any(
                target.get('id') == chat_id and 
                target.get('user_id') == user_id
                for target in admin_task.target_channels
            )

            if target_exists_in_admin:
                # المهمة موجودة في كلا الملفين - تفعيل صحيح
                logger.info(f"ℹ️ المهمة موجودة بالفعل وصحيحة في ملفات المستخدم {user_id}")
                if message.chat.type in ['group', 'supergroup']:
                    await message.reply(
                        f"ℹ️ <b>القناة مفعلة مسبقاً</b>\n\n"
                        f"هذه القناة مفعلة بالفعل للمهمة: <b>{task_name}</b>",
                        parse_mode='HTML'
                    )
                elif message.chat.type == 'channel':
                    try:
                        notice_msg = await bot.send_message(
                            chat_id,
                            f"ℹ️ <b>القناة مفعلة مسبقاً</b>\n\n"
                            f"هذه القناة مفعلة بالفعل للمهمة: <b>{task_name}</b>",
                            parse_mode='HTML'
                        )
                        import asyncio
                        await asyncio.sleep(3)
                        try:
                            await bot.delete_message(chat_id, message.message_id)
                            await bot.delete_message(chat_id, notice_msg.message_id)
                        except:
                            pass
                    except Exception as e:
                        logger.error(f"❌ خطأ في إرسال إشعار في القناة: {e}")
                return
            else:
                # المهمة موجودة في ملف المستخدم لكن ليست في المهمة الإدارية - يتيمة
                orphan_user_task_id = task_id
                logger.info(f"🔄 وجدنا مهمة يتيمة في ملف المستخدم - سنحذفها وإعادة إنشائها")
                break

    # حذف المهمة اليتيمة من ملف المستخدم إذا وجدت
    if orphan_user_task_id:
        user_task_manager.delete_task(orphan_user_task_id)
        logger.info(f"🗑 تم حذف المهمة اليتيمة #{orphan_user_task_id} من ملف المستخدم")

    # الحصول على معلومات القناة
    chat_info = await bot.get_chat(chat_id)

    # التحقق من صلاحيات البوت في القناة
    from channel_verification import ChannelVerification
    bot_has_perms, bot_error = await ChannelVerification.check_bot_permissions(bot, chat_id)
    
    if not bot_has_perms:
        logger.error(f"❌ البوت لا يملك الصلاحيات المطلوبة في القناة {chat_id}")
        
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"❌ <b>خطأ في الصلاحيات</b>\n\n"
                f"{bot_error}\n\n"
                f"💡 يرجى منح البوت صلاحيات الإشراف والنشر في القناة.",
                parse_mode='HTML'
            )
        elif message.chat.type == 'channel':
            try:
                error_msg = await bot.send_message(
                    chat_id,
                    f"❌ <b>خطأ في الصلاحيات</b>\n\n"
                    f"{bot_error}\n\n"
                    f"💡 يرجى منح البوت صلاحيات الإشراف والنشر.",
                    parse_mode='HTML'
                )
                import asyncio
                await asyncio.sleep(5)
                try:
                    await bot.delete_message(chat_id, message.message_id)
                    await bot.delete_message(chat_id, error_msg.message_id)
                except:
                    pass
            except Exception as e:
                logger.error(f"❌ خطأ في إرسال رسالة في القناة: {e}")
        
        # إرسال إشعار للمستخدم
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>فشل تفعيل المهمة</b>\n\n"
                f"📰 المهمة: <b>{task_name}</b>\n"
                f"📣 القناة: <b>{chat_info.title}</b>\n\n"
                f"{bot_error}\n\n"
                f"💡 يرجى منح البوت صلاحيات الإشراف والنشر في القناة.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f"⚠️ لم يتم إرسال إشعار للمستخدم {user_id}: {e}")
        
        return

    # البحث عن المستخدم القديم إذا كانت القناة مفعلة
    old_user_id = None
    old_user_task_id = None
    removed_orphan = False

    for idx in range(len(admin_task.target_channels) - 1, -1, -1):
        target = admin_task.target_channels[idx]
        if target.get('id') == chat_id:
            if target.get('user_id') == user_id:
                # نفس المستخدم - هدف يتيم
                logger.info(f"🔄 إزالة القناة {chat_id} من المهمة الإدارية (يتيمة)")
                admin_task.target_channels.pop(idx)
                removed_orphan = True
            elif target.get('user_id') and target.get('user_id') != user_id:
                # مستخدم مختلف - سنحذف مهمته ونستبدله بالمستخدم الجديد
                old_user_id = target.get('user_id')
                old_user_task_id = target.get('user_task_id')
                logger.info(f"🔄 القناة {chat_id} موجودة للمستخدم القديم {old_user_id} - سيتم نقلها للمستخدم الجديد {user_id}")
                admin_task.target_channels.pop(idx)
                removed_orphan = True

    # حذف المهمة من ملف المستخدم القديم إذا وجد
    if old_user_id and old_user_task_id:
        try:
            old_user_task_manager = UserTaskManager(old_user_id)
            old_user_task_manager.delete_task(old_user_task_id)
            logger.info(f"✅ تم حذف المهمة #{old_user_task_id} من ملف المستخدم القديم {old_user_id}")

            # إرسال إشعار للمستخدم القديم
            try:
                await bot.send_message(
                    old_user_id,
                    f"⚠️ <b>تنبيه: تم نقل القناة</b>\n\n"
                    f"تم نقل القناة من قائمة مهامك لأن مستخدم آخر قام بتفعيلها.\n\n"
                    f"📰 المهمة: <b>{task_name}</b>\n"
                    f"📣 القناة: <b>{chat_info.title}</b>",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.warning(f"⚠️ لم يتم إرسال إشعار للمستخدم القديم {old_user_id}: {e}")
        except Exception as e:
            logger.error(f"❌ خطأ في حذف مهمة المستخدم القديم: {e}")

    if removed_orphan:
        manager.save_tasks(manager.get_all_tasks())
        logger.info(f"🔄 تم تنظيف القناة من المهمة الإدارية")

    source_channels = admin_task.source_channels
    if not source_channels:
        return

    source_channel = source_channels[0]

    target_channel_info = {
        'id': chat_id,
        'title': chat_info.title,
        'username': chat_info.username,
        'user_id': user_id,
        'user_task_id': None # سيتم تعيينه بعد إضافة المهمة
    }

    # إنشاء اسم مخصص للمهمة: اسم مهمة المشرف --< اسم قناة الهدف
    custom_task_name = f"{task_name} --< {target_channel_info['title']}"

    # إنشاء مهمة المستخدم
    user_task_manager = UserTaskManager(user_id)
    user_task_id = user_task_manager.add_task(
        admin_task_id=admin_task_id,
        admin_task_name=custom_task_name,
        target_channel=target_channel_info
    )

    logger.info(f"✅ تم إنشاء مهمة المستخدم #{user_task_id} للمستخدم {user_id}")

    target_channel_info['user_task_id'] = user_task_id # تحديث user_task_id في target_channel_info

    fm = ForwardingManager() # instantiate manager for saving tasks
    # التحقق من المهمة الإدارية وإضافة الهدف بشكل صحيح
    admin_task = fm.get_task(admin_task_id)
    if admin_task:
        # التحقق من عدم وجود الهدف بنفس المستخدم مسبقاً (منع التكرار)
        user_target_exists = any(
            target['id'] == chat_id and target.get('user_id') == user_id
            for target in admin_task.target_channels
        )

        if not user_target_exists:
            # إضافة القناة كهدف للمستخدم
            admin_target = {
                'id': chat_id,
                'title': chat_info.title or "قناة بدون اسم",
                'username': chat_info.username,
                'user_id': user_id,
                'user_task_id': user_task_id
            }
            admin_task.target_channels.append(admin_target)

            all_tasks = fm.get_all_tasks()
            all_tasks[admin_task_id] = admin_task
            fm.save_tasks(all_tasks)

            logger.info(f"✅ تمت إضافة القناة {chat_id} كهدف للمستخدم {user_id} في المهمة #{admin_task_id}")
        else:
            logger.info(f"ℹ️ الهدف موجود بالفعل في المهمة الإدارية")


    # إعادة تحميل النظام المتوازي لتحديث الأهداف
    import parallel_forwarding_system
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()
        logger.info(f"🔄 تم إعادة تحميل النظام المتوازي - دمج قناة المستخدم {user_id} مع المهمة #{admin_task_id}")

    logger.info(f"✅ تم تفعيل المهمة {task_name} للمستخدم {user_id} في القناة {chat_id}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 إدارة المهام الإخبارية", callback_data="user_manage_tasks")]
    ])

    try:
        await bot.send_message(
            user_id,
            f"✅ <b>تم تفعيل النشر التلقائي بنجاح!</b>\n\n"
            f"📰 <b>المهمة:</b> {custom_task_name}\n"
            f"📢 <b>من:</b> {source_channel['title']}\n"
            f"📣 <b>إلى:</b> {target_channel_info['title']}\n\n"
            f"سيتم نسخ المحتوى تلقائياً من المصدر إلى قناتك.",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        logger.info(f"✅ تم إرسال إشعار التفعيل للمستخدم {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ لم يتم إرسال إشعار للمستخدم {user_id}: {e}")
        logger.info(f"💡 على المستخدم بدء محادثة مع البوت بإرسال /start للحصول على الإشعارات")

    if message.chat.type in ['group', 'supergroup']:
        await message.reply(
            f"✅ <b>تم تفعيل النشر التلقائي</b>\n\n"
            f"📰 المهمة: <b>{custom_task_name}</b>\n"
            f"سيتم النشر تلقائياً في هذه المجموعة.",
            parse_mode='HTML'
        )
    elif message.chat.type == 'channel':
        try:
            import asyncio
            success_msg = await bot.send_message(
                chat_id,
                f"✅ <b>تم تفعيل النشر التلقائي بنجاح!</b>\n\n"
                f"📰 المهمة: <b>{custom_task_name}</b>\n"
                f"سيتم نسخ المحتوى تلقائياً إلى هذه القناة.",
                parse_mode='HTML'
            )

            await asyncio.sleep(2)

            try:
                await bot.delete_message(chat_id, message.message_id)
            except:
                pass

            try:
                await bot.delete_message(chat_id, success_msg.message_id)
            except:
                pass

        except Exception as e:
            logger.error(f"❌ خطأ في إرسال رسالة في القناة: {e}")

async def process_deactivation(message: Message, bot: Bot):
    """معالجة أمر التعطيل"""
    logger.info(f"🔍 بدء معالجة أمر التعطيل من {message.chat.type}: {message.chat.id}")

    if not message.text:
        logger.info(f"⚠️ الرسالة لا تحتوي على نص")
        return

    logger.info(f"📝 النص: {message.text}")

    sender = message.from_user
    sender_user_id = None
    
    # في المجموعات، المستخدم يرسل بـ from_user
    if sender:
        sender_user_id = sender.id
        logger.info(f"👤 المرسل: {sender_user_id} ({sender.first_name})")
    elif message.sender_chat:
        from channel_detection import channel_owner_map
        sender_user_id = channel_owner_map.get(message.chat.id)

        if sender_user_id:
            logger.info(f"👤 تم تحديد صاحب القناة من السجل: {sender_user_id}")
        else:
            try:
                admins = await bot.get_chat_administrators(message.chat.id)
                bot_info = await bot.get_me()
                for admin in admins:
                    if not admin.user.is_bot and admin.user.id != bot_info.id:
                        sender_user_id = admin.user.id
                        logger.info(f"👤 تم تحديد المشرف: {admin.user.id} ({admin.user.first_name})")
                        break

                if not sender_user_id:
                    logger.warning(f"⚠️ لم يتم العثور على مشرف إنسان في القناة {message.chat.id}")
                    return
            except Exception as e:
                logger.error(f"خطأ في الحصول على معلومات المشرفين: {e}")
                return
    
    if not sender_user_id:
        logger.warning(f"⚠️ لم يتم تحديد المرسل")
        return

    text = message.text.strip()

    match = re.match(r'^تعطيل\s+(.+)$', text, re.IGNORECASE)
    if not match:
        return

    task_name = match.group(1).strip()
    user_id = sender_user_id
    chat_id = message.chat.id

    if message.chat.type in ['group', 'supergroup']:
        is_admin = await is_user_admin(bot, chat_id, user_id)
        if not is_admin:
            logger.info(f"⚠️ المستخدم {user_id} ليس مشرفاً في المجموعة {chat_id}")
            return

    manager = ForwardingManager()
    all_tasks = manager.get_all_tasks()

    admin_task = None
    admin_task_id = None
    for tid, task in all_tasks.items():
        if task.name.lower() == task_name.lower():
            admin_task = task
            admin_task_id = tid
            break

    if not admin_task or admin_task_id is None:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"❌ <b>المهمة غير موجودة</b>\n\n"
                f"لم يتم العثور على مهمة باسم: <b>{task_name}</b>",
                parse_mode='HTML'
            )
        return

    user_task_manager = UserTaskManager(user_id)
    user_tasks = user_task_manager.get_all_tasks()

    user_task_to_disable = None
    user_task_id_to_disable = None

    for task_id, task in user_tasks.items():
        if task.admin_task_id == admin_task_id and task.target_channel['id'] == chat_id:
            user_task_to_disable = task
            user_task_id_to_disable = task_id
            break

    if not user_task_to_disable or user_task_id_to_disable is None:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"⚠️ <b>المهمة غير مفعلة</b>\n\n"
                f"لم يتم العثور على مهمة نشطة باسم <b>{task_name}</b> في هذه القناة.",
                parse_mode='HTML'
            )
        return

    if not user_task_to_disable.is_active:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply(
                f"ℹ️ <b>المهمة معطلة مسبقاً</b>\n\n"
                f"المهمة <b>{task_name}</b> معطلة بالفعل.",
                parse_mode='HTML'
            )
        return

    user_task_manager.toggle_task(user_task_id_to_disable)
    logger.info(f"⏸️ تم تعطيل مهمة المستخدم #{user_task_id_to_disable}")

    fm = ForwardingManager()
    all_tasks = fm.get_all_tasks()
    admin_task = all_tasks.get(admin_task_id)

    if admin_task:
        target_found_idx = None
        for idx, target in enumerate(admin_task.target_channels):
            if target['id'] == chat_id and target.get('user_id') == user_id:
                target_found_idx = idx
                break

        if target_found_idx is not None:
            admin_task.target_channels.pop(target_found_idx)
            logger.info(f"⏸️ تم حذف القناة {chat_id} من المهمة الإدارية #{admin_task_id}")
            fm.save_tasks(all_tasks)

    import parallel_forwarding_system
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()
        logger.info(f"🔄 تم إعادة تحميل النظام المتوازي بعد تعطيل المهمة")

    logger.info(f"✅ تم تعطيل المهمة {task_name} للمستخدم {user_id} في القناة {chat_id}")

    try:
        await bot.send_message(
            user_id,
            f"⏸️ <b>تم تعطيل النشر التلقائي</b>\n\n"
            f"📰 <b>المهمة:</b> {task_name}\n"
            f"📣 <b>القناة:</b> {user_task_to_disable.target_channel['title']}\n\n"
            f"لن يتم نسخ المحتوى إلى قناتك.\n"
            f"يمكنك إعادة التفعيل في أي وقت.",
            parse_mode='HTML'
        )
        logger.info(f"✅ تم إرسال إشعار التعطيل للمستخدم {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ لم يتم إرسال إشعار للمستخدم {user_id}: {e}")

    if message.chat.type in ['group', 'supergroup']:
        await message.reply(
            f"⏸️ <b>تم تعطيل النشر التلقائي</b>\n\n"
            f"📰 المهمة: <b>{task_name}</b>\n"
            f"لن يتم النشر في هذه المجموعة.",
            parse_mode='HTML'
        )
    elif message.chat.type == 'channel':
        try:
            import asyncio
            success_msg = await bot.send_message(
                chat_id,
                f"⏸️ <b>تم تعطيل النشر التلقائي</b>\n\n"
                f"📰 المهمة: <b>{task_name}</b>\n"
                f"لن يتم نسخ المحتوى إلى هذه القناة.",
                parse_mode='HTML'
            )

            await asyncio.sleep(2)

            try:
                await bot.delete_message(chat_id, message.message_id)
            except:
                pass

            try:
                await bot.delete_message(chat_id, success_msg.message_id)
            except:
                pass

        except Exception as e:
            logger.error(f"❌ خطأ في إرسال رسالة في القناة: {e}")

# تم تعطيل معالج أوامر التفعيل والتعطيل في المجموعات
# @router.message(F.text, F.chat.type.in_(['group', 'supergroup']))
# async def handle_activation_message(message: Message, bot: Bot):
#     logger.info(f"📨 استقبال رسالة من مجموعة: {message.chat.id} - النص: {message.text}")
#
#     if message.text and message.text.strip().startswith("تعطيل"):
#         await process_deactivation(message, bot)
#     else:
#         await process_activation(message, bot)