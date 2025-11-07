from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from forwarding_manager import ForwardingManager
from typing import List, Dict
import parallel_forwarding_system
import logging
import os
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

router = Router()
manager = ForwardingManager()

class ForwardingStates(StatesGroup):
    waiting_for_task_name = State()
    waiting_for_source_channels = State()
    waiting_for_target_channels = State()
    adding_source_to_task = State()

async def check_bot_admin(bot: Bot, channel_id: int) -> bool:
    """التحقق من أن البوت مشرف في القناة"""
    try:
        member = await bot.get_chat_member(channel_id, bot.id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

async def get_channel_info(bot: Bot, channel_id: int) -> Dict:
    """الحصول على معلومات القناة"""
    try:
        chat = await bot.get_chat(channel_id)
        return {
            "id": channel_id,
            "title": chat.title,
            "username": chat.username
        }
    except Exception:
        return None

@router.message(Command("forwarding"))
async def forwarding_menu(message: Message):
    from user_handlers import delete_last_panel_and_save_new
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة مهمة جديدة", callback_data="fwd_add")],
        [InlineKeyboardButton(text="📋 عرض جميع المهام", callback_data="fwd_list")],
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="fwd_stats")],
        [InlineKeyboardButton(text="🔙 رجوع للرئيسية", callback_data="back_to_start")]
    ])

    sent_message = await message.answer(
        "📤 <b>إدارة مهام التوجيه المتوازي</b>\n\n"
        "النظام يعمل بالتوازي الكامل:\n"
        "✅ Queue عامة لجميع الرسائل\n"
        "✅ Workers متعددة لكل مهمة\n"
        "✅ توزيع متوازي للأهداف\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=keyboard
    )
    await delete_last_panel_and_save_new(message.bot, message.from_user.id, sent_message.message_id)

