import logging
import asyncio
from typing import Dict, Optional
from aiogram import Bot

logger = logging.getLogger(__name__)

class AutoDeleteManager:
    """مدير الحذف التلقائي للرسائل"""
    
    def __init__(self):
        # {task_key: asyncio.Task}
        self.deletion_tasks: Dict[str, asyncio.Task] = {}
    
    def schedule_deletion(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        delay_seconds: int,
        task_id: Optional[int] = None
    ):
        """
        جدولة حذف رسالة بعد مدة معينة
        
        Args:
            bot: مثيل البوت
            chat_id: معرف القناة
            message_id: معرف الرسالة
            delay_seconds: التأخير بالثواني
            task_id: معرف المهمة (اختياري للتتبع)
        """
        if delay_seconds <= 0:
            logger.warning(f"⚠️ تأخير الحذف غير صالح: {delay_seconds} ثانية")
            return
        
        task_key = f"{chat_id}_{message_id}"
        
        # إلغاء المهمة السابقة إن وجدت
        if task_key in self.deletion_tasks:
            self.deletion_tasks[task_key].cancel()
        
        # إنشاء مهمة جديدة
        task = asyncio.create_task(
            self._delete_message_after_delay(
                bot, chat_id, message_id, delay_seconds, task_id
            )
        )
        
        self.deletion_tasks[task_key] = task
        
        logger.info(
            f"⏰ جدولة حذف الرسالة {message_id} من القناة {chat_id} "
            f"بعد {delay_seconds} ثانية"
        )
    
    async def _delete_message_after_delay(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        delay: int,
        task_id: Optional[int]
    ):
        """حذف رسالة بعد مدة معينة"""
        try:
            await asyncio.sleep(delay)
            
            try:
                await bot.delete_message(chat_id, message_id)
                logger.info(
                    f"🗑️ تم حذف الرسالة {message_id} من القناة {chat_id} "
                    f"تلقائياً (المهمة: {task_id})"
                )
            except Exception as e:
                logger.error(
                    f"❌ فشل حذف الرسالة {message_id} من القناة {chat_id}: {e}"
                )
            
            # إزالة المهمة من القائمة
            task_key = f"{chat_id}_{message_id}"
            if task_key in self.deletion_tasks:
                del self.deletion_tasks[task_key]
                
        except asyncio.CancelledError:
            logger.info(f"⚠️ تم إلغاء مهمة حذف الرسالة {message_id}")
        except Exception as e:
            logger.error(f"❌ خطأ في مهمة الحذف التلقائي: {e}")
    
    def cancel_deletion(self, chat_id: int, message_id: int):
        """إلغاء حذف رسالة مجدولة"""
        task_key = f"{chat_id}_{message_id}"
        
        if task_key in self.deletion_tasks:
            self.deletion_tasks[task_key].cancel()
            del self.deletion_tasks[task_key]
            logger.info(f"❌ تم إلغاء حذف الرسالة {message_id}")
    
    def cancel_all_deletions(self):
        """إلغاء جميع مهام الحذف المجدولة"""
        for task in self.deletion_tasks.values():
            task.cancel()
        
        self.deletion_tasks.clear()
        logger.info("🛑 تم إلغاء جميع مهام الحذف التلقائي")
    
    def get_pending_deletions_count(self) -> int:
        """الحصول على عدد مهام الحذف المعلقة"""
        return len(self.deletion_tasks)
    
    @staticmethod
    def convert_time_to_seconds(value: int, unit: str) -> int:
        """
        تحويل الوقت إلى ثواني
        
        Args:
            value: القيمة
            unit: الوحدة (seconds, minutes, hours, days)
            
        Returns:
            الوقت بالثواني
        """
        conversions = {
            'seconds': 1,
            'minutes': 60,
            'hours': 3600,
            'days': 86400
        }
        
        return value * conversions.get(unit, 1)

# مثيل عام
auto_delete_manager = AutoDeleteManager()
