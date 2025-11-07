
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from task_settings_manager import TaskSettingsManager
from subscription_manager import SubscriptionManager, PREMIUM_FEATURES
from entity_handler import EntityHandler
import re

logger = logging.getLogger(__name__)
router = Router()

def parse_markdown_entities(text: str) -> tuple[str, list]:
    """
    تحويل Markdown syntax إلى entities - محاكاة سلوك Telegram الفعلي
    يدعم: **bold**, *italic*, __underline__, ~~strikethrough~~, `code`, ```code block```, [link](url)
    
    ملاحظة: هذه دالة احتياطية تستخدم فقط إذا لم يقم Telegram بالتحويل التلقائي
    """
    if not text or not any(marker in text for marker in ['**', '__', '~~', '*', '`', '[', '```']):
        return text, []
    
    entities = []
    clean_text = text
    
    # الترتيب مهم: نبدأ بالأنماط الأطول أولاً لتجنب التداخل
    patterns = [
        # Code blocks (``` يجب أن يكون قبل ` العادي)
        (r'```([^\n]*)\n(.*?)```', 'pre', '```', True),  # ```language\ncode```
        (r'```(.*?)```', 'pre', '```', False),           # ```code```
        # Inline formatting - الترتيب مهم: ** قبل * لتجنب التداخل
        (r'\[([^\]]+)\]\(([^\)]+)\)', 'text_link', '[]()', True),  # [text](url)
        (r'\*\*(.+?)\*\*', 'bold', '**', False),                   # **bold**
        (r'__(.+?)__', 'underline', '__', False),                  # __underline__
        (r'~~(.+?)~~', 'strikethrough', '~~', False),              # ~~strike~~
        (r'`(.+?)`', 'code', '`', False),                          # `code`
        # * للمائل يجب أن يكون بعد ** لتجنب التطابق الخاطئ
        (r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', 'italic', '*', False),  # *italic* (لكن ليس **)
    ]
    
    for pattern, entity_type, marker, has_special_handling in patterns:
        matches_found = []
        
        for match in re.finditer(pattern, clean_text):
            if entity_type == 'text_link':
                # معالجة خاصة للروابط
                link_text = match.group(1)
                url = match.group(2)
                start = match.start()
                
                matches_found.append({
                    'match': match,
                    'entity': {
                        'type': 'text_link',
                        'offset': start,
                        'length': len(link_text),
                        'url': url
                    },
                    'replacement': link_text
                })
            elif entity_type == 'pre' and has_special_handling:
                # Code block مع لغة
                language = match.group(1).strip()
                code = match.group(2)
                start = match.start()
                
                entity_data = {
                    'type': 'pre',
                    'offset': start,
                    'length': len(code)
                }
                if language:
                    entity_data['language'] = language
                
                matches_found.append({
                    'match': match,
                    'entity': entity_data,
                    'replacement': code
                })
            else:
                # التنسيقات العادية
                content = match.group(1)
                start = match.start()
                
                matches_found.append({
                    'match': match,
                    'entity': {
                        'type': entity_type,
                        'offset': start,
                        'length': len(content)
                    },
                    'replacement': content
                })
        
        # استبدال من الآخر إلى الأول لتجنب تغيير المواقع
        for match_data in reversed(matches_found):
            match = match_data['match']
            replacement = match_data['replacement']
            entity = match_data['entity']
            
            # حساب الموقع الجديد بعد الاستبدالات السابقة
            offset_before = len(clean_text[:match.start()])
            clean_text = clean_text[:match.start()] + replacement + clean_text[match.end():]
            
            # تحديث offset للـ entity
            entity['offset'] = offset_before
            entities.append(entity)
    
    # ترتيب entities حسب offset
    entities.sort(key=lambda x: x['offset'])
    
    # إعادة حساب offsets بصيغة UTF-16 (Telegram format)
    final_entities = []
    for entity in entities:
        py_offset = entity['offset']
        py_length = entity['length']
        
        utf16_offset = EntityHandler.python_offset_to_utf16(clean_text, py_offset)
        utf16_end = EntityHandler.python_offset_to_utf16(clean_text, py_offset + py_length)
        utf16_length = utf16_end - utf16_offset
        
        final_entity = {
            'type': entity['type'],
            'offset': utf16_offset,
            'length': utf16_length
        }
        
        # إضافة الحقول الإضافية إن وجدت
        if 'url' in entity:
            final_entity['url'] = entity['url']
        if 'language' in entity:
            final_entity['language'] = entity['language']
        
        final_entities.append(final_entity)
    
    return clean_text, final_entities

class ReplacementStates(StatesGroup):
    waiting_for_old = State()
    waiting_for_new = State()

def check_premium(feature_key, subscription_manager):
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

@router.callback_query(F.data.startswith("settings_replacements:"))
async def settings_replacements(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    sub_manager = SubscriptionManager(user_id)
    is_premium, error_msg = check_premium('replacements', sub_manager)
    
    if not is_premium:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(error_msg, parse_mode='HTML', reply_markup=keyboard)
        await callback.answer()
        return
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    replacements_settings = settings_manager.get_setting('replacements')
    
    enabled = replacements_settings.get('enabled', False)
    pairs = replacements_settings.get('pairs', [])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 تعطيل" if enabled else "🟢 تفعيل", callback_data=f"toggle_replacements:{task_id}")],
        [InlineKeyboardButton(text="➕ إضافة استبدال", callback_data=f"add_replacement:{task_id}")],
        [InlineKeyboardButton(text="📋 عرض القائمة", callback_data=f"show_replacements:{task_id}")],
        [InlineKeyboardButton(text="🗑️ مسح الكل", callback_data=f"clear_replacements:{task_id}")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
    ])
    
    status = "مفعّل ✅" if enabled else "معطّل ❌"
    count = f"\n\n<b>عدد الاستبدالات:</b> {len(pairs)}" if pairs else "\n\n⚠️ القائمة فارغة"
    
    await callback.message.edit_text(
        f"🔄 <b>الاستبدالات</b>\n\n"
        f"الحالة: {status}{count}\n\n"
        f"💡 استبدال نصوص معينة بأخرى مع الحفاظ على التنسيقات",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_replacements:"))
async def toggle_replacements(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    new_status = settings_manager.toggle_feature('replacements')
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} الاستبدالات")
    await settings_replacements(callback)

@router.callback_query(F.data.startswith("add_replacement:"))
async def add_replacement(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    await state.set_state(ReplacementStates.waiting_for_old)
    await state.update_data(task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await callback.message.edit_text(
        "🔄 <b>إضافة استبدال جديد</b>\n\n"
        "📝 يمكنك إضافة الاستبدال بطريقتين:\n\n"
        "<b>الطريقة السريعة:</b>\n"
        "أرسل: <code>النص_القديم >> النص_الجديد</code>\n"
        "مثال: <code>مرحبا >> </code><b>أهلا وسهلا</b>\n\n"
        "<b>للحذف:</b>\n"
        "أرسل: <code>النص_المراد_حذفه >></code> (بدون نص جديد)\n"
        "مثال: <code>إعلان >></code>\n\n"
        "<b>الطريقة التفصيلية:</b>\n"
        "أرسل النص القديم فقط، وسيطلب منك النص الجديد في الخطوة التالية\n\n"
        "💡 <b>طرق التنسيق:</b>\n"
        "  • <b>عريض</b>: **نص** أو استخدم زر Bold\n"
        "  • <i>مائل</i>: *نص* أو استخدم زر Italic\n"
        "  • <u>تحته خط</u>: __نص__\n"
        "  • <s>مشطوب</s>: ~~نص~~\n"
        "  • <code>كود</code>: `نص`\n\n"
        "⚠️ <b>ملاحظة مهمة:</b> إذا أرسلت النص مع صورة/فيديو/ملف، استخدم Markdown (**//__/~~) أو أزرار التنسيق في Telegram",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await callback.answer()

@router.message(ReplacementStates.waiting_for_old)
async def process_old_text(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    user_id = message.from_user.id
    
    # تسجيل تشخيصي مفصل
    logger.info(f"📥 استلام رسالة في waiting_for_old:")
    logger.info(f"   message.text: {repr(message.text)}")
    logger.info(f"   message.caption: {repr(message.caption)}")
    logger.info(f"   message.entities: {message.entities}")
    logger.info(f"   message.caption_entities: {message.caption_entities}")
    logger.info(f"   عدد Entities: {len(message.entities) if message.entities else 0}")
    
    if message.entities:
        for e in message.entities:
            logger.info(f"      Entity: type={e.type}, offset={e.offset}, length={e.length}")
    else:
        logger.warning(f"   ⚠️ لا توجد entities من Telegram!")
    
    # التحقق من استخدام الطريقة السريعة (مع >>)
    if '>>' in message.text:
        # الطريقة السريعة - تقسيم النص فقط، الـ entities نأخذها كما هي
        split_position = message.text.find('>>')
        
        # استخراج النصين الخام (بدون strip)
        old_text_raw = message.text[:split_position]
        new_text_raw = message.text[split_position + 2:]
        
        # حساب عدد المسافات في البداية لكل قسم
        old_text_start_spaces = len(old_text_raw) - len(old_text_raw.lstrip())
        new_text_start_spaces = len(new_text_raw) - len(new_text_raw.lstrip())
        
        # النص النهائي بعد strip
        old_text = old_text_raw.strip()
        new_text = new_text_raw.strip()
        
        # التحقق من النص القديم فقط (النص الجديد يمكن أن يكون فارغاً للحذف)
        if not old_text:
            await message.answer("❌ يجب كتابة النص القديم بشكل صحيح")
            return
        
        # دعم الحذف: إذا كان النص الجديد فارغاً، نستخدم سلسلة فارغة
        is_deletion = not new_text
        if is_deletion:
            new_text = ""  # استبدال بنص فارغ = حذف
        
        # ✅ تحويل الـ entities مرة واحدة فقط (مثل Header/Footer تمامًا)
        if message.entities:
            all_entities = EntityHandler.entities_to_dict(message.entities, message.text)
            logger.info(f"✅ تحويل {len(all_entities)} entities")
            
            # تقسيم entities بين old و new بناءً على موقعها في النص الأصلي
            old_entities = []
            new_entities = []
            
            for entity in all_entities:
                py_offset = EntityHandler.utf16_offset_to_python(message.text, entity['offset'])
                
                # إذا كانت Entity قبل ">>" فهي للنص القديم
                if py_offset < split_position:
                    # تعديل offset لإزالة المسافات في البداية
                    adjusted_entity = entity.copy()
                    new_py_offset = py_offset - old_text_start_spaces
                    if new_py_offset >= 0:  # تأكد أن الـ entity داخل النص المفيد
                        adjusted_entity['offset'] = EntityHandler.python_offset_to_utf16(old_text, new_py_offset)
                        old_entities.append(adjusted_entity)
                # إذا كانت بعد ">>" فهي للنص الجديد - نعدل offset بطرح موقع >>
                elif py_offset >= split_position + 2:
                    adjusted_entity = entity.copy()
                    # حساب الموقع الجديد نسبة للنص الجديد (بعد إزالة ">>" والمسافات)
                    new_py_offset = py_offset - (split_position + 2) - new_text_start_spaces
                    if new_py_offset >= 0:  # تأكد أن الـ entity داخل النص المفيد
                        adjusted_entity['offset'] = EntityHandler.python_offset_to_utf16(new_text, new_py_offset)
                        new_entities.append(adjusted_entity)
        else:
            old_entities = []
            new_entities = []
        
        # تسجيل entities قبل الحفظ
        logger.info(f"💾 الطريقة السريعة - حفظ استبدال:")
        logger.info(f"   old_text: '{old_text}'")
        logger.info(f"   new_text: '{new_text}'")
        logger.info(f"   old_entities: {len(old_entities)} items")
        if old_entities:
            for i, e in enumerate(old_entities):
                logger.info(f"      old_entities[{i}]: {e}")
        logger.info(f"   new_entities: {len(new_entities)} items")
        if new_entities:
            for i, e in enumerate(new_entities):
                logger.info(f"      new_entities[{i}]: {e}")
        
        # حفظ الاستبدال
        settings_manager = TaskSettingsManager(user_id, task_id)
        settings_manager.add_replacement(old_text, new_text, old_entities, new_entities)
        
        # عرض معاينة
        preview_old = EntityHandler.entities_to_html(old_text, old_entities) if old_entities else old_text
        
        if is_deletion:
            await message.answer(
                f"✅ تم إضافة قاعدة الحذف بنجاح\n\n"
                f"<b>سيتم حذف:</b>\n{preview_old}",
                parse_mode='HTML'
            )
        else:
            preview_new = EntityHandler.entities_to_html(new_text, new_entities) if new_entities else new_text
            await message.answer(
                f"✅ تم إضافة الاستبدال بنجاح\n\n"
                f"<b>القديم:</b>\n{preview_old}\n\n"
                f"<b>الجديد:</b>\n{preview_new}",
                parse_mode='HTML'
            )
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_replacements:{task_id}")]
        ])
        await message.answer("اضغط للعودة:", reply_markup=keyboard)
        return
    
    # الطريقة التفصيلية - نفس منطق Header/Footer تمامًا
    old_text = message.text
    
    # ✅ تحويل entities مباشرة (مثل Header/Footer) - بدون شرط!
    old_entities = EntityHandler.entities_to_dict(message.entities, message.text)
    
    logger.info(f"💾 الخطوة 1 - حفظ النص القديم:")
    logger.info(f"   النص: '{old_text}'")
    logger.info(f"   عدد entities: {len(old_entities)}")
    for i, e in enumerate(old_entities):
        logger.info(f"   [{i}] {e}")
    
    await state.update_data(
        old_text=old_text,
        old_entities=old_entities
    )
    await state.set_state(ReplacementStates.waiting_for_new)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_input:{task_id}")]
    ])
    
    await message.answer(
        "🔄 <b>إضافة استبدال جديد</b>\n\n"
        "📝 <b>الخطوة 2:</b> أرسل النص الجديد\n\n"
        "💡 يمكنك استخدام التنسيقات (عريض، مائل، إلخ) في النص\n\n"
        "🗑️ <b>للحذف:</b> اكتب <code>حذف</code> لحذف النص القديم بدلاً من استبداله",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@router.message(ReplacementStates.waiting_for_new)
async def process_new_text(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_id')
    old_text = data.get('old_text')
    old_entities = data.get('old_entities', [])
    user_id = message.from_user.id
    
    # تسجيل تشخيصي مفصل
    logger.info(f"📥 استلام رسالة في waiting_for_new:")
    logger.info(f"   message.text: {repr(message.text)}")
    logger.info(f"   message.entities: {message.entities}")
    logger.info(f"   عدد entities: {len(message.entities) if message.entities else 0}")
    
    # التحقق من كلمة "حذف" للحذف
    is_deletion = message.text.strip().lower() == "حذف"
    
    if is_deletion:
        # حذف النص القديم (استبدال بنص فارغ)
        new_text = ""
        new_entities = []
        logger.info(f"🗑️ الخطوة 2 - حذف النص القديم")
    else:
        # استبدال عادي
        new_text = message.text
        # تحويل entities مباشرة (مثل Header/Footer تماماً - بدون شرط!)
        new_entities = EntityHandler.entities_to_dict(message.entities, message.text)
        
        logger.info(f"💾 الخطوة 2 - حفظ النص الجديد:")
        logger.info(f"   النص: '{new_text}'")
        logger.info(f"   عدد entities: {len(new_entities) if new_entities else 0}")
        for i, e in enumerate(new_entities):
            logger.info(f"   [{i}] {e}")
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    
    # حفظ الاستبدال
    logger.info(f"💾 حفظ استبدال:")
    logger.info(f"   القديم: '{old_text}' مع {len(old_entities) if old_entities else 0} entities")
    logger.info(f"   الجديد: '{new_text}' مع {len(new_entities) if new_entities else 0} entities")
    logger.info(f"   نوع العملية: {'حذف' if is_deletion else 'استبدال'}")
    
    settings_manager.add_replacement(old_text, new_text, old_entities, new_entities)
    
    # التحقق من الحفظ
    saved_pairs = settings_manager.get_setting('replacements', 'pairs')
    last_pair = saved_pairs[-1] if saved_pairs else None
    if last_pair:
        logger.info(f"✅ تم التحقق من الحفظ:")
        logger.info(f"   old_entities المحفوظة: {len(last_pair.get('old_entities', []))}")
        logger.info(f"   new_entities المحفوظة: {len(last_pair.get('new_entities', []))}")
    
    # عرض معاينة مع التنسيقات
    preview_old = EntityHandler.entities_to_html(old_text, old_entities) if old_entities else old_text
    
    if is_deletion:
        await message.answer(
            f"✅ تم إضافة قاعدة الحذف بنجاح\n\n"
            f"<b>سيتم حذف:</b>\n{preview_old}",
            parse_mode='HTML'
        )
    else:
        preview_new = EntityHandler.entities_to_html(new_text, new_entities) if new_entities else new_text
        await message.answer(
            f"✅ تم إضافة الاستبدال بنجاح\n\n"
            f"<b>القديم:</b>\n{preview_old}\n\n"
            f"<b>الجديد:</b>\n{preview_new}",
            parse_mode='HTML'
        )
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_replacements:{task_id}")]
    ])
    await message.answer("اضغط للعودة:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_replacements:"))
async def show_replacements(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    pairs = settings_manager.get_setting('replacements', 'pairs')
    
    if not pairs:
        await callback.answer("القائمة فارغة", show_alert=True)
        return
    
    text = "🔄 <b>قائمة الاستبدالات:</b>\n\n"
    for i, pair in enumerate(pairs, 1):
        old = pair.get('old', '')
        new = pair.get('new', '')
        old_entities = pair.get('old_entities', [])
        new_entities = pair.get('new_entities', [])
        
        # عرض النص مع التنسيقات
        old_formatted = EntityHandler.entities_to_html(old, old_entities) if old_entities else old
        
        # إذا كان النص الجديد فارغاً، هذه قاعدة حذف
        if not new:
            text += f"{i}. 🗑️ <s>{old_formatted}</s> (حذف)\n\n"
        else:
            new_formatted = EntityHandler.entities_to_html(new, new_entities) if new_entities else new
            text += f"{i}. {old_formatted} → {new_formatted}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"settings_replacements:{task_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("clear_replacements:"))
async def clear_replacements(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    settings_manager = TaskSettingsManager(user_id, task_id)
    settings_manager.clear_replacements()
    
    await callback.answer("✅ تم مسح جميع الاستبدالات", show_alert=True)
    await settings_replacements(callback)

@router.callback_query(F.data.startswith("cancel_input:"))
async def cancel_input(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    await state.clear()
    
    # العودة لصفحة الاستبدالات
    callback.data = f"settings_replacements:{task_id}"
    await settings_replacements(callback)