@router.callback_query(F.data == "fwd_stats")
async def show_stats(callback: CallbackQuery):
    """عرض إحصائيات النظام المتوازي"""
    if not parallel_forwarding_system.parallel_system:
        await callback.answer("❌ النظام المتوازي غير مفعّل!", show_alert=True)
        return

    stats = parallel_forwarding_system.parallel_system.get_stats()

    text = "📊 <b>إحصائيات النظام المتوازي</b>\n\n"
    text += f"📥 حجم القائمة العامة: {stats['global_queue_size']}\n"
    text += f"🔄 عدد Global Workers: {stats['num_global_workers']}\n"
    text += f"✅ عدد المهام النشطة: {stats['num_active_tasks']}\n\n"

    if stats['tasks']:
        text += "📋 <b>تفاصيل المهام:</b>\n"
        for task_id, task_stats in stats['tasks'].items():
            text += f"\nالمهمة #{task_id}:\n"
            text += f"  📥 قائمة الانتظار: {task_stats['queue_size']}\n"
            text += f"  👷 عدد Workers: {task_stats['num_workers']}\n"

    keyboard = [[InlineKeyboardButton(text="refresh", callback_data="fwd_stats")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_fwd_menu")]]

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@router.callback_query(F.data == "fwd_add")
async def start_add_task(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 <b>إضافة مهمة توجيه جديدة</b>\n\n"
        "أدخل اسم المهمة:"
    )
    await state.set_state(ForwardingStates.waiting_for_task_name)
    await callback.answer()

@router.message(ForwardingStates.waiting_for_task_name)
async def process_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    await message.answer(
        "📥 <b>إضافة قنوات المصدر</b>\n\n"
        "أرسل معرفات قنوات المصدر (يمكنك إرسال عدة قنوات).\n"
        "يمكنك:\n"
        "• إرسال معرف القناة الرقمي (مثل: -1001234567890)\n"
        "• إعادة توجيه رسالة من القناة\n\n"
        "أرسل /done عند الانتهاء من إضافة جميع قنوات المصدر."
    )
    await state.update_data(source_channels=[])
    await state.set_state(ForwardingStates.waiting_for_source_channels)

@router.message(ForwardingStates.waiting_for_source_channels)
async def process_source_channels(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/done":
        data = await state.get_data()
        source_channels = data.get('source_channels', [])

        if not source_channels:
            await message.answer("❌ يجب إضافة قناة مصدر واحدة على الأقل!")
            return

        await message.answer(
            "📤 <b>إضافة قنوات الهدف</b>\n\n"
            "أرسل معرفات قنوات الهدف (يمكنك إرسال عدة قنوات).\n"
            "يمكنك:\n"
            "• إرسال معرف القناة الرقمي (مثل: -1001234567890)\n"
            "• إعادة توجيه رسالة من القناة\n\n"
            "أرسل /done عند الانتهاء من إضافة جميع قنوات الهدف."
        )
        await state.update_data(target_channels=[])
        await state.set_state(ForwardingStates.waiting_for_target_channels)
        return

    channel_id = None

    if message.forward_from_chat:
        if message.forward_from_chat.type in ['channel', 'supergroup']:
            channel_id = message.forward_from_chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        channel_id = int(message.text)

        if not str(channel_id).startswith('-100'):
            await message.answer(
                "❌ معرف القناة يجب أن يبدأ بـ -100\n"
                "مثال: -1001234567890"
            )
            return
    else:
        await message.answer("❌ الرجاء إرسال معرف قناة صحيح أو إعادة توجيه رسالة من القناة.")
        return

    if not await check_bot_admin(bot, channel_id):
        await message.answer(
            f"❌ البوت ليس مشرفاً في القناة!\n"
            f"معرف القناة: <code>{channel_id}</code>\n\n"
            "يرجى إضافة البوت كمشرف في القناة أولاً."
        )
        return

    channel_info = await get_channel_info(bot, channel_id)
    if not channel_info:
        await message.answer("❌ فشل الحصول على معلومات القناة!")
        return

    data = await state.get_data()
    source_channels = data.get('source_channels', [])

    if any(ch['id'] == channel_id for ch in source_channels):
        await message.answer("⚠️ هذه القناة مضافة بالفعل!")
        return

    source_channels.append(channel_info)
    await state.update_data(source_channels=source_channels)

    await message.answer(
        f"✅ تمت إضافة قناة المصدر:\n"
        f"📢 {channel_info['title']}\n"
        f"🆔 <code>{channel_info['id']}</code>\n\n"
        f"📊 عدد قنوات المصدر: {len(source_channels)}\n\n"
        f"أرسل /done للانتقال إلى قنوات الهدف."
    )

@router.message(ForwardingStates.waiting_for_target_channels)
async def process_target_channels(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/done":
        data = await state.get_data()
        target_channels = data.get('target_channels', [])

        if not target_channels:
            await message.answer("❌ يجب إضافة قناة هدف واحدة على الأقل!")
            return

        task_name = data['task_name']
        source_channels = data['source_channels']

        task_id = manager.add_task(task_name, source_channels, target_channels)

        # إعادة تحميل المهام في النظام المتوازي
        if parallel_forwarding_system.parallel_system:
            await parallel_forwarding_system.parallel_system.reload_tasks()

        summary = f"✅ <b>تم إنشاء المهمة بنجاح!</b>\n\n"
        summary += f"🔢 رقم المهمة: {task_id}\n"
        summary += f"📝 الاسم: {task_name}\n\n"
        summary += f"📥 قنوات المصدر ({len(source_channels)}):\n"
        for ch in source_channels:
            summary += f"  • {ch['title']}\n"
        summary += f"\n📤 قنوات الهدف ({len(target_channels)}):\n"
        for ch in target_channels:
            summary += f"  • {ch['title']}\n"
        summary += f"\n✅ الحالة: مفعّلة ومتصلة بالنظام المتوازي"

        await message.answer(summary)
        await state.clear()
        return

    channel_id = None

    if message.forward_from_chat:
        if message.forward_from_chat.type in ['channel', 'supergroup']:
            channel_id = message.forward_from_chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        channel_id = int(message.text)

        if not str(channel_id).startswith('-100'):
            await message.answer(
                "❌ معرف القناة يجب أن يبدأ بـ -100\n"
                "مثال: -1001234567890"
            )
            return
    else:
        await message.answer("❌ الرجاء إرسال معرف قناة صحيح أو إعادة توجيه رسالة من القناة.")
        return

    if not await check_bot_admin(bot, channel_id):
        await message.answer(
            f"❌ البوت ليس مشرفاً في القناة!\n"
            f"معرف القناة: <code>{channel_id}</code>\n\n"
            "يرجى إضافة البوت كمشرف في القناة أولاً."
        )
        return

    channel_info = await get_channel_info(bot, channel_id)
    if not channel_info:
        await message.answer("❌ فشل الحصول على معلومات القناة!")
        return

    data = await state.get_data()
    target_channels = data.get('target_channels', [])

    if any(ch['id'] == channel_id for ch in target_channels):
        await message.answer("⚠️ هذه القناة مضافة بالفعل!")
        return

    target_channels.append(channel_info)
    await state.update_data(target_channels=target_channels)

    await message.answer(
        f"✅ تمت إضافة قناة الهدف:\n"
        f"📢 {channel_info['title']}\n"
        f"🆔 <code>{channel_info['id']}</code>\n\n"
        f"📊 عدد قنوات الهدف: {len(target_channels)}\n\n"
        f"أرسل /done لحفظ المهمة."
    )

@router.callback_query(F.data == "fwd_list")
async def list_tasks(callback: CallbackQuery):
    tasks = manager.get_all_tasks()

    if not tasks:
        await callback.message.edit_text(
            "📭 لا توجد مهام توجيه حالياً.\n\n"
            "استخدم /forwarding لإضافة مهمة جديدة."
        )
        await callback.answer()
        return

    keyboard = []
    for task_id, task in tasks.items():
        status = "✅" if task.is_active else "⏸"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {task.name} (#{task_id})",
                callback_data=f"fwd_view_{task_id}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_fwd_menu")])

    await callback.message.edit_text(
        f"📋 <b>مهام التوجيه ({len(tasks)})</b>\n\n"
        "اضغط على مهمة لعرض التفاصيل:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

def format_subscriber_count(count: int) -> str:
    """تنسيق عدد المشتركين"""
    if count >= 1000000:
        return f"{count/1000000:.1f}M"
    elif count >= 100000:
        return f"{int(count/1000)}k"
    elif count >= 1000:
        return f"{count/1000:.1f}k"
    elif count >= 100:
        return f"{int(count/100)}h"
    else:
        return str(count)

async def get_channel_members_count(bot: Bot, channel_id: int) -> int:
    """الحصول على عدد المشتركين في القناة"""
    try:
        count = await bot.get_chat_member_count(channel_id)
        return count if count else 0
    except Exception as e:
        logger.error(f"❌ خطأ في جلب عدد المشتركين للقناة {channel_id}: {e}")
        return 0

@router.callback_query(F.data.startswith("fwd_view_"))
async def view_task(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    task_id = int(parts[2])
    task = manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    text = f"📋 <b>تفاصيل المهمة #{task_id}</b>\n\n"
    text += f"📝 الاسم: {task.name}\n"
    text += f"✅ الحالة: {'مفعّلة' if task.is_active else 'معطّلة'}\n\n"

    text += f"📥 قنوات المصدر ({len(task.source_channels)}):\n"
    for ch in task.source_channels:
        text += f"  • {ch['title']}\n"

    text += f"\n📤 قنوات الهدف: {len(task.target_channels)}\n"

    keyboard = [
        [InlineKeyboardButton(
            text="⏸ تعطيل" if task.is_active else "▶️ تفعيل",
            callback_data=f"fwd_toggle_{task_id}"
        )],
        [
            InlineKeyboardButton(text="📥 تعديل المصدر", callback_data=f"fwd_edit_source_{task_id}"),
            InlineKeyboardButton(text="📤 إدارة الأهداف", callback_data=f"fwd_manage_targets_{task_id}_0")
        ],
        [InlineKeyboardButton(text="🗑 حذف المهمة", callback_data=f"fwd_delete_{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="fwd_list")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@router.callback_query(F.data.startswith("fwd_edit_source_"))
async def edit_source_channels(callback: CallbackQuery, bot: Bot):
    task_id = int(callback.data.split("_")[3])
    task = manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    text = f"📥 <b>قنوات المصدر - المهمة #{task_id}</b>\n\n"

    keyboard = []
    for idx, ch in enumerate(task.source_channels):
        members = await get_channel_members_count(bot, ch['id'])
        formatted_count = format_subscriber_count(members)

        keyboard.append([
            InlineKeyboardButton(
                text="❌ حذف",
                callback_data=f"fwd_remove_source_{task_id}_{idx}"
            ),
            InlineKeyboardButton(
                text=f"{ch['title']} ({formatted_count})",
                callback_data="noop"
            )
        ])

    keyboard.append([InlineKeyboardButton(
        text="➕ إضافة قناة مصدر جديدة",
        callback_data=f"fwd_add_source_{task_id}"
    )])
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"fwd_view_{task_id}")])

    if not task.source_channels:
        text += "⚠️ لا توجد قنوات مصدر حالياً\n"
    else:
        text += f"عدد القنوات: {len(task.source_channels)}\n"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@router.callback_query(F.data.startswith("fwd_manage_targets_"))
async def manage_targets(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    task_id = int(parts[3])
    page = int(parts[4])
    task = manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    # الحصول على عدد المشتركين لكل قناة
    channels_with_counts = []
    for ch in task.target_channels:
        members = await get_channel_members_count(bot, ch['id'])
        channels_with_counts.append({
            'channel': ch,
            'members': members
        })

    # ترتيب تنازلي حسب عدد المشتركين
    channels_with_counts.sort(key=lambda x: x['members'], reverse=True)

    # Pagination - 30 قناة في كل صفحة
    per_page = 30
    total_pages = (len(channels_with_counts) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(channels_with_counts))
    page_channels = channels_with_counts[start_idx:end_idx]

    text = f"📤 <b>إدارة الأهداف - المهمة #{task_id}</b>\n\n"
    text += f"إجمالي القنوات: {len(task.target_channels)}\n"
    text += f"الصفحة: {page + 1} / {max(total_pages, 1)}\n"

    keyboard = []

    # عرض القنوات - زرين في كل صف
    for i in range(0, len(page_channels), 2):
        row = []

        # الزر الأول
        ch_data = page_channels[i]
        ch = ch_data['channel']
        members = ch_data['members']
        formatted_count = format_subscriber_count(members)

        # البحث عن index الحقيقي في القائمة الأصلية
        real_idx = task.target_channels.index(ch)

        row.append(InlineKeyboardButton(
            text=f"{ch['title']} ({formatted_count})",
            callback_data=f"fwd_target_action_{task_id}_{real_idx}_{page}"
        ))

        # الزر الثاني (إن وجد)
        if i + 1 < len(page_channels):
            ch_data2 = page_channels[i + 1]
            ch2 = ch_data2['channel']
            members2 = ch_data2['members']
            formatted_count2 = format_subscriber_count(members2)

            real_idx2 = task.target_channels.index(ch2)

            row.append(InlineKeyboardButton(
                text=f"{ch2['title']} ({formatted_count2})",
                callback_data=f"fwd_target_action_{task_id}_{real_idx2}_{page}"
            ))

        keyboard.append(row)

    # أزرار التنقل
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ السابق",
            callback_data=f"fwd_manage_targets_{task_id}_{page-1}"
        ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ التالي",
            callback_data=f"fwd_manage_targets_{task_id}_{page+1}"
        ))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"fwd_view_{task_id}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await bot.answer_callback_query(callback.id)

@router.callback_query(F.data.startswith("fwd_target_action_"))
async def target_action(callback: CallbackQuery):
    parts = callback.data.split("_")
    task_id = int(parts[3])
    target_idx = int(parts[4])
    page = int(parts[5])

    task = manager.get_task(task_id)
    if not task or target_idx >= len(task.target_channels):
        await callback.answer("❌ القناة غير موجودة!", show_alert=True)
        return

    channel = task.target_channels[target_idx]

    text = f"📤 <b>إدارة القناة الهدف</b>\n\n"
    text += f"📢 {channel['title']}\n"
    text += f"🆔 <code>{channel['id']}</code>\n\n"
    text += "ماذا تريد أن تفعل؟"

    keyboard = [
        [InlineKeyboardButton(
            text="🗑 حذف هذه القناة",
            callback_data=f"fwd_confirm_remove_target_{task_id}_{target_idx}_{page}"
        )],
        [InlineKeyboardButton(
            text="🔙 رجوع للقائمة",
            callback_data=f"fwd_manage_targets_{task_id}_{page}"
        )]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@router.callback_query(F.data.startswith("fwd_confirm_remove_target_"))
async def confirm_remove_target(callback: CallbackQuery):
    parts = callback.data.split("_")
    task_id = int(parts[4])
    target_idx = int(parts[5])
    page = int(parts[6])

    # تحميل جميع المهام وتعديلها مباشرة
    all_tasks = manager.get_all_tasks()
    
    if task_id not in all_tasks:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return
    
    task = all_tasks[task_id]
    
    if target_idx >= len(task.target_channels):
        await callback.answer("❌ القناة غير موجودة!", show_alert=True)
        return

    removed_channel = task.target_channels.pop(target_idx)

    # حذف ملف إعدادات المهمة للمستخدم إذا كان موجوداً
    user_id = removed_channel.get('user_id')
    user_task_id = removed_channel.get('user_task_id')

    if user_id and user_task_id:
        settings_file = os.path.join(USERS_DATA_DIR, str(user_id), f'task_{user_task_id}_settings.json')
        if os.path.exists(settings_file):
            try:
                os.remove(settings_file)
                logger.info(f"🗑️ تم حذف ملف الإعدادات: {settings_file}")
            except Exception as e:
                logger.error(f"❌ خطأ في حذف ملف الإعدادات: {e}")

    # حذف مهمة المستخدم المرتبطة بهذا الهدف
    if user_id and user_task_id:
        from user_task_manager import UserTaskManager
        user_task_manager = UserTaskManager(user_id)

        # حذف مهمة المستخدم
        deleted = user_task_manager.delete_task(user_task_id)

        if deleted:
            logger.info(f"🗑 تم حذف مهمة المستخدم #{user_task_id} للمستخدم {user_id}")

            # إرسال إشعار للمستخدم
            try:
                await callback.bot.send_message(
                    user_id,
                    f"📋 <b>إشعار حذف مهمة</b>\n\n"
                    f"تم حذف قناة هدف من المهمة <b>{task.name}</b> من قبل المشرف.\n\n"
                    f"📢 القناة: <b>{removed_channel['title']}</b>\n"
                    f"🆔 المعرف: <code>{removed_channel['id']}</code>\n\n"
                    f"✅ تم حذف مهمتك المرتبطة بهذه القناة تلقائياً.",
                    parse_mode='HTML'
                )
                logger.info(f"✅ تم إرسال إشعار للمستخدم {user_id}")
            except Exception as e:
                logger.error(f"❌ خطأ في إرسال إشعار للمستخدم {user_id}: {e}")
        else:
            logger.warning(f"⚠️ فشل حذف مهمة المستخدم #{user_task_id}")

    # حفظ التعديلات في قاعدة البيانات
    manager.save_tasks(all_tasks)

    # إعادة تحميل النظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    await callback.answer(f"✅ تم حذف القناة: {removed_channel['title']}", show_alert=True)

    # تحديث الرسالة مباشرة للعودة لقائمة الأهداف
    # الحصول على عدد المشتركين لكل قناة
    channels_with_counts = []
    for ch in task.target_channels:
        members = await get_channel_members_count(callback.bot, ch['id'])
        channels_with_counts.append({
            'channel': ch,
            'members': members
        })

    # ترتيب تنازلي حسب عدد المشتركين
    channels_with_counts.sort(key=lambda x: x['members'], reverse=True)

    # Pagination
    per_page = 30
    total_pages = (len(channels_with_counts) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(channels_with_counts))
    page_channels = channels_with_counts[start_idx:end_idx]

    text = f"📤 <b>إدارة الأهداف - المهمة #{task_id}</b>\n\n"
    text += f"إجمالي القنوات: {len(task.target_channels)}\n"
    text += f"الصفحة: {page + 1} / {max(total_pages, 1)}\n"

    keyboard = []

    # عرض القنوات - زرين في كل صف
    for i in range(0, len(page_channels), 2):
        row = []

        ch_data = page_channels[i]
        ch = ch_data['channel']
        members = ch_data['members']
        formatted_count = format_subscriber_count(members)
        real_idx = task.target_channels.index(ch)

        row.append(InlineKeyboardButton(
            text=f"{ch['title']} ({formatted_count})",
            callback_data=f"fwd_target_action_{task_id}_{real_idx}_{page}"
        ))

        if i + 1 < len(page_channels):
            ch_data2 = page_channels[i + 1]
            ch2 = ch_data2['channel']
            members2 = ch_data2['members']
            formatted_count2 = format_subscriber_count(members2)
            real_idx2 = task.target_channels.index(ch2)

            row.append(InlineKeyboardButton(
                text=f"{ch2['title']} ({formatted_count2})",
                callback_data=f"fwd_target_action_{task_id}_{real_idx2}_{page}"
            ))

        keyboard.append(row)

    # أزرار التنقل
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ السابق",
            callback_data=f"fwd_manage_targets_{task_id}_{page-1}"
        ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ التالي",
            callback_data=f"fwd_manage_targets_{task_id}_{page+1}"
        ))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"fwd_view_{task_id}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await bot.answer_callback_query(callback.id)

@router.callback_query(F.data.startswith("fwd_add_source_"))
async def add_source_channel(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[3])
    task = manager.get_task(task_id)

    if not task:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return

    await state.update_data(edit_task_id=task_id)
    await state.set_state(ForwardingStates.adding_source_to_task)

    await callback.message.edit_text(
        f"📥 <b>إضافة قناة مصدر جديدة</b>\n\n"
        f"أرسل معرف القناة أو قم بإعادة توجيه رسالة من القناة.\n\n"
        f"مثال: <code>-1001234567890</code>\n\n"
        f"أرسل /cancel للإلغاء",
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(ForwardingStates.adding_source_to_task)
async def process_new_source_channel(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        data = await state.get_data()
        task_id = data.get('edit_task_id')
        await state.clear()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"fwd_edit_source_{task_id}")]
        ])
        await message.answer("❌ تم الإلغاء", reply_markup=keyboard)
        return

    channel_id = None

    if message.forward_from_chat:
        if message.forward_from_chat.type in ['channel', 'supergroup']:
            channel_id = message.forward_from_chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        channel_id = int(message.text)

        if not str(channel_id).startswith('-100'):
            await message.answer("❌ معرف القناة يجب أن يبدأ بـ -100")
            return
    else:
        await message.answer("❌ الرجاء إرسال معرف قناة صحيح أو إعادة توجيه رسالة من القناة.")
        return

    if not await check_bot_admin(bot, channel_id):
        await message.answer(
            f"❌ البوت ليس مشرفاً في القناة!\n"
            f"معرف القناة: <code>{channel_id}</code>",
            parse_mode='HTML'
        )
        return

    channel_info = await get_channel_info(bot, channel_id)
    if not channel_info:
        await message.answer("❌ فشل الحصول على معلومات القناة!")
        return

    data = await state.get_data()
    task_id = data.get('edit_task_id')
    
    # تحميل جميع المهام وتعديلها مباشرة
    all_tasks = manager.get_all_tasks()
    
    if task_id not in all_tasks:
        await state.clear()
        await message.answer("❌ المهمة غير موجودة!")
        return

    task = all_tasks[task_id]

    # التحقق من عدم تكرار القناة
    if any(ch['id'] == channel_id for ch in task.source_channels):
        await message.answer("⚠️ هذه القناة مضافة بالفعل كمصدر!")
        return

    # إضافة القناة
    task.source_channels.append(channel_info)

    # حفظ التعديلات
    manager.save_tasks(all_tasks)

    # إعادة تحميل النظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"fwd_edit_source_{task_id}")]
    ])

    await message.answer(
        f"✅ <b>تمت إضافة قناة المصدر بنجاح</b>\n\n"
        f"📢 {channel_info['title']}\n"
        f"🆔 <code>{channel_info['id']}</code>",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("fwd_remove_source_"))
