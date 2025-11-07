
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from forwarding_manager import ForwardingManager
from custom_source_requests import custom_source_manager
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

class CustomSourceStates(StatesGroup):
    waiting_for_source_link = State()

@router.callback_query(F.data == "available_sources")
async def show_available_sources(callback: CallbackQuery):
    """عرض المصادر المتاحة"""
    user_id = callback.from_user.id
    
    # الحصول على مهام المشرف النشطة
    fm = ForwardingManager()
    admin_tasks = fm.get_active_tasks()
    
    text = "📰 <b>المصادر المتاحة</b>\n\n"
    
    if not admin_tasks:
        text += "❌ لا توجد مصادر متاحة حالياً\n\n"
    else:
        text += f"لديك <b>{len(admin_tasks)}</b> مصدر متاح:\n\n"
    
    keyboard_buttons = []
    
    # عرض مهام المشرف كمصادر
    for task_id, task in admin_tasks.items():
        source_info = ""
        if task.source_channels:
            source_titles = ", ".join([ch.get('title', 'قناة')[:15] for ch in task.source_channels[:2]])
            if len(task.source_channels) > 2:
                source_titles += f" +{len(task.source_channels) - 2}"
            source_info = f" ({source_titles})"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📢 {task.name}{source_info}",
                callback_data=f"view_source_{task_id}"
            )
        ])
    
    # زر إضافة مصدر خاص
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="➕ طلب إضافة مصدر خاص",
            callback_data="request_custom_source"
        )
    ])
    
    # زر عرض طلباتي
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="📋 طلباتي",
            callback_data="my_source_requests"
        )
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("view_source_"))
async def view_source_details(callback: CallbackQuery):
    """عرض تفاصيل مصدر معين"""
    task_id = int(callback.data.split("_")[2])
    
    fm = ForwardingManager()
    task = fm.get_task(task_id)
    
    if not task:
        await callback.answer("❌ المصدر غير موجود", show_alert=True)
        return
    
    text = f"📰 <b>{task.name}</b>\n\n"
    
    if task.source_channels:
        text += "📥 <b>القنوات المصدر:</b>\n"
        for ch in task.source_channels:
            text += f"  • {ch.get('title', 'قناة')}\n"
    
    text += f"\n📊 عدد المشتركين: {len(task.target_channels)}\n"
    text += f"✅ الحالة: {'نشط' if task.is_active else 'معطل'}\n\n"
    text += "💡 يمكنك إضافة هذا المصدر إلى قناتك من خلال \"إضافة مهمة إخبارية\""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ إضافة إلى قناتي",
            callback_data=f"user_select_admin_task_{task_id}"
        )],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="available_sources")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "request_custom_source")
async def request_custom_source(callback: CallbackQuery, state: FSMContext):
    """طلب إضافة مصدر خاص"""
    await state.set_state(CustomSourceStates.waiting_for_source_link)
    
    text = """➕ <b>طلب إضافة مصدر خاص</b>

📝 يرجى إدخال رابط مصدرك الخاص:

يمكنك إرسال:
• رابط قناة عامة: <code>https://t.me/channel_name</code>
• معرف القناة: <code>@channel_name</code>
• معرف القناة الرقمي: <code>-1001234567890</code>

💡 سيتم مراجعة طلبك من قبل الإدارة

أرسل /cancel للإلغاء"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_custom_source")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "cancel_custom_source")
async def cancel_custom_source(callback: CallbackQuery, state: FSMContext):
    """إلغاء طلب المصدر"""
    await state.clear()
    await show_available_sources(callback)

@router.message(CustomSourceStates.waiting_for_source_link)
async def process_custom_source_link(message: Message, state: FSMContext):
    """معالجة رابط المصدر الخاص"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ تم إلغاء طلب المصدر")
        return
    
    source_link = message.text.strip()
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # حفظ رابط المصدر في الحالة
    await state.update_data(source_link=source_link)
    
    # عرض معاينة وزر إرسال الطلب
    text = f"""📝 <b>معاينة طلب المصدر</b>

👤 المستخدم: {user_name}
🔗 رابط المصدر: <code>{source_link}</code>

⚠️ تأكد من صحة الرابط قبل الإرسال

هل تريد إرسال هذا الطلب إلى الإدارة؟"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ إرسال الطلب",
            callback_data="send_custom_source_request"
        )],
        [InlineKeyboardButton(
            text="❌ إلغاء",
            callback_data="cancel_custom_source_final"
        )]
    ])
    
    await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

@router.callback_query(F.data == "send_custom_source_request")
async def send_custom_source_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """إرسال طلب المصدر إلى الإدارة"""
    data = await state.get_data()
    source_link = data.get('source_link')
    
    if not source_link:
        await callback.answer("❌ خطأ: لم يتم العثور على رابط المصدر", show_alert=True)
        await state.clear()
        return
    
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    # إنشاء الطلب
    request_id = custom_source_manager.create_request(user_id, user_name, source_link)
    
    await state.clear()
    
    # إرسال إشعار للمستخدم
    await callback.message.edit_text(
        "✅ <b>تم إرسال طلبك بنجاح!</b>\n\n"
        f"📋 رقم الطلب: <code>{request_id}</code>\n\n"
        "⏳ سيتم مراجعة طلبك من قبل الإدارة قريباً\n"
        "يمكنك متابعة حالة طلبك من \"طلباتي\"",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 طلباتي", callback_data="my_source_requests")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="available_sources")]
        ])
    )
    await callback.answer("تم إرسال الطلب")
    
    # إرسال إشعار للمشرف
    if ADMIN_ID and ADMIN_ID != 0:
        try:
            admin_text = f"""🔔 <b>طلب مصدر خاص جديد</b>

