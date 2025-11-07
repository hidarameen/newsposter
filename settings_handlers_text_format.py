from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from text_formatter import TextFormatter
import logging

logger = logging.getLogger(__name__)
router = Router()

class TextFormatStates(StatesGroup):
    waiting_for_link = State()

def get_text_format_keyboard(user_id: int, task_id: int) -> InlineKeyboardMarkup:
    """لوحة مفاتيح إعدادات تنسيق النص"""
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings = settings_manager.load_settings()
    text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
    
    enabled = text_format.get('enabled', False)
    current_format = text_format.get('format_type', 'normal')
    text_link_url = text_format.get('text_link_url', '')
    
    buttons = []
    
    # زر التفعيل/التعطيل
    toggle_text = "✅ مفعّل" if enabled else "❌ معطّل"
    buttons.append([InlineKeyboardButton(
        text=f"الحالة: {toggle_text}",
        callback_data=f"text_format_toggle_{task_id}"
    )])
    
    if enabled:
        buttons.append([InlineKeyboardButton(
            text="اختر نوع التنسيق:",
            callback_data="ignore"
        )])
        
        # أزرار أنواع التنسيقات
        format_buttons = []
        for format_type in TextFormatter.SUPPORTED_FORMATS:
            display_name = TextFormatter.get_format_display_name(format_type)
            
            # إضافة علامة ✓ للتنسيق الحالي
            if format_type == current_format:
                display_name = f"✓ {display_name}"
            
            format_buttons.append(InlineKeyboardButton(
                text=display_name,
                callback_data=f"text_format_set_{task_id}_{format_type}"
            ))
        
        # تقسيم الأزرار إلى صفوف (3 أزرار في كل صف)
        for i in range(0, len(format_buttons), 3):
            buttons.append(format_buttons[i:i+3])
        
        # إذا كان التنسيق المختار هو text_link، أضف زر تخصيص الرابط
        if current_format == 'text_link':
            link_status = f"🔗 {text_link_url[:30]}..." if text_link_url else "🔗 لم يتم تحديد رابط"
            buttons.append([InlineKeyboardButton(
                text=link_status,
                callback_data=f"text_format_customize_link_{task_id}"
            )])
    
    # زر العودة
    buttons.append([InlineKeyboardButton(
        text="🔙 رجوع",
        callback_data=f"task_settings:{task_id}"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def _build_text_format_message(enabled: bool, current_format: str, text_link_url: str = '') -> str:
    """بناء نص رسالة إعدادات تنسيق النص"""
    current_format_name = TextFormatter.get_format_display_name(current_format)
    status_emoji = "✅" if enabled else "❌"
    
    msg = (
        f"🎨 <b>إعدادات تنسيق النص الموحد</b>\n\n"
        f"الحالة: {status_emoji} {'مفعّل' if enabled else 'معطّل'}\n"
        f"التنسيق الحالي: {current_format_name}\n"
    )
    
    if current_format == 'text_link':
        if text_link_url:
            msg += f"الرابط: {text_link_url}\n"
        else:
            msg += f"⚠️ تحذير: لم يتم تحديد رابط!\n"
    
    msg += (
        f"\n<b>📝 الشرح:</b>\n"
        f"هذه الوظيفة تحول جميع تنسيقات النص (العريض، المائل، المخفي، إلخ) "
        f"إلى تنسيق موحد من اختيارك.\n\n"
        f"<b>📌 مثال:</b>\n"
        f"إذا فعّلت \"عريض\"، سيصبح النص كله <b>عريض</b>\n"
        f"إذا فعّلت \"رابط نصي\"، سيصبح النص كله رابطاً قابلاً للنقر\n"
        f"إذا فعّلت \"عادي\"، ستُزال جميع التنسيقات\n\n"
        f"<b>ℹ️ ملاحظات:</b>\n"
        f"• يُطبّق على: النص الأصلي + الهيدر + الفوتر + الاستبدالات\n"
        f"• لا يؤثر على: المنشنات والهاشتاغ\n"
        f"• يُطبّق كآخر خطوة قبل الإرسال"
    )
    
    return msg

@router.callback_query(F.data.startswith("text_format_menu_"))
async def text_format_menu(callback: CallbackQuery):
    """عرض قائمة إعدادات تنسيق النص"""
    try:
        # الرد فوراً لتجنب timeout
        await callback.answer()
        
        task_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id
        
        # التحقق من الاشتراك المدفوع
        from subscription_manager import SubscriptionManager, PREMIUM_FEATURES
        
        sub_manager = SubscriptionManager(user_id)
        if not sub_manager.is_premium():
            feature_info = PREMIUM_FEATURES.get('text_format', {'name': 'تنسيق النص الموحد', 'icon': '🎨', 'description': 'تحويل جميع تنسيقات النص إلى تنسيق موحد من اختيارك'})
            icon = feature_info.get('icon', '🔒')
            name = feature_info.get('name', 'تنسيق النص الموحد')
            description = feature_info.get('description', '')
            
            msg = f"🔒 <b>{name}</b>\n\n"
            if description:
                msg += f"📝 {description}\n\n"
            msg += "💡 هذه ميزة مدفوعة! للاستفادة منها، يرجى ترقية حسابك."
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
            ])
            
            await callback.message.edit_text(msg, parse_mode='HTML', reply_markup=keyboard)
            return
        
        settings_manager = TaskSettingsManager(user_id, task_id)
        settings = settings_manager.load_settings()
        text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
        
        enabled = text_format.get('enabled', False)
        current_format = text_format.get('format_type', 'normal')
        text_link_url = text_format.get('text_link_url', '')
        
        text = _build_text_format_message(enabled, current_format, text_link_url)
        keyboard = get_text_format_keyboard(user_id, task_id)
        
        try:
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                raise
        
    except Exception as e:
        logger.error(f"خطأ في text_format_menu: {e}", exc_info=True)

@router.callback_query(F.data.startswith("text_format_toggle_"))
async def text_format_toggle(callback: CallbackQuery):
    """تفعيل/تعطيل تنسيق النص"""
    try:
        task_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id
        
        settings_manager = TaskSettingsManager(user_id, task_id)
        
        # قراءة الإعدادات الحالية
        settings = settings_manager.load_settings()
        text_format = settings.get('text_format', {})
        
        # التأكد من وجود القيم الأساسية
        if 'enabled' not in text_format:
            text_format['enabled'] = False
        if 'format_type' not in text_format:
            text_format['format_type'] = 'normal'
        
        # عكس الحالة
        new_state = not text_format['enabled']
        text_format['enabled'] = new_state
        
        # حفظ الإعدادات المحدثة
        settings['text_format'] = text_format
        settings_manager.save_settings(settings)
        
        status_text = "تم تفعيل" if new_state else "تم تعطيل"
        
        # إرسال الإشعار فوراً
        await callback.answer(f"✅ {status_text} تنسيق النص الموحد")
        
        logger.info(f"🔄 تغيير حالة تنسيق النص للمستخدم {user_id} مهمة {task_id}: {new_state}")
        
        # إعادة تحميل الإعدادات للتأكد
        settings = settings_manager.load_settings()
        text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
        
        enabled = text_format.get('enabled', False)
        current_format = text_format.get('format_type', 'normal')
        text_link_url = text_format.get('text_link_url', '')
        
        # بناء الرسالة واللوحة
        text = _build_text_format_message(enabled, current_format, text_link_url)
        keyboard = get_text_format_keyboard(user_id, task_id)
        
        try:
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            logger.info(f"✅ تم تحديث اللوحة بنجاح - enabled={enabled}, format={current_format}")
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                logger.error(f"خطأ في تحديث الرسالة: {edit_error}")
        
    except Exception as e:
        logger.error(f"خطأ في text_format_toggle: {e}", exc_info=True)
        await callback.answer("❌ حدث خطأ أثناء التبديل", show_alert=True)

@router.callback_query(F.data.startswith("text_format_set_"))
async def text_format_set(callback: CallbackQuery):
    """تعيين نوع التنسيق"""
    try:
        # استخراج task_id و format_type بطريقة صحيحة
        # الشكل: text_format_set_{task_id}_{format_type}
        callback_data = callback.data
        prefix = "text_format_set_"
        rest = callback_data[len(prefix):]  # إزالة البادئة
        
        # فصل task_id عن format_type
        parts = rest.split('_', 1)  # نفصل عند أول underscore فقط
        task_id = int(parts[0])
        format_type = parts[1] if len(parts) > 1 else 'normal'
        
        user_id = callback.from_user.id
        
        # التحقق من صحة نوع التنسيق
        if format_type not in TextFormatter.SUPPORTED_FORMATS:
            await callback.answer("❌ نوع تنسيق غير صحيح", show_alert=True)
            logger.warning(f"⚠️ محاولة اختيار تنسيق غير مدعوم: {format_type}")
            return
        
        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.update_setting('text_format', 'format_type', format_type)
        
        format_name = TextFormatter.get_format_display_name(format_type)
        
        # إرسال الإشعار فوراً
        await callback.answer(f"✅ تم اختيار: {format_name}")
        
        logger.info(f"✅ تم اختيار تنسيق '{format_type}' للمستخدم {user_id} مهمة {task_id}")
        
        # تحديث القائمة
        settings = settings_manager.load_settings()
        text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
        
        text = _build_text_format_message(text_format['enabled'], text_format['format_type'], text_format.get('text_link_url', ''))
        keyboard = get_text_format_keyboard(user_id, task_id)
        
        try:
            await callback.message.edit_text(
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                logger.error(f"خطأ في تحديث الرسالة: {edit_error}")
        
    except Exception as e:
        logger.error(f"خطأ في text_format_set: {e}", exc_info=True)

@router.callback_query(F.data.startswith("text_format_customize_link_"))
async def text_format_customize_link(callback: CallbackQuery, state: FSMContext):
    """فتح نافذة إدخال الرابط لتنسيق text_link"""
    try:
        task_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id
        
        await state.set_state(TextFormatStates.waiting_for_link)
        await state.update_data(task_id=task_id, user_id=user_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"text_format_menu_{task_id}")]
        ])
        
        await callback.message.edit_text(
            "🔗 <b>تخصيص رابط النص</b>\n\n"
            "أرسل الرابط الذي تريد استخدامه لجميع النصوص.\n\n"
            "💡 <b>أمثلة:</b>\n"
            "• https://t.me/yourchannel\n"
            "• https://example.com\n"
            "• https://twitter.com/username\n\n"
            "⚠️ تأكد من أن الرابط صحيح ويبدأ بـ http:// أو https://",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"خطأ في text_format_customize_link: {e}", exc_info=True)
        await callback.answer("❌ حدث خطأ", show_alert=True)