async def remove_source_channel(callback: CallbackQuery):
    parts = callback.data.split("_")
    task_id = int(parts[3])
    source_idx = int(parts[4])

    # تحميل جميع المهام وتعديلها مباشرة
    all_tasks = manager.get_all_tasks()
    
    if task_id not in all_tasks:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
        return
    
    task = all_tasks[task_id]
    
    if source_idx >= len(task.source_channels):
        await callback.answer("❌ القناة غير موجودة!", show_alert=True)
        return

    # حذف القناة
    removed_channel = task.source_channels.pop(source_idx)

    # حفظ التعديلات
    manager.save_tasks(all_tasks)

    # إعادة تحميل النظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    await callback.answer(f"✅ تم حذف القناة: {removed_channel['title']}", show_alert=True)

    # إعادة عرض قائمة المصادر
    await edit_source_channels(callback, callback.bot)

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    """معالج فارغ للأزرار غير التفاعلية"""
    await callback.answer()

@router.callback_query(F.data.startswith("fwd_toggle_"))
async def toggle_task(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    new_status = manager.toggle_task(task_id)

    # إعادة تحميل المهام في النظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    await callback.answer(
        f"✅ تم {'تفعيل' if new_status else 'تعطيل'} المهمة!",
        show_alert=True
    )
    await view_task(callback, callback.bot)