👤 من المستخدم: {user_name}
🆔 معرف المستخدم: <code>{user_id}</code>
🔗 رابط المصدر: <code>{source_link}</code>
📋 رقم الطلب: <code>{request_id}</code>

⏰ الوقت: {data.get('created_at', 'الآن')}"""
            
            admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ قبول", callback_data=f"approve_source_{request_id}"),
                    InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_source_{request_id}")
                ],
                [InlineKeyboardButton(text="📋 جميع الطلبات", callback_data="admin_view_source_requests")]
            ])
            
            await bot.send_message(
                ADMIN_ID,
                admin_text,
                parse_mode='HTML',
                reply_markup=admin_keyboard
            )
            logger.info(f"✅ تم إرسال إشعار طلب المصدر للمشرف")
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال إشعار للمشرف: {e}")

@router.callback_query(F.data == "cancel_custom_source_final")
async def cancel_custom_source_final(callback: CallbackQuery, state: FSMContext):
    """إلغاء الطلب والعودة"""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="available_sources")]
    ])
    
    await callback.message.edit_text(
        "❌ تم إلغاء الطلب",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "my_source_requests")
async def show_my_source_requests(callback: CallbackQuery):
    """عرض طلبات المستخدم"""
    user_id = callback.from_user.id
    
    requests = custom_source_manager.get_user_requests(user_id)
    
    text = "📋 <b>طلباتي</b>\n\n"
    
    if not requests:
        text += "❌ ليس لديك أي طلبات حالياً\n\n"
        text += "💡 يمكنك طلب إضافة مصدر خاص من \"المصادر المتاحة\""
    else:
        text += f"لديك <b>{len(requests)}</b> طلب:\n\n"
        
        status_emoji = {
            'pending': '⏳',
            'approved': '✅',
            'rejected': '❌'
        }
        
        status_text = {
            'pending': 'قيد المراجعة',
            'approved': 'مقبول',
            'rejected': 'مرفوض'
        }
        
        for req in requests:
            emoji = status_emoji.get(req['status'], '❓')
            status = status_text.get(req['status'], 'غير معروف')
            
            text += f"{emoji} <b>الطلب #{req['id'][-8:]}</b>\n"
            text += f"   🔗 الرابط: <code>{req['source_link']}</code>\n"
            text += f"   📊 الحالة: {status}\n"
            text += f"   📅 التاريخ: {req['created_at'][:10]}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="available_sources")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

# Handlers للمشرف
@router.callback_query(F.data == "admin_view_source_requests")
async def admin_view_source_requests(callback: CallbackQuery):
    """عرض جميع طلبات المصادر للمشرف"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    pending_requests = custom_source_manager.get_pending_requests()
    
    text = "📋 <b>طلبات المصادر المعلقة</b>\n\n"
    
    if not pending_requests:
        text += "✅ لا توجد طلبات معلقة حالياً"
    else:
        text += f"عدد الطلبات المعلقة: <b>{len(pending_requests)}</b>\n\n"
        
        for req in pending_requests[:10]:  # عرض أول 10 طلبات
            text += f"👤 <b>{req['user_name']}</b> (ID: <code>{req['user_id']}</code>)\n"
            text += f"   🔗 <code>{req['source_link']}</code>\n"
            text += f"   📅 {req['created_at'][:10]}\n"
            text += f"   📋 الطلب: <code>{req['id']}</code>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("approve_source_"))
async def approve_source_request(callback: CallbackQuery, bot: Bot):
    """قبول طلب المصدر"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    request_id = callback.data.replace("approve_source_", "")
    request = custom_source_manager.get_request(request_id)
    
    if not request:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    
    # تحديث حالة الطلب
    custom_source_manager.update_request_status(request_id, 'approved')
    
    # إشعار المستخدم
    try:
        await bot.send_message(
            request['user_id'],
            f"✅ <b>تم قبول طلبك!</b>\n\n"
            f"📋 رقم الطلب: <code>{request_id}</code>\n"
            f"🔗 المصدر: <code>{request['source_link']}</code>\n\n"
            f"سيتم إضافة المصدر قريباً",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار للمستخدم: {e}")
    
    await callback.message.edit_text(
        f"✅ <b>تم قبول الطلب</b>\n\n"
        f"المستخدم: {request['user_name']}\n"
        f"المصدر: <code>{request['source_link']}</code>",
        parse_mode='HTML'
    )
    await callback.answer("تم قبول الطلب")

@router.callback_query(F.data.startswith("reject_source_"))
async def reject_source_request(callback: CallbackQuery, bot: Bot):
    """رفض طلب المصدر"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ ليس لديك صلاحية", show_alert=True)
        return
    
    request_id = callback.data.replace("reject_source_", "")
    request = custom_source_manager.get_request(request_id)
    
    if not request:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    
    # تحديث حالة الطلب
    custom_source_manager.update_request_status(request_id, 'rejected')
    
    # إشعار المستخدم
    try:
        await bot.send_message(
            request['user_id'],
            f"❌ <b>تم رفض طلبك</b>\n\n"
            f"📋 رقم الطلب: <code>{request_id}</code>\n"
            f"🔗 المصدر: <code>{request['source_link']}</code>\n\n"
            f"💡 يمكنك تقديم طلب آخر",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار للمستخدم: {e}")
    
    await callback.message.edit_text(
        f"❌ <b>تم رفض الطلب</b>\n\n"
        f"المستخدم: {request['user_name']}\n"
        f"المصدر: <code>{request['source_link']}</code>",
        parse_mode='HTML'
    )
    await callback.answer("تم رفض الطلب")
