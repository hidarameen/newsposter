import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from subscription_manager import SubscriptionManager, PLAN_PRICES
from config import ADMIN_ID, USERS_DATA_DIR
import os
import json

logger = logging.getLogger(__name__)
router = Router()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_plan_duration = State()
    waiting_for_downgrade_user_id = State()
    waiting_for_log_channel = State()
    waiting_for_import_file = State()
    waiting_for_welcome_message = State()
    waiting_for_broadcast_message = State()
    waiting_for_broadcast_confirmation = State()
    waiting_for_min_subscribers = State()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from user_handlers import delete_last_panel_and_save_new

    text = """👑 <b>لوحة تحكم المشرف</b>

<b>الأوامر المتاحة:</b>

/upgrade_user - ترقية مستخدم
/downgrade_user - إلغاء ترقية مستخدم
/check_user - فحص اشتراك مستخدم
/cleanup_tasks - تنظيف المهام القديمة
/notifications - إعدادات الإشعارات
/stats - إحصائيات البوت
/check_channels - فحص جميع القنوات والمجموعات
/export - تصدير بيانات البوت
/import - استيراد بيانات البوت
/welcome - تعديل رسالة الترحيب
/broadcast - إرسال إذاعة جماعية
/min_subscribers - تحديد الحد الأدنى لعدد المشتركين
/add_forward - إنشاء مهام توجيه سريعة

📝 <b>مثال الاستخدام:</b>
<code>/upgrade_user</code>
<code>/add_forward أخبار -1001111111111 -> -1002222222222</code>
"""

    sent_message = await message.answer(text, parse_mode='HTML')
    await delete_last_panel_and_save_new(message.bot, message.from_user.id, sent_message.message_id)

@router.message(Command("upgrade_user"))
async def upgrade_user_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return

    await state.set_state(AdminStates.waiting_for_user_id)

    await message.answer(
        "👤 <b>ترقية مستخدم</b>\n\n"
        "أرسل معرف المستخدم (User ID):",
        parse_mode='HTML'
    )

@router.message(AdminStates.waiting_for_user_id)
async def process_upgrade_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(target_user_id=user_id)

        text = """💎 <b>اختر الخطة:</b>

اختر الخطة أو أدخل عدد الأيام مباشرة:

<b>الخطط الجاهزة:</b>
/plan_monthly - شهري (30 يوم)
/plan_3months - 3 شهور (90 يوم)
/plan_6months - 6 شهور (180 يوم)
/plan_yearly - سنوي (365 يوم)

<b>أو أدخل عدد الأيام مباشرة:</b>
مثال: 15
"""

        await state.set_state(AdminStates.waiting_for_plan_duration)
        await message.answer(text, parse_mode='HTML')

    except ValueError:
        await message.answer("❌ معرف المستخدم يجب أن يكون رقماً. حاول مرة أخرى:")