@router.callback_query(F.data.startswith("fwd_delete_"))
async def delete_task(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])

    keyboard = [
        [
            InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"fwd_confirm_delete_{task_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data=f"fwd_view_{task_id}")
        ]
    ]

    await callback.message.edit_text(
        f"⚠️ هل أنت متأكد من حذف المهمة #{task_id}؟\n\n"
        "هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("fwd_confirm_delete_"))
async def confirm_delete_task(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[3])

    # الحصول على المهمة قبل حذفها
    task = manager.get_task(task_id)

    if task:
        # حذف جميع مهام المستخدمين المرتبطة بهذه المهمة
        from user_task_manager import UserTaskManager
        deleted_user_tasks = []

        for target in task.target_channels:
            user_id = target.get('user_id')
            user_task_id = target.get('user_task_id')

            if user_id and user_task_id:
                try:
                    user_manager = UserTaskManager(user_id)
                    if user_manager.delete_task(user_task_id):
                        deleted_user_tasks.append((user_id, user_task_id))
                        logger.info(f"🗑 تم حذف مهمة المستخدم #{user_task_id} للمستخدم {user_id}")
                except Exception as e:
                    logger.error(f"❌ خطأ في حذف مهمة المستخدم {user_id}: {e}")

        logger.info(f"🗑 تم حذف {len(deleted_user_tasks)} مهمة مستخدم مرتبطة بالمهمة #{task_id}")

    # حذف المهمة الإدارية
    manager.delete_task(task_id)

    # إعادة تحميل المهام في النظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.reload_tasks()

    await callback.answer("✅ تم حذف المهمة وجميع مهام المستخدمين المرتبطة بها!", show_alert=True)
    await list_tasks(callback)

@router.callback_query(F.data == "back_to_fwd_menu")
async def back_to_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة مهمة جديدة", callback_data="fwd_add")],
        [InlineKeyboardButton(text="📋 عرض جميع المهام", callback_data="fwd_list")],
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="fwd_stats")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ])

    await callback.message.edit_text(
        "📤 <b>إدارة مهام التوجيه المتوازي</b>\n\n"
        "النظام يعمل بالتوازي الكامل:\n"
        "✅ Queue عامة لجميع الرسائل\n"
        "✅ Workers متعددة لكل مهمة\n"
        "✅ توزيع متوازي للأهداف\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.channel_post()
async def auto_forward_handler(message: Message, bot: Bot):
    """استقبال الرسائل من webhook وإضافتها للقائمة العامة"""
    if not message.chat.id:
        return

    # تم تعطيل معالجة رسائل التفعيل والتعطيل
    # if message.text and message.text.strip().startswith("تفعيل"):
    #     logger.info(f"🔄 معالجة رسالة تفعيل من القناة {message.chat.id}")
    #     from activation_handler import process_activation
    #     await process_activation(message, bot)
    #     return

    # if message.text and message.text.strip().startswith("تعطيل"):
    #     logger.info(f"🔄 معالجة رسالة تعطيل من القناة {message.chat.id}")
    #     from activation_handler import process_deactivation
    #     await process_deactivation(message, bot)
    #     return

    logger.info(f"📨 رسالة واردة من القناة {message.chat.id} ({message.chat.title if message.chat.title else 'Unknown'})")

    # إضافة الرسالة للنظام المتوازي
    if parallel_forwarding_system.parallel_system:
        await parallel_forwarding_system.parallel_system.add_message_from_webhook(message)
        logger.info(f"✅ تم إضافة الرسالة للنظام المتوازي")
    else:
        logger.warning("⚠️ النظام المتوازي غير مفعّل!")

# Dummy function for view_targets as it's used in the removed code
async def view_targets(callback: CallbackQuery, task_id: int):
    """Placeholder for view_targets to resolve NameError if it was actually called"""
    task = manager.get_task(task_id)
    if task:
        # Simulate redirecting to manage_targets page 0
        await manage_targets(callback, callback.bot)
    else:
        await callback.answer("❌ المهمة غير موجودة!", show_alert=True)

# Removed callback query handler for fwd_remove_target as it's replaced by confirm_remove_target
# @router.callback_query(F.data.startswith("fwd_remove_target_"))
# async def remove_target(callback: CallbackQuery):
#     parts = callback.data.split("_")
#     task_id = int(parts[3])
#     target_id = int(parts[4])

#     manager = ForwardingManager()
#     all_tasks = manager.get_all_tasks()
#     task = all_tasks.get(task_id)

#     if not task:
#         await callback.answer("❌ المهمة غير موجودة!", show_alert=True)
#         return

#     # البحث عن الهدف وحذفه
#     target_found = False
#     for i, target in enumerate(task.target_channels):
#         if target['id'] == target_id:
#             task.target_channels.pop(i)
#             target_found = True
#             break

#     if target_found:
#         # حفظ التغييرات
#         manager.save_tasks(all_tasks)

#         # إعادة تحميل النظام المتوازي
#         import parallel_forwarding_system
#         if parallel_forwarding_system.parallel_system:
#             await parallel_forwarding_system.parallel_system.reload_tasks()

#         await callback.answer("✅ تم حذف الهدف بنجاح", show_alert=True)
#     else:
#         await callback.answer("❌ الهدف غير موجود!", show_alert=True)

#     # العودة لعرض الأهداف
#     await view_targets(callback, task_id)