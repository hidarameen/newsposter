import logging
import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)

class AutoPinManager:
    """مدير التثبيت التلقائي للرسائل"""
    
    def __init__(self):
        self.delete_notification_tasks = {}
    
    async def pin_message(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        disable_notification: bool = True,
        delete_notification_after: Optional[int] = None
    ) -> bool:
        """
        تثبيت رسالة في القناة
        
        Args:
            bot: مثيل البوت
            chat_id: معرف القناة
            message_id: معرف الرسالة
            disable_notification: تعطيل إشعار التثبيت
            delete_notification_after: حذف إشعار التثبيت بعد X ثانية
        
        Returns:
            نجاح العملية
        """
        try:
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=disable_notification
            )
            
            logger.info(f"📌 تم تثبيت الرسالة {message_id} في القناة {chat_id}")
            
            # حذف إشعار التثبيت بعد مدة معينة
            if delete_notification_after and delete_notification_after > 0:
                task_key = f"{chat_id}_{message_id}"
                
                # إلغاء المهمة السابقة إن وجدت
                if task_key in self.delete_notification_tasks:
                    self.delete_notification_tasks[task_key].cancel()
                
                # إنشاء مهمة جديدة
                task = asyncio.create_task(
                    self._delete_pin_notification(
                        bot, chat_id, message_id, delete_notification_after
                    )
                )
                self.delete_notification_tasks[task_key] = task
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تثبيت الرسالة {message_id} في القناة {chat_id}: {e}")
            return False
    
    async def _delete_pin_notification(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        delay: int
    ):
        """حذف إشعار التثبيت بعد مدة معينة"""
        try:
            await asyncio.sleep(delay)
            
            # البحث عن رسالة إشعار التثبيت وحذفها
            # عادة ما تكون الرسالة التالية مباشرة بعد الرسالة المثبتة
            try:
                await bot.delete_message(chat_id, message_id + 1)
                logger.info(f"🗑️ تم حذف إشعار التثبيت للرسالة {message_id}")
            except:
                # قد لا يكون هناك إشعار أو تم حذفه مسبقاً
                pass
            
            # إزالة المهمة من القائمة
            task_key = f"{chat_id}_{message_id}"
            if task_key in self.delete_notification_tasks:
                del self.delete_notification_tasks[task_key]
                
        except asyncio.CancelledError:
            logger.info(f"⚠️ تم إلغاء مهمة حذف إشعار التثبيت للرسالة {message_id}")
        except Exception as e:
            logger.error(f"❌ خطأ في حذف إشعار التثبيت: {e}")
    
    async def unpin_message(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int
    ) -> bool:
        """إلغاء تثبيت رسالة"""
        try:
            await bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=message_id
            )
            logger.info(f"📍 تم إلغاء تثبيت الرسالة {message_id} في القناة {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في إلغاء تثبيت الرسالة: {e}")
            return False
    
    def cancel_all_tasks(self):
        """إلغاء جميع مهام حذف الإشعارات"""
        for task in self.delete_notification_tasks.values():
            task.cancel()
        self.delete_notification_tasks.clear()
        logger.info("🛑 تم إلغاء جميع مهام حذف إشعارات التثبيت")

# مثيل عام
auto_pin_manager = AutoPinManager()
