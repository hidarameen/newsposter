import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Set
from config import USERS_DATA_DIR
from aiogram.types import Message
from aiogram import Bot

logger = logging.getLogger(__name__)

class BroadcastManager:
    """مدير الإذاعة - إرسال رسائل جماعية"""
    
    @staticmethod
    async def get_all_users() -> List[int]:
        """الحصول على قائمة بجميع معرفات المستخدمين"""
        users = []
        try:
            users_dir = Path(USERS_DATA_DIR)
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir() and user_dir.name.isdigit():
                        users.append(int(user_dir.name))
            logger.info(f"تم العثور على {len(users)} مستخدم")
        except Exception as e:
            logger.error(f"خطأ في الحصول على المستخدمين: {e}")
        return users
    
    @staticmethod
    async def get_all_target_channels() -> Set[int]:
        """الحصول على جميع القنوات الهدف من مهام المستخدمين"""
        channels = set()
        try:
            from user_task_manager import UserTaskManager
            users = await BroadcastManager.get_all_users()
            
            for user_id in users:
                utm = UserTaskManager(user_id)
                tasks = utm.get_all_tasks()
                for task_id, task in tasks.items():
                    if hasattr(task, 'target_channel'):
                        channels.add(task.target_channel)
                    elif isinstance(task, dict) and 'target_channel' in task:
                        channels.add(task['target_channel'])
            
            logger.info(f"تم العثور على {len(channels)} قناة هدف")
        except Exception as e:
            logger.error(f"خطأ في الحصول على القنوات الهدف: {e}")
        return channels
    
    @staticmethod
    async def get_all_admin_targets() -> Set[int]:
        """الحصول على جميع الأهداف من مهام المشرف"""
        targets = set()
        try:
            from forwarding_manager import ForwardingManager
            fm = ForwardingManager()
            admin_tasks = fm.get_all_tasks()
            
            for task_id, task in admin_tasks.items():
                for target in task.target_channels:
                    targets.add(target['id'])
            
            logger.info(f"تم العثور على {len(targets)} هدف من مهام المشرف")
        except Exception as e:
            logger.error(f"خطأ في الحصول على أهداف المشرف: {e}")
        return targets
    
    @staticmethod
    async def broadcast_to_users(
        bot: Bot,
        message: Message,
        users: List[int],
        progress_callback=None
    ) -> Dict[str, int]:
        """إرسال رسالة لجميع المستخدمين"""
        success = 0
        failed = 0
        blocked = 0
        
        total = len(users)
        
        for idx, user_id in enumerate(users, 1):
            try:
                # نسخ الرسالة للمستخدم
                if message.text:
                    await bot.send_message(
                        user_id,
                        message.text,
                        entities=message.entities
                    )
                elif message.photo:
                    await bot.send_photo(
                        user_id,
                        message.photo[-1].file_id,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.video:
                    await bot.send_video(
                        user_id,
                        message.video.file_id,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.document:
                    await bot.send_document(
                        user_id,
                        message.document.file_id,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                else:
                    await bot.copy_message(user_id, message.chat.id, message.message_id)
                
                success += 1
                
                # تأخير صغير لتجنب حد المعدل
                if idx % 30 == 0:
                    await asyncio.sleep(1)
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'blocked' in error_msg or 'user is deactivated' in error_msg:
                    blocked += 1
                else:
                    failed += 1
                logger.debug(f"فشل الإرسال للمستخدم {user_id}: {e}")
            
            # تحديث التقدم كل 10 رسائل
            if progress_callback and idx % 10 == 0:
                await progress_callback(idx, total, success, failed, blocked)
        
        return {
            'success': success,
            'failed': failed,
            'blocked': blocked,
            'total': total
        }
    
    @staticmethod
    async def broadcast_to_channels(
        bot: Bot,
        message: Message,
        channels: List[int],
        progress_callback=None
    ) -> Dict[str, int]:
        """إرسال رسالة لجميع القنوات"""
        success = 0
        failed = 0
        no_permission = 0
        
        total = len(channels)
        
        for idx, channel_id in enumerate(channels, 1):
            try:
                # نسخ الرسالة للقناة
                await bot.copy_message(channel_id, message.chat.id, message.message_id)
                success += 1
                
                # تأخير صغير
                if idx % 20 == 0:
                    await asyncio.sleep(1)
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'not enough rights' in error_msg or 'admin' in error_msg:
                    no_permission += 1
                else:
                    failed += 1
                logger.debug(f"فشل الإرسال للقناة {channel_id}: {e}")
            
            # تحديث التقدم
            if progress_callback and idx % 10 == 0:
                await progress_callback(idx, total, success, failed, no_permission)
        
        return {
            'success': success,
            'failed': failed,
            'no_permission': no_permission,
            'total': total
        }
    
    @staticmethod
    async def get_channel_type(bot: Bot, chat_id: int) -> str:
        """معرفة نوع الدردشة (قناة/مجموعة)"""
        try:
            chat = await bot.get_chat(chat_id)
            if chat.type == 'channel':
                return 'channel'
            elif chat.type in ['group', 'supergroup']:
                return 'group'
        except:
            pass
        return 'unknown'
    
    @staticmethod
    async def filter_channels_by_type(
        bot: Bot,
        channels: List[int],
        channel_type: str
    ) -> List[int]:
        """تصفية القنوات حسب النوع (قناة أو مجموعة)"""
        filtered = []
        
        for channel_id in channels:
            try:
                chat = await bot.get_chat(channel_id)
                
                if channel_type == 'channel' and chat.type == 'channel':
                    filtered.append(channel_id)
                elif channel_type == 'group' and chat.type in ['group', 'supergroup']:
                    filtered.append(channel_id)
            except:
                continue
        
        return filtered

broadcast_manager = BroadcastManager()
