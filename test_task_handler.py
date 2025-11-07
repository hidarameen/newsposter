
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from user_task_manager import UserTaskManager
from message_processor import MessageProcessor
from album_processor import AlbumProcessor
from entity_handler import EntityHandler

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data.startswith("test_task:"))
async def test_task(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[1])
    
    task_manager = UserTaskManager(user_id)
    task = task_manager.get_task(task_id)
    
    if not task:
        await callback.answer("❌ المهمة غير موجودة", show_alert=True)
        return
    
    await callback.answer("🔄 جاري اختبار المهمة...", show_alert=False)
    
    try:
        bot: Bot = callback.bot
        source_channel_id = task.source_channel['id']
        target_channel_id = task.target_channel['id']
        
        try:
            last_message = await bot.send_message(source_channel_id, "اختبار")
            await bot.delete_message(source_channel_id, last_message.message_id)
        except:
            pass
        
        chat = await bot.get_chat(source_channel_id)
        
        test_text = f"""🧪 <b>اختبار المهمة</b>

✅ تم جلب معلومات المصدر بنجاح!

📊 <b>معلومات المصدر:</b>
• الاسم: {chat.title}
• النوع: {chat.type}

⚙️ <b>الإعدادات المطبقة:</b>
"""
        
        message_processor = MessageProcessor(user_id, task_id)
        settings_summary = message_processor.get_settings_summary()
        
        test_text += "\n" + settings_summary
        
        test_text += "\n\n💡 <b>ملاحظة:</b>\n"
        test_text += "سيتم تطبيق هذه الإعدادات على جميع الرسائل القادمة من المصدر."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(test_text, parse_mode='HTML', reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"خطأ في اختبار المهمة: {e}")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"task_settings:{task_id}")]
        ])
        
        await callback.message.edit_text(
            f"❌ <b>خطأ في اختبار المهمة</b>\n\n"
            f"تفاصيل الخطأ: {str(e)}\n\n"
            f"تأكد من أن البوت لديه صلاحيات كافية في المصدر.",
            parse_mode='HTML',
            reply_markup=keyboard
        )