@router.message(AdminStates.waiting_for_plan_duration)
async def process_plan_duration(message: Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get('target_user_id')

    text = message.text.strip()

    duration_days = None
    plan_name = "مخصص"

    if text == "/plan_monthly":
        duration_days = 30
        plan_name = "شهري"
    elif text == "/plan_3months":
        duration_days = 90
        plan_name = "3 شهور"
    elif text == "/plan_6months":
        duration_days = 180
        plan_name = "6 شهور"
    elif text == "/plan_yearly":
        duration_days = 365
        plan_name = "سنوي"
    else:
        try:
            duration_days = int(text)
        except ValueError:
            await message.answer("❌ يرجى إدخال عدد الأيام أو اختيار خطة جاهزة")
            return

    sub_manager = SubscriptionManager(target_user_id)
    sub_manager.activate_subscription('premium', duration_days, is_trial=False)

    await state.clear()
    
    # إرسال إشعار ترقية الاشتراك
    from notification_manager import notification_manager
    try:
        from storage import UserStorage
        user_storage = UserStorage(target_user_id)
        user_data = user_storage.load_data()
        user_name = user_data.get('first_name', 'مستخدم')
        
        await notification_manager.notify_subscription_upgraded(
            message.bot,
            target_user_id,
            user_name,
            plan_name,
            duration_days
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار ترقية الاشتراك: {e}")

    await message.answer(
        f"✅ <b>تم ترقية المستخدم بنجاح!</b>\n\n"
        f"👤 المستخدم: <code>{target_user_id}</code>\n"
        f"📋 الخطة: {plan_name}\n"
        f"⏰ المدة: {duration_days} يوم\n\n"
        f"تم تفعيل جميع المميزات المدفوعة!",
        parse_mode='HTML'
    )

    try:
        from aiogram import Bot
        bot = message.bot
        await bot.send_message(
            target_user_id,
            f"🎉 <b>تهانينا!</b>\n\n"
            f"تم ترقية حسابك إلى النسخة المدفوعة!\n\n"
            f"📋 الخطة: {plan_name}\n"
            f"⏰ المدة: {duration_days} يوم\n\n"
            f"✨ يمكنك الآن استخدام جميع المميزات المدفوعة!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار للمستخدم: {e}")

@router.message(Command("downgrade_user"))
async def downgrade_user_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return

    await state.set_state(AdminStates.waiting_for_downgrade_user_id)

    await message.answer(
        "👤 <b>إلغاء ترقية مستخدم</b>\n\n"
        "أرسل معرف المستخدم (User ID):",
        parse_mode='HTML'
    )

@router.message(AdminStates.waiting_for_downgrade_user_id)
async def process_downgrade_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())

        sub_manager = SubscriptionManager(user_id)
        sub_manager.deactivate_premium_features()

        from user_task_manager import UserTaskManager
        task_manager = UserTaskManager(user_id)
        tasks = task_manager.get_all_tasks()

        if len(tasks) > 1:
            tasks_to_keep = list(tasks.items())[:1]
            tasks_to_disable = list(tasks.items())[1:]

            for task_id, task in tasks_to_disable:
                task_manager.toggle_task(task_id)

            await message.answer(
                f"✅ <b>تم إلغاء الترقية بنجاح!</b>\n\n"
                f"👤 المستخدم: <code>{user_id}</code>\n\n"
                f"تم تعطيل المميزات المدفوعة\n"
                f"تم تعطيل {len(tasks_to_disable)} مهمة (الحد الأقصى للمجاني: 1 مهمة)",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"✅ <b>تم إلغاء الترقية بنجاح!</b>\n\n"
                f"👤 المستخدم: <code>{user_id}</code>\n\n"
                f"تم تعطيل المميزات المدفوعة",
                parse_mode='HTML'
            )

        await state.clear()

        try:
            await message.bot.send_message(
                user_id,
                "📋 <b>إشعار</b>\n\n"
                "انتهى اشتراكك المدفوع.\n\n"
                "تم تعطيل المميزات المدفوعة.\n\n"
                "⭐ للاستمرار في استخدام جميع المميزات، يرجى تجديد اشتراكك!",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار للمستخدم: {e}")

    except ValueError:
        await message.answer("❌ معرف المستخدم يجب أن يكون رقماً. حاول مرة أخرى:")
    except Exception as e:
        logger.error(f"خطأ في إلغاء ترقية المستخدم: {e}")
        await message.answer(f"❌ حدث خطأ: {str(e)}")
        await state.clear()

@router.message(Command("check_user"))
async def check_user_subscription(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "📋 <b>فحص اشتراك مستخدم</b>\n\n"
            "الاستخدام:\n<code>/check_user USER_ID</code>\n\n"
            "مثال:\n<code>/check_user 123456789</code>",
            parse_mode='HTML'
        )
        return

    try:
        user_id = int(parts[1])

        sub_manager = SubscriptionManager(user_id)
        plan_details = sub_manager.get_plan_details()

        from user_task_manager import UserTaskManager
        task_manager = UserTaskManager(user_id)
        tasks = task_manager.get_all_tasks()

        text = f"""📊 <b>معلومات المستخدم</b>

👤 <b>User ID:</b> <code>{user_id}</code>

📋 <b>الاشتراك:</b>
• الخطة: {plan_details['plan']}
• الحالة: {"نشط ✅" if plan_details['is_active'] else "منتهي ❌"}
"""

        if plan_details['is_active']:
            text += f"""• تجريبي: {"نعم 🎁" if plan_details['is_trial'] else "لا"}
• الأيام المتبقية: {plan_details['days_remaining']} يوم
• ينتهي في: {plan_details['end_date'][:10]}
"""

        text += f"\n📊 <b>الإحصائيات:</b>\n"
        text += f"• عدد المهام: {len(tasks)}\n"
        text += f"• المهام النشطة: {len([t for t in tasks.values() if t.is_active])}"

        await message.answer(text, parse_mode='HTML')

    except ValueError:
        await message.answer("❌ معرف المستخدم يجب أن يكون رقماً")
    except Exception as e:
        logger.error(f"خطأ في فحص المستخدم: {e}")
        await message.answer(f"❌ حدث خطأ: {str(e)}")

@router.message(Command("cleanup_tasks"))
async def cleanup_tasks(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return

    deleted_settings_count = 0
    deleted_pending_count = 0

    # Clean up orphaned task settings for all users
    for user_dir_name in os.listdir(USERS_DATA_DIR):
        user_dir_path = os.path.join(USERS_DATA_DIR, user_dir_name)
        
        # تخطي الملفات (نريد المجلدات فقط)
        if not os.path.isdir(user_dir_path):
            continue
        
        # التحقق من أن اسم المجلد هو user_id صحيح
        if not user_dir_name.isdigit():
            continue
        
        user_id = int(user_dir_name)
        
        # البحث عن ملفات الإعدادات في مجلد المستخدم
        for filename in os.listdir(user_dir_path):
            if filename.startswith("task_") and filename.endswith("_settings.json"):
                # استخراج task_id من اسم الملف
                try:
                    task_id = int(filename.split("_")[1])
                except (IndexError, ValueError):
                    logger.warning(f"⚠️ اسم ملف غير صحيح: {filename}")
                    continue
                
                # التحقق من وجود المهمة في tasks.json
                from user_task_manager import UserTaskManager
                task_manager = UserTaskManager(user_id)
                tasks = task_manager.get_all_tasks()
                
                if task_id not in tasks:
                    settings_file_path = os.path.join(user_dir_path, filename)
                    try:
                        os.remove(settings_file_path)
                        deleted_settings_count += 1
                        logger.info(f"🗑️ حذف ملف إعدادات يتيم: {settings_file_path}")
                    except OSError as e:
                        logger.error(f"❌ خطأ في حذف الملف {settings_file_path}: {e}")

    # Clean up expired pending tasks
    pending_tasks_file = os.path.join(USERS_DATA_DIR, "pending_tasks.json")
    if os.path.exists(pending_tasks_file):
        try:
            with open(pending_tasks_file, 'r') as f:
                pending_tasks = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error reading pending_tasks.json: {e}")
            await message.answer("❌ حدث خطأ أثناء قراءة ملف المهام المعلقة.")
            return

        current_time = int(os.path.getmtime(pending_tasks_file)) # Using modification time as a proxy for task creation/update time
        updated_pending_tasks = {}
        for task_id, task_data in pending_tasks.items():
            # Assuming tasks have an 'expires_at' timestamp. If not, this logic needs adjustment.
            # For now, let's consider tasks older than a certain threshold (e.g., 7 days) as expired.
            # A more robust solution would involve checking actual expiration timestamps within task_data.
            task_mtime = os.path.getmtime(os.path.join(USERS_DATA_DIR, f"task_{task_id}.json")) if os.path.exists(os.path.join(USERS_DATA_DIR, f"task_{task_id}.json")) else current_time
            if current_time - task_mtime < 7 * 24 * 60 * 60: # Keep tasks for 7 days
                updated_pending_tasks[task_id] = task_data
            else:
                deleted_pending_count += 1
                logger.info(f"Deleted expired pending task: {task_id}")

        if deleted_pending_count > 0:
            try:
                with open(pending_tasks_file, 'w') as f:
                    json.dump(updated_pending_tasks, f, indent=4)
            except OSError as e:
                logger.error(f"Error writing updated pending_tasks.json: {e}")
                await message.answer("❌ حدث خطأ أثناء تحديث ملف المهام المعلقة.")
                return

    await message.answer(
        f"✅ <b>تم تنظيف المهام بنجاح!</b>\n\n"
        f"• تم حذف {deleted_settings_count} ملف إعدادات مهمة قديمة.\n"
        f"• تم حذف {deleted_pending_count} مهمة معلقة منتهية الصلاحية.",
        parse_mode='HTML'
    )

@router.message(Command("notifications"))
async def notifications_settings(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from notification_manager import notification_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    log_channel = notification_manager.get_log_channel()
    channel_status = f"<code>{log_channel}</code>" if log_channel else "غير محددة"
    
    text = f"""🔔 <b>إعدادات الإشعارات</b>

📢 <b>قناة الإشعارات:</b> {channel_status}

<b>حالة الإشعارات:</b>"""
    
    keyboard_buttons = []
    
    events = {
        "new_user": "مستخدم جديد",
        "bot_added_to_channel": "إضافة البوت لقناة",
        "bot_restricted": "تقييد البوت",
        "bot_removed": "حذف البوت من قناة",
        "task_created": "إنشاء مهمة",
        "task_toggled": "تفعيل/تعطيل مهمة",
        "task_deleted": "حذف مهمة",
        "forwarding_report": "تقرير التوجيه",
        "subscription_upgraded": "ترقية اشتراك",
        "subscription_expired": "انتهاء اشتراك"
    }
    
    for event_id, event_name in events.items():
        is_enabled = notification_manager.is_event_enabled(event_id)
        status_icon = "✅" if is_enabled else "❌"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {event_name}",
                callback_data=f"notif_toggle:{event_id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⚙️ تغيير قناة الإشعارات",
            callback_data="notif_set_channel"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

@router.callback_query(F.data.startswith("notif_toggle:"))
async def toggle_notification(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from notification_manager import notification_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    event_type = callback.data.split(":")[1]
    current_status = notification_manager.is_event_enabled(event_type)
    notification_manager.toggle_event(event_type, not current_status)
    
    log_channel = notification_manager.get_log_channel()
    channel_status = f"<code>{log_channel}</code>" if log_channel else "غير محددة"
    
    text = f"""🔔 <b>إعدادات الإشعارات</b>

📢 <b>قناة الإشعارات:</b> {channel_status}

<b>حالة الإشعارات:</b>"""
    
    keyboard_buttons = []
    
    events = {
        "new_user": "مستخدم جديد",
        "bot_added_to_channel": "إضافة البوت لقناة",
        "bot_restricted": "تقييد البوت",
        "bot_removed": "حذف البوت من قناة",
        "task_created": "إنشاء مهمة",
        "task_toggled": "تفعيل/تعطيل مهمة",
        "task_deleted": "حذف مهمة",
        "forwarding_report": "تقرير التوجيه",
        "subscription_upgraded": "ترقية اشتراك",
        "subscription_expired": "انتهاء اشتراك"
    }
    
    for event_id, event_name in events.items():
        is_enabled = notification_manager.is_event_enabled(event_id)
        status_icon = "✅" if is_enabled else "❌"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {event_name}",
                callback_data=f"notif_toggle:{event_id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⚙️ تغيير قناة الإشعارات",
            callback_data="notif_set_channel"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer("تم تحديث الإعدادات")

@router.callback_query(F.data == "notif_set_channel")
async def set_log_channel_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_log_channel)
    await callback.message.answer(
        "📢 <b>تعيين قناة الإشعارات</b>\n\n"
        "أرسل معرف قناة الإشعارات (Channel ID):\n\n"
        "💡 للحصول على معرف القناة، أضف البوت كمشرف في القناة ثم استخدم @userinfobot",
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_log_channel)
async def process_log_channel(message: Message, state: FSMContext):
    from notification_manager import notification_manager
    
    try:
        channel_id = int(message.text.strip())
        
        try:
            chat = await message.bot.get_chat(channel_id)
            if chat.type not in ['channel', 'supergroup']:
                await message.answer("❌ المعرف المرسل ليس قناة صالحة")
                return
        except Exception as e:
            await message.answer(f"❌ لا يمكن الوصول إلى القناة. تأكد من إضافة البوت كمشرف.\n\nالخطأ: {str(e)}")
            return
        
        notification_manager.set_log_channel(channel_id)
        await state.clear()
        
        await message.answer(
            f"✅ <b>تم تعيين قناة الإشعارات بنجاح!</b>\n\n"
            f"📢 القناة: {chat.title}\n"
            f"🆔 المعرف: <code>{channel_id}</code>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await message.answer("❌ المعرف يجب أن يكون رقماً. حاول مرة أخرى:")

@router.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from stats_manager import stats_manager
    from forwarding_manager import ForwardingManager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from user_handlers import delete_last_panel_and_save_new
    
    stats_manager.recompute_all_stats()
    
    stats = stats_manager.get_stats()
    fm = ForwardingManager()
    admin_tasks = fm.get_all_tasks()
    task_stats = stats_manager.get_admin_task_stats(admin_tasks)
    
    text = f"""📊 <b>إحصائيات البوت</b>

👥 <b>المستخدمون:</b>
• الإجمالي: {stats['total_users']}
• مدفوع: {stats['premium_users']}
• مجاني: {stats['free_users']}

📰 <b>المهام:</b>
• الإجمالي: {stats['total_tasks']}
• نشطة: {stats['active_tasks']}
• معطلة: {stats['inactive_tasks']}

📢 <b>القنوات:</b>
• العدد: {stats['total_channels']}

⏰ <b>آخر تحديث:</b> {stats.get('last_updated', 'غير محدد')[:19] if stats.get('last_updated') else 'غير محدد'}
"""
    
    keyboard_buttons = [[
        InlineKeyboardButton(
            text="📋 تفاصيل مهام المشرف",
            callback_data="stats_admin_tasks"
        )
    ]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    sent_message = await message.answer(text, parse_mode='HTML', reply_markup=keyboard)
    await delete_last_panel_and_save_new(message.bot, message.from_user.id, sent_message.message_id)

@router.callback_query(F.data == "stats_admin_tasks")
async def show_admin_task_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from stats_manager import stats_manager
    from forwarding_manager import ForwardingManager
    
    fm = ForwardingManager()
    admin_tasks = fm.get_all_tasks()
    task_stats = stats_manager.get_admin_task_stats(admin_tasks)
    
    if not task_stats:
        await callback.answer("لا توجد مهام مشرف", show_alert=True)
        return
    
    text = "📋 <b>تفاصيل مهام المشرف:</b>\n\n"
    
    for task_id, stats in task_stats.items():
        text += f"📰 <b>{stats['task_name']}</b>\n"
        text += f"   📢 المصدر: {stats['source_channel']}\n"
        text += f"   📊 الأهداف: {stats['total_targets']}\n"
        text += f"   ✅ نشطة: {stats['active_targets']}\n"
        text += f"   ⏸️ معطلة: {stats['inactive_targets']}\n\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 رجوع", callback_data="stats_back")
    ]])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "stats_back")
async def stats_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from stats_manager import stats_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    stats = stats_manager.get_stats()
    
    text = f"""📊 <b>إحصائيات البوت</b>

👥 <b>المستخدمون:</b>
• الإجمالي: {stats['total_users']}
• مدفوع: {stats['premium_users']}
• مجاني: {stats['free_users']}

📰 <b>المهام:</b>
• الإجمالي: {stats['total_tasks']}
• نشطة: {stats['active_tasks']}
• معطلة: {stats['inactive_tasks']}

📢 <b>القنوات:</b>
• العدد: {stats['total_channels']}

⏰ <b>آخر تحديث:</b> {stats.get('last_updated', 'غير محدد')[:19] if stats.get('last_updated') else 'غير محدد'}
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📋 تفاصيل مهام المشرف",
            callback_data="stats_admin_tasks"
        )
    ]])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()
@router.message(Command("export"))
async def export_data(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    await message.answer("⏳ <b>جاري تصدير البيانات...</b>\n\nقد يستغرق هذا بضع ثوانٍ.", parse_mode="HTML")
    
    try:
        from export_import_manager import export_import_manager
        
        # تصدير البيانات
        export_data_dict = export_import_manager.export_all_data()
        
        # حفظ في ملف
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bot_export_{timestamp}.json"
        filepath = export_import_manager.export_to_file(filename)
        
        # إرسال الملف للمشرف
        from aiogram.types import FSInputFile
        file = FSInputFile(filepath)
        
        stats_text = f"""✅ <b>تم التصدير بنجاح!</b>

📊 <b>الإحصائيات:</b>
👥 المستخدمون: {len(export_data_dict.get("users", {}))}
📰 مهام المشرف: {len(export_data_dict.get("admin_tasks", {}))}
📅 تاريخ التصدير: {export_data_dict.get("export_date", "غير محدد")[:19]}

💾 الملف: <code>{filename}</code>
"""
        
        await message.answer_document(
            document=file,
            caption=stats_text,
            parse_mode="HTML"
        )
        
        # حذف الملف المؤقت
        import os
        os.remove(filepath)
        
    except Exception as e:
        logger.error(f"خطأ في التصدير: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>فشل التصدير!</b>\n\n"
            f"الخطأ: {str(e)}",
            parse_mode="HTML"
        )

@router.message(Command("import"))
async def import_data_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_import")]
    ])
    
    await state.set_state(AdminStates.waiting_for_import_file)
    await message.answer(
        "📥 <b>استيراد بيانات البوت</b>\n\n"
        "⚠️ <b>تحذير:</b> عملية الاستيراد ستستبدل البيانات الحالية!\n\n"
        "📎 أرسل ملف JSON المُصدّر سابقاً:\n\n"
        "💡 تأكد من أن الملف بصيغة JSON وتم تصديره من نفس إصدار البوت.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(AdminStates.waiting_for_import_file)
async def process_import_file(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("❌ يرجى إرسال ملف JSON")
        return
    
    if not message.document.file_name.endswith(".json"):
        await message.answer("❌ يرجى إرسال ملف بصيغة JSON")
        return
    
    await message.answer("⏳ <b>جاري استيراد البيانات...</b>\n\nقد يستغرق هذا بضع دقائق.", parse_mode="HTML")
    
    try:
        # تحميل الملف
        file = await message.bot.get_file(message.document.file_id)
        file_path = f"temp_import_{message.from_user.id}.json"
        await message.bot.download_file(file.file_path, file_path)
        
        # استيراد البيانات
        from export_import_manager import export_import_manager
        stats = export_import_manager.import_from_file(file_path, overwrite=True)
        
        # حذف الملف المؤقت
        import os
        os.remove(file_path)
        
        await state.clear()
        
        users_count = stats["users_imported"]
        tasks_count = stats["admin_tasks_imported"]
        errors_count = stats["errors"]
        
        await message.answer(
            f"✅ <b>تم الاستيراد بنجاح!</b>\n\n"
            f"📊 <b>الإحصائيات:</b>\n"
            f"👥 المستخدمون: {users_count}\n"
            f"📰 مهام المشرف: {tasks_count}\n"
            f"❌ الأخطاء: {errors_count}\n\n"
            f"💡 قد تحتاج لإعادة تشغيل البوت لتطبيق جميع التغييرات.",
            parse_mode="HTML"
        )
        
        # إعادة تحميل النظام المتوازي
        import parallel_forwarding_system
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()
            logger.info("تم إعادة تحميل النظام المتوازي بعد الاستيراد")
        
    except Exception as e:
        logger.error(f"خطأ في الاستيراد: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>فشل الاستيراد!</b>\n\n"
            f"الخطأ: {str(e)}",
            parse_mode="HTML"
        )
        await state.clear()

@router.callback_query(F.data == "cancel_import")
async def cancel_import(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>تم إلغاء عملية الاستيراد</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("welcome"))
async def welcome_message_settings(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from welcome_message_manager import welcome_message_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    config = welcome_message_manager.get_config()
    
    status = "مفعلة" if config.get('use_custom', False) else "معطلة"
    current_message = config.get('message', 'لا توجد رسالة مخصصة')
    
    if len(current_message) > 200:
        current_message = current_message[:200] + "..."
    
    text = f"""💬 <b>رسالة الترحيب</b>

📊 <b>الحالة:</b> {status}

📝 <b>الرسالة الحالية:</b>
{current_message if config.get('use_custom', False) else 'يتم استخدام الرسالة الافتراضية'}

💡 يمكنك تعديل رسالة الترحيب التي تظهر للمستخدمين عند بدء البوت."""
    
    keyboard_buttons = []
    
    if config.get('use_custom', False):
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ تعطيل الرسالة المخصصة", callback_data="welcome_disable")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ تعديل الرسالة", callback_data="welcome_edit")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

@router.callback_query(F.data == "welcome_edit")
async def welcome_edit_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_welcome_message)
    
    await callback.message.edit_text(
        "✏️ <b>تعديل رسالة الترحيب</b>\n\n"
        "أرسل الرسالة الجديدة:\n\n"
        "💡 <b>ملاحظات:</b>\n"
        "• يمكنك استخدام HTML للتنسيق\n"
        "• استخدم {name} لإدراج اسم المستخدم\n"
        "• مثال: <code>مرحباً {name}! 👋</code>\n\n"
        "📝 أرسل الرسالة الآن:",
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_welcome_message)
async def process_welcome_message(message: Message, state: FSMContext):
    from welcome_message_manager import welcome_message_manager
    
    try:
        custom_message = message.text or message.caption or ""
        
        if not custom_message:
            await message.answer("❌ يرجى إرسال نص الرسالة")
            return
        
        # حفظ الرسالة
        welcome_message_manager.set_welcome_message(custom_message)
        
        await state.clear()
        
        # عرض معاينة
        preview = custom_message.replace('{name}', message.from_user.first_name)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_welcome")]
        ])
        
        await message.answer(
            f"✅ <b>تم حفظ رسالة الترحيب بنجاح!</b>\n\n"
            f"📝 <b>معاينة:</b>\n\n{preview}",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"خطأ في حفظ رسالة الترحيب: {e}")
        await message.answer(
            f"❌ <b>فشل حفظ الرسالة!</b>\n\n"
            f"الخطأ: {str(e)}",
            parse_mode='HTML'
        )
        await state.clear()

@router.callback_query(F.data == "welcome_disable")
async def welcome_disable(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from welcome_message_manager import welcome_message_manager
    
    try:
        welcome_message_manager.disable_custom_message()
        
        await callback.message.edit_text(
            "✅ <b>تم تعطيل الرسالة المخصصة</b>\n\n"
            "سيتم استخدام الرسالة الافتراضية.",
            parse_mode='HTML'
        )
        await callback.answer("تم التعطيل")
        
    except Exception as e:
        logger.error(f"خطأ في تعطيل الرسالة: {e}")
        await callback.answer(f"❌ خطأ: {str(e)}", show_alert=True)

@router.callback_query(F.data == "back_to_welcome")
async def back_to_welcome(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from welcome_message_manager import welcome_message_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    config = welcome_message_manager.get_config()
    
    status = "مفعلة" if config.get('use_custom', False) else "معطلة"
    current_message = config.get('message', 'لا توجد رسالة مخصصة')
    
    if len(current_message) > 200:
        current_message = current_message[:200] + "..."
    
    text = f"""💬 <b>رسالة الترحيب</b>

📊 <b>الحالة:</b> {status}

📝 <b>الرسالة الحالية:</b>
{current_message if config.get('use_custom', False) else 'يتم استخدام الرسالة الافتراضية'}

💡 يمكنك تعديل رسالة الترحيب التي تظهر للمستخدمين عند بدء البوت."""
    
    keyboard_buttons = []
    
    if config.get('use_custom', False):
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ تعطيل الرسالة المخصصة", callback_data="welcome_disable")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ تعديل الرسالة", callback_data="welcome_edit")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.message(Command("broadcast"))
async def broadcast_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 إرسال للمستخدمين", callback_data="broadcast_users")],
        [InlineKeyboardButton(text="📢 إرسال لجميع الأهداف", callback_data="broadcast_all_targets")],
        [InlineKeyboardButton(text="📺 القنوات فقط", callback_data="broadcast_channels_only")],
        [InlineKeyboardButton(text="👥 المجموعات فقط", callback_data="broadcast_groups_only")],
        [InlineKeyboardButton(text="🌐 الجميع (مستخدمين + أهداف)", callback_data="broadcast_everyone")]
    ])
    
    await message.answer(
        "📡 <b>نظام الإذاعة الجماعية</b>\n\n"
        "اختر الفئة المستهدفة للإرسال:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("broadcast_"))
async def broadcast_type_selected(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    # معالجة الإلغاء
    if callback.data == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text(
            "❌ <b>تم إلغاء الإذاعة</b>",
            parse_mode='HTML'
        )
        await callback.answer("تم الإلغاء")
        return
    
    broadcast_type = callback.data.replace("broadcast_", "")


@router.message(Command("check_channels"))
async def check_channels_command(message: Message):
    """أمر فحص جميع القنوات والمجموعات"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from user_handlers import delete_last_panel_and_save_new
    
    wait_msg = await message.answer(
        "⏳ <b>جاري فحص جميع القنوات والمجموعات...</b>\n\n"
        "قد يستغرق هذا بضع ثوانٍ حسب عدد القنوات.",
        parse_mode='HTML'
    )
    
    try:
        from channels_checker import channels_checker
        
        # إجراء الفحص الشامل
        check_results = await channels_checker.check_all_channels(message.bot)
        
        # إنشاء التقرير
        report = await channels_checker.generate_report(message.bot, check_results)
        
        # حذف رسالة الانتظار
        await wait_msg.delete()
        
        # إرسال التقرير (قد يكون طويل، نقسمه إذا لزم الأمر)
        max_length = 4000
        if len(report) <= max_length:
            await message.answer(report, parse_mode='HTML', disable_web_page_preview=True)
        else:
            # تقسيم التقرير لأجزاء
            parts = []
            current_part = ""
            
            for line in report.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            # إرسال الأجزاء
            for i, part in enumerate(parts, 1):
                header = f"📄 <b>الجزء {i}/{len(parts)}</b>\n\n" if len(parts) > 1 else ""
                await message.answer(header + part, parse_mode='HTML', disable_web_page_preview=True)
        
        logger.info(f"✅ تم إرسال تقرير فحص القنوات للمشرف {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في فحص القنوات: {e}", exc_info=True)
        await wait_msg.edit_text(
            f"❌ <b>حدث خطأ أثناء الفحص!</b>\n\n"
            f"الخطأ: {str(e)}",
            parse_mode='HTML'
        )

    
    # حفظ نوع الإذاعة
    await state.update_data(broadcast_type=broadcast_type)
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    
    type_names = {
        'users': 'المستخدمين',
        'all_targets': 'جميع الأهداف (قنوات + مجموعات)',
        'channels_only': 'القنوات فقط',
        'groups_only': 'المجموعات فقط',
        'everyone': 'الجميع (مستخدمين + أهداف)'
    }
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="broadcast_cancel_input")]
    ])
    
    await callback.message.edit_text(
        f"📝 <b>إذاعة إلى: {type_names.get(broadcast_type, 'غير معروف')}</b>\n\n"
        "أرسل الرسالة التي تريد إذاعتها:\n\n"
        "💡 يمكنك إرسال:\n"
        "• نص\n"
        "• صورة مع نص\n"
        "• فيديو مع نص\n"
        "• ملف مع نص\n\n"
        "📝 أرسل الرسالة الآن، أو اضغط إلغاء للخروج:",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "broadcast_cancel_input")