@router.message(TextFormatStates.waiting_for_link)
async def process_text_link_url(message: Message, state: FSMContext):
    """معالجة الرابط المدخل"""
    try:
        data = await state.get_data()
        task_id = data.get('task_id')
        user_id = data.get('user_id')
        
        url = message.text.strip()
        
        # التحقق من صحة الرابط
        if not url.startswith(('http://', 'https://')):
            await message.answer(
                "❌ الرابط غير صحيح!\n\n"
                "يجب أن يبدأ الرابط بـ http:// أو https://\n"
                "مثال: https://t.me/yourchannel"
            )
            return
        
        # حفظ الرابط
        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.update_setting('text_format', 'text_link_url', url)
        
        await message.answer(f"✅ تم حفظ الرابط بنجاح!\n\n🔗 {url}")
        
        # العودة إلى قائمة التنسيق
        await state.clear()
        
        settings = settings_manager.load_settings()
        text_format = settings.get('text_format', {'enabled': False, 'format_type': 'normal', 'text_link_url': ''})
        
        text = _build_text_format_message(text_format['enabled'], text_format['format_type'], text_format.get('text_link_url', ''))
        keyboard = get_text_format_keyboard(user_id, task_id)
        
        await message.answer(text, parse_mode='HTML', reply_markup=keyboard)
        
        logger.info(f"✅ تم حفظ رابط text_link للمستخدم {user_id} مهمة {task_id}: {url}")
        
    except Exception as e:
        logger.error(f"خطأ في process_text_link_url: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء حفظ الرابط")
        await state.clear()