async def cancel_broadcast_input(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>تم إلغاء الإذاعة</b>",
        parse_mode='HTML'
    )
    await callback.answer("تم الإلغاء")

@router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    from broadcast_manager import broadcast_manager
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # التحقق من أمر الإلغاء
    if message.text and message.text.startswith('/'):
        if message.text in ['/cancel', '/start']:
            await state.clear()
            await message.answer("❌ تم إلغاء الإذاعة")
            return
    
    data = await state.get_data()
    broadcast_type = data.get('broadcast_type')
    
    if not broadcast_type:
        await state.clear()
        await message.answer("❌ خطأ: لم يتم تحديد نوع الإذاعة")
        return
    
    # حساب عدد المستلمين
    recipient_count = 0
    
    if broadcast_type == 'users':
        users = await broadcast_manager.get_all_users()
        recipient_count = len(users)
        target_text = f"{recipient_count} مستخدم"
        
    elif broadcast_type == 'all_targets':
        # دمج قنوات المستخدمين مع أهداف المشرف
        user_channels = await broadcast_manager.get_all_target_channels()
        admin_targets = await broadcast_manager.get_all_admin_targets()
        all_targets = user_channels.union(admin_targets)
        recipient_count = len(all_targets)
        target_text = f"{recipient_count} هدف (قنوات + مجموعات)"
        
    elif broadcast_type == 'channels_only':
        user_channels = await broadcast_manager.get_all_target_channels()
        admin_targets = await broadcast_manager.get_all_admin_targets()
        all_targets = user_channels.union(admin_targets)
        # تصفية القنوات فقط
        channels = await broadcast_manager.filter_channels_by_type(
            message.bot, list(all_targets), 'channel'
        )
        recipient_count = len(channels)
        target_text = f"{recipient_count} قناة"
        
    elif broadcast_type == 'groups_only':
        user_channels = await broadcast_manager.get_all_target_channels()
        admin_targets = await broadcast_manager.get_all_admin_targets()
        all_targets = user_channels.union(admin_targets)
        # تصفية المجموعات فقط
        groups = await broadcast_manager.filter_channels_by_type(
            message.bot, list(all_targets), 'group'
        )
        recipient_count = len(groups)
        target_text = f"{recipient_count} مجموعة"
        
    elif broadcast_type == 'everyone':
        users = await broadcast_manager.get_all_users()
        user_channels = await broadcast_manager.get_all_target_channels()
        admin_targets = await broadcast_manager.get_all_admin_targets()
        all_targets = user_channels.union(admin_targets)
        recipient_count = len(users) + len(all_targets)
        target_text = f"{len(users)} مستخدم + {len(all_targets)} هدف"
    
    else:
        await message.answer("❌ نوع إذاعة غير صحيح")
        await state.clear()
        return
    
    # حفظ الرسالة
    await state.update_data(
        message_id=message.message_id,
        chat_id=message.chat.id,
        recipient_count=recipient_count
    )
    
    # طلب التأكيد
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تأكيد الإرسال", callback_data="confirm_broadcast"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_broadcast")
        ]
    ])
    
    await message.answer(
        f"📊 <b>معاينة الإذاعة</b>\n\n"
        f"👥 <b>المستهدفون:</b> {target_text}\n"
        f"📝 <b>الرسالة:</b> تم حفظها\n\n"
        f"⚠️ <b>هل أنت متأكد من الإرسال؟</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from broadcast_manager import broadcast_manager
    
    data = await state.get_data()
    broadcast_type = data.get('broadcast_type')
    message_id = data.get('message_id')
    chat_id = data.get('chat_id')
    
    # إشعار ببدء الإرسال
    progress_msg = await callback.message.edit_text(
        "⏳ <b>جاري الإرسال...</b>\n\n"
        "📊 سيتم تحديث التقدم تلقائياً",
        parse_mode='HTML'
    )
    
    # الحصول على الرسالة الأصلية
    original_message = await callback.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=chat_id,
        message_id=message_id
    )
    
    # دالة لتحديث التقدم
    async def update_progress(current, total, success, failed, extra=0):
        try:
            percentage = int((current / total) * 100) if total > 0 else 0
            await progress_msg.edit_text(
                f"⏳ <b>جاري الإرسال...</b>\n\n"
                f"📊 التقدم: {current}/{total} ({percentage}%)\n"
                f"✅ نجح: {success}\n"
                f"❌ فشل: {failed}\n"
                f"🚫 محظور/بدون صلاحية: {extra}",
                parse_mode='HTML'
            )
        except:
            pass
    
    results = {}
    
    try:
        if broadcast_type == 'users':
            users = await broadcast_manager.get_all_users()
            results = await broadcast_manager.broadcast_to_users(
                callback.bot, original_message, users, update_progress
            )
            
        elif broadcast_type == 'all_targets':
            user_channels = await broadcast_manager.get_all_target_channels()
            admin_targets = await broadcast_manager.get_all_admin_targets()
            all_targets = list(user_channels.union(admin_targets))
            results = await broadcast_manager.broadcast_to_channels(
                callback.bot, original_message, all_targets, update_progress
            )
            
        elif broadcast_type == 'channels_only':
            user_channels = await broadcast_manager.get_all_target_channels()
            admin_targets = await broadcast_manager.get_all_admin_targets()
            all_targets = user_channels.union(admin_targets)
            channels = await broadcast_manager.filter_channels_by_type(
                callback.bot, list(all_targets), 'channel'
            )
            results = await broadcast_manager.broadcast_to_channels(
                callback.bot, original_message, channels, update_progress
            )
            
        elif broadcast_type == 'groups_only':
            user_channels = await broadcast_manager.get_all_target_channels()
            admin_targets = await broadcast_manager.get_all_admin_targets()
            all_targets = user_channels.union(admin_targets)
            groups = await broadcast_manager.filter_channels_by_type(
                callback.bot, list(all_targets), 'group'
            )
            results = await broadcast_manager.broadcast_to_channels(
                callback.bot, original_message, groups, update_progress
            )
            
        elif broadcast_type == 'everyone':
            # إرسال للمستخدمين أولاً
            users = await broadcast_manager.get_all_users()
            user_results = await broadcast_manager.broadcast_to_users(
                callback.bot, original_message, users, update_progress
            )
            
            # ثم للأهداف
            user_channels = await broadcast_manager.get_all_target_channels()
            admin_targets = await broadcast_manager.get_all_admin_targets()
            all_targets = list(user_channels.union(admin_targets))
            channel_results = await broadcast_manager.broadcast_to_channels(
                callback.bot, original_message, all_targets, update_progress
            )
            
            # دمج النتائج
            results = {
                'success': user_results.get('success', 0) + channel_results.get('success', 0),
                'failed': user_results.get('failed', 0) + channel_results.get('failed', 0),
                'blocked': user_results.get('blocked', 0),
                'no_permission': channel_results.get('no_permission', 0),
                'total': user_results.get('total', 0) + channel_results.get('total', 0)
            }
        
        # حذف الرسالة المؤقتة
        await callback.bot.delete_message(ADMIN_ID, original_message.message_id)
        
        # عرض النتائج النهائية
        await progress_msg.edit_text(
            f"✅ <b>اكتملت الإذاعة!</b>\n\n"
            f"📊 <b>الإحصائيات:</b>\n"
            f"✅ نجح: {results.get('success', 0)}\n"
            f"❌ فشل: {results.get('failed', 0)}\n"
            f"🚫 محظور: {results.get('blocked', 0)}\n"
            f"🔒 بدون صلاحية: {results.get('no_permission', 0)}\n"
            f"📊 الإجمالي: {results.get('total', 0)}",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"خطأ في الإذاعة: {e}", exc_info=True)
        await progress_msg.edit_text(
            f"❌ <b>فشلت الإذاعة!</b>\n\n"
            f"الخطأ: {str(e)}",
            parse_mode='HTML'
        )
    
    await state.clear()

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>تم إلغاء الإذاعة</b>",
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(Command("add_forward"))
async def quick_add_forward_tasks(message: Message):
    """إنشاء مهمة/مهام توجيه بشكل سريع"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    # استخراج النص بعد الأمر
    command_text = message.text.strip()
    
    # إزالة الأمر من النص
    if command_text.startswith('/add_forward'):
        tasks_text = command_text[len('/add_forward'):].strip()
    else:
        await message.answer(
            "📝 <b>إنشاء مهام توجيه سريعة</b>\n\n"
            "<b>الصيغة:</b>\n"
            "<code>/add_forward task_name source_id1,source_id2 -> target_id1,target_id2</code>\n\n"
            "<b>لإضافة عدة مهام:</b>\n"
            "<code>/add_forward task1 source1 -> target1\n"
            "task2 source2,source3 -> target2,target3</code>\n\n"
            "<b>مثال:</b>\n"
            "<code>/add_forward أخبار -1001234567890 -> -1009876543210,-1005555555555</code>\n\n"
            "💡 يمكنك إضافة مصادر وأهداف متعددة بفصلها بفاصلة",
            parse_mode='HTML'
        )
        return
    
    if not tasks_text:
        await message.answer(
            "❌ <b>لم يتم إدخال أي بيانات</b>\n\n"
            "استخدم الصيغة:\n"
            "<code>/add_forward task_name source_ids -> target_ids</code>",
            parse_mode='HTML'
        )
        return
    
    from forwarding_manager import ForwardingManager
    import parallel_forwarding_system
    
    fm = ForwardingManager()
    
    # تقسيم المهام (كل سطر مهمة منفصلة)
    task_lines = [line.strip() for line in tasks_text.split('\n') if line.strip()]
    
    created_tasks = []
    failed_tasks = []
    
    for line in task_lines:
        try:
            # تقسيم السطر إلى: اسم المهمة، مصادر -> أهداف
            if '->' not in line:
                failed_tasks.append({
                    'line': line,
                    'error': 'صيغة خاطئة: يجب استخدام -> للفصل بين المصادر والأهداف'
                })
                continue
            
            # فصل المصادر والأهداف
            parts = line.split('->')
            if len(parts) != 2:
                failed_tasks.append({
                    'line': line,
                    'error': 'صيغة خاطئة: يجب وجود -> واحدة فقط'
                })
                continue
            
            # الجزء الأول: اسم المهمة والمصادر
            left_part = parts[0].strip()
            # الجزء الثاني: الأهداف
            targets_part = parts[1].strip()
            
            # استخراج اسم المهمة والمصادر
            left_tokens = left_part.split()
            if len(left_tokens) < 2:
                failed_tasks.append({
                    'line': line,
                    'error': 'صيغة خاطئة: يجب إدخال اسم المهمة ومعرف مصدر واحد على الأقل'
                })
                continue
            
            task_name = left_tokens[0]
            sources_text = ' '.join(left_tokens[1:])
            
            # تحويل المصادر إلى قائمة
            source_ids = []
            for s in sources_text.split(','):
                s = s.strip()
                if s:
                    try:
                        source_id = int(s)
                        source_ids.append(source_id)
                    except ValueError:
                        failed_tasks.append({
                            'line': line,
                            'error': f'معرف مصدر غير صحيح: {s}'
                        })
                        break
            
            if not source_ids:
                failed_tasks.append({
                    'line': line,
                    'error': 'لم يتم تحديد مصادر صحيحة'
                })
                continue
            
            # تحويل الأهداف إلى قائمة
            target_ids = []
            for t in targets_part.split(','):
                t = t.strip()
                if t:
                    try:
                        target_id = int(t)
                        target_ids.append(target_id)
                    except ValueError:
                        failed_tasks.append({
                            'line': line,
                            'error': f'معرف هدف غير صحيح: {t}'
                        })
                        break
            
            if not target_ids:
                failed_tasks.append({
                    'line': line,
                    'error': 'لم يتم تحديد أهداف صحيحة'
                })
                continue
            
            # جلب معلومات القنوات من تيليجرام
            source_channels = []
            for source_id in source_ids:
                try:
                    chat = await message.bot.get_chat(source_id)
                    source_channels.append({
                        'id': source_id,
                        'title': chat.title or 'Unknown',
                        'username': chat.username
                    })
                except Exception as e:
                    logger.error(f"خطأ في جلب معلومات المصدر {source_id}: {e}")
                    failed_tasks.append({
                        'line': line,
                        'error': f'فشل جلب معلومات المصدر {source_id}: {str(e)}'
                    })
                    break
            
            if len(source_channels) != len(source_ids):
                continue
            
            target_channels = []
            for target_id in target_ids:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_channels.append({
                        'id': target_id,
                        'title': chat.title or 'Unknown',
                        'username': chat.username
                    })
                except Exception as e:
                    logger.error(f"خطأ في جلب معلومات الهدف {target_id}: {e}")
                    failed_tasks.append({
                        'line': line,
                        'error': f'فشل جلب معلومات الهدف {target_id}: {str(e)}'
                    })
                    break
            
            if len(target_channels) != len(target_ids):
                continue
            
            # إنشاء المهمة
            task_id = fm.add_task(task_name, source_channels, target_channels)
            
            created_tasks.append({
                'id': task_id,
                'name': task_name,
                'sources': len(source_channels),
                'targets': len(target_channels)
            })
            
            logger.info(f"✅ تم إنشاء مهمة توجيه #{task_id}: {task_name}")
            
        except Exception as e:
            logger.error(f"خطأ في معالجة السطر '{line}': {e}", exc_info=True)
            failed_tasks.append({
                'line': line,
                'error': str(e)
            })
    
    # إعادة تحميل النظام المتوازي
    if created_tasks and parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()
        logger.info("🔄 تم إعادة تحميل النظام المتوازي بعد إضافة المهام")
    
    # إنشاء تقرير النتائج
    report = "📊 <b>نتائج إنشاء المهام</b>\n\n"
    
    if created_tasks:
        report += f"✅ <b>تم إنشاء {len(created_tasks)} مهمة:</b>\n\n"
        for task in created_tasks:
            report += f"🆔 #{task['id']} - {task['name']}\n"
            report += f"   📥 المصادر: {task['sources']}\n"
            report += f"   📤 الأهداف: {task['targets']}\n\n"
    
    if failed_tasks:
        report += f"\n❌ <b>فشل {len(failed_tasks)} مهمة:</b>\n\n"
        for i, failed in enumerate(failed_tasks, 1):
            report += f"{i}. <code>{failed['line'][:50]}...</code>\n"
            report += f"   السبب: {failed['error']}\n\n"
    
    if not created_tasks and not failed_tasks:
        report = "❌ لم يتم إنشاء أي مهام"
    
    await message.answer(report, parse_mode='HTML')

@router.message(Command("min_subscribers"))
async def min_subscribers_settings(message: Message):
    """إعدادات الحد الأدنى لعدد المشتركين"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ ليس لديك صلاحية لهذا الأمر")
        return
    
    from admin_settings_manager import admin_settings
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    min_subs = admin_settings.get_min_subscribers()
    is_enabled = admin_settings.is_enforcement_enabled()
    
    status_text = "✅ مفعّل" if is_enabled else "❌ معطّل"
    limit_text = f"{min_subs:,}" if min_subs > 0 else "بدون حد"
    
    text = f"""⚙️ <b>إعدادات الحد الأدنى لعدد المشتركين</b>

📊 <b>الحالة الحالية:</b>
• الحد الأدنى: {limit_text}
• الحالة: {status_text}

📝 <b>الوصف:</b>
يتم فحص عدد المشتركين في القنوات/المجموعات عند إضافتها كأهداف. القنوات التي تحتوي على عدد مشتركين أقل من الحد المحدد سيتم رفضها.

💡 <b>ملاحظة:</b> القيمة 0 تعني عدم وجود حد أدنى
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📝 تعديل الحد الأدنى",
            callback_data="min_subs_edit"
        )],
        [InlineKeyboardButton(
            text=f"{'❌ تعطيل' if is_enabled else '✅ تفعيل'} الفحص",
            callback_data="min_subs_toggle"
        )],
        [InlineKeyboardButton(
            text="🔄 تحديث",
            callback_data="min_subs_refresh"
        )]
    ])
    
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

@router.callback_query(F.data == "min_subs_refresh")
async def refresh_min_subs_settings(callback: CallbackQuery):
    """تحديث صفحة الإعدادات"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from admin_settings_manager import admin_settings
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    min_subs = admin_settings.get_min_subscribers()
    is_enabled = admin_settings.is_enforcement_enabled()
    
    status_text = "✅ مفعّل" if is_enabled else "❌ معطّل"
    limit_text = f"{min_subs:,}" if min_subs > 0 else "بدون حد"
    
    text = f"""⚙️ <b>إعدادات الحد الأدنى لعدد المشتركين</b>

📊 <b>الحالة الحالية:</b>
• الحد الأدنى: {limit_text}
• الحالة: {status_text}

📝 <b>الوصف:</b>
يتم فحص عدد المشتركين في القنوات/المجموعات عند إضافتها كأهداف. القنوات التي تحتوي على عدد مشتركين أقل من الحد المحدد سيتم رفضها.

💡 <b>ملاحظة:</b> القيمة 0 تعني عدم وجود حد أدنى
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📝 تعديل الحد الأدنى",
            callback_data="min_subs_edit"
        )],
        [InlineKeyboardButton(
            text=f"{'❌ تعطيل' if is_enabled else '✅ تفعيل'} الفحص",
            callback_data="min_subs_toggle"
        )],
        [InlineKeyboardButton(
            text="🔄 تحديث",
            callback_data="min_subs_refresh"
        )]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer("تم التحديث")

@router.callback_query(F.data == "min_subs_toggle")
async def toggle_min_subs_enforcement(callback: CallbackQuery):
    """تفعيل/تعطيل فرض الحد الأدنى"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from admin_settings_manager import admin_settings
    
    current_status = admin_settings.is_enforcement_enabled()
    admin_settings.set_enforcement(not current_status)
    
    action_text = "تعطيل" if current_status else "تفعيل"
    await callback.answer(f"✅ تم {action_text} فحص الحد الأدنى", show_alert=True)
    
    await refresh_min_subs_settings(callback)

@router.callback_query(F.data == "min_subs_edit")
async def start_edit_min_subs(callback: CallbackQuery, state: FSMContext):
    """بدء تعديل الحد الأدنى"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    from admin_settings_manager import admin_settings
    
    current_min = admin_settings.get_min_subscribers()
    
    await state.set_state(AdminStates.waiting_for_min_subscribers)
    await callback.message.edit_text(
        f"📝 <b>تعديل الحد الأدنى لعدد المشتركين</b>\n\n"
        f"القيمة الحالية: {current_min:,}\n\n"
        f"أرسل العدد الجديد (0 لإلغاء الحد):\n\n"
        f"أمثلة:\n"
        f"• 100 - قنوات بحد أدنى 100 مشترك\n"
        f"• 1000 - قنوات بحد أدنى 1000 مشترك\n"
        f"• 0 - بدون حد أدنى\n\n"
        f"أرسل /cancel للإلغاء",
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_min_subscribers)
async def process_min_subscribers(message: Message, state: FSMContext):
    """معالجة الحد الأدنى الجديد"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ تم الإلغاء")
        return
    
    try:
        min_count = int(message.text.strip())
        
        if min_count < 0:
            await message.answer("❌ الرقم يجب أن يكون 0 أو أكبر")
            return
        
        from admin_settings_manager import admin_settings
        admin_settings.set_min_subscribers(min_count)
        
        await state.clear()
        
        limit_text = f"{min_count:,}" if min_count > 0 else "بدون حد"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="↩️ رجوع للإعدادات",
                callback_data="min_subs_refresh"
            )]
        ])
        
        await message.answer(
            f"✅ <b>تم تحديث الحد الأدنى بنجاح!</b>\n\n"
            f"📊 القيمة الجديدة: {limit_text}\n\n"
            f"سيتم تطبيق هذا الحد على جميع القنوات/المجموعات الجديدة.",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح")
