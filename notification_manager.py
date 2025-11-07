import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from aiogram import Bot
from aiogram.types import Chat
from config import NOTIFICATIONS_CONFIG_FILE, EVENT_LOGS_FILE

logger = logging.getLogger(__name__)

def format_number(num: int) -> str:
    """تنسيق الأرقام بصيغة مختصرة (K للآلاف، M للملايين)"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)

async def format_channel_link(bot: Bot, channel_id: int, channel_title: str, 
                               username: Optional[str] = None, 
                               include_members: bool = True) -> str:
    """
    تنسيق رابط القناة كـ text link مع عرض عدد المشتركين
    
    Args:
        bot: البوت
        channel_id: معرف القناة
        channel_title: اسم القناة
        username: معرف المستخدم للقناة (إن وجد)
        include_members: هل يتم عرض عدد المشتركين
        
    Returns:
        رابط منسق بـ HTML
    """
    try:
        # الحصول على معلومات القناة
        chat = await bot.get_chat(channel_id)
        
        # الحصول على الرابط
        if username:
            # قناة عامة
            link_url = f"https://t.me/{username}"
        elif hasattr(chat, 'invite_link') and chat.invite_link:
            # قناة خاصة مع رابط دعوة موجود
            link_url = chat.invite_link
        else:
            # محاولة إنشاء رابط دعوة للقنوات الخاصة
            try:
                invite_link = await bot.export_chat_invite_link(channel_id)
                link_url = invite_link
            except:
                # إذا فشل، استخدم رابط افتراضي
                chat_id_str = str(channel_id).replace('-100', '')
                link_url = f"https://t.me/c/{chat_id_str}/1"
        
        # الحصول على عدد المشتركين
        members_text = ""
        if include_members:
            try:
                member_count = await bot.get_chat_member_count(channel_id)
                members_text = f" ({format_number(member_count)})"
            except:
                pass
        
        return f'<a href="{link_url}">{channel_title}</a>{members_text}'
    
    except Exception as e:
        logger.error(f"خطأ في تنسيق رابط القناة {channel_id}: {e}")
        return channel_title

class NotificationManager:
    def __init__(self):
        self.config_file = Path(NOTIFICATIONS_CONFIG_FILE)
        self.logs_file = Path(EVENT_LOGS_FILE)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطأ في تحميل إعدادات الإشعارات: {e}")
        
        return {
            "log_channel_id": None,
            "enabled_events": {
                "new_user": True,
                "bot_added_to_channel": True,
                "bot_restricted": True,
                "bot_removed": True,
                "task_created": True,
                "task_toggled": True,
                "task_deleted": True,
                "forwarding_report": True,
                "subscription_upgraded": True,
                "subscription_expired": True
            }
        }
    
    def _save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ إعدادات الإشعارات: {e}")
    
    def set_log_channel(self, channel_id: Optional[int]):
        self.config["log_channel_id"] = channel_id
        self._save_config()
        logger.info(f"تم تعيين قناة الإشعارات: {channel_id}")
    
    def get_log_channel(self) -> Optional[int]:
        return self.config.get("log_channel_id")
    
    def toggle_event(self, event_type: str, enabled: bool):
        if event_type in self.config["enabled_events"]:
            self.config["enabled_events"][event_type] = enabled
            self._save_config()
            logger.info(f"تم {'تفعيل' if enabled else 'تعطيل'} إشعار: {event_type}")
    
    def is_event_enabled(self, event_type: str) -> bool:
        return self.config["enabled_events"].get(event_type, False)
    
    def _log_event(self, event_type: str, payload: Dict[str, Any]):
        try:
            event_data = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                **payload
            }
            
            with open(self.logs_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event_data, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"خطأ في تسجيل الحدث: {e}")
    
    async def notify(self, bot: Bot, event_type: str, message: str, payload: Optional[Dict] = None):
        if not self.is_event_enabled(event_type):
            return
        
        log_channel = self.get_log_channel()
        if not log_channel:
            logger.warning("لم يتم تعيين قناة الإشعارات")
            return
        
        self._log_event(event_type, payload or {})
        
        try:
            await bot.send_message(
                chat_id=log_channel,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"تم إرسال إشعار {event_type} إلى قناة الإشعارات")
        except Exception as e:
            logger.error(f"خطأ في إرسال الإشعار: {e}")
    
    async def notify_new_user(self, bot: Bot, user_id: int, username: Optional[str], first_name: str):
        user_link = f'<a href="tg://user?id={user_id}">{first_name}</a>'
        message = f"""
🆕 <b>مستخدم جديد</b>

👤 <b>الاسم:</b> {user_link}
🆔 <b>المعرف:</b> <code>{user_id}</code>
🔗 <b>اسم المستخدم:</b> {'@' + username if username else 'غير متوفر'}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "new_user", message, {
            "user_id": user_id,
            "username": username,
            "first_name": first_name
        })
    
    async def notify_bot_added_to_channel(self, bot: Bot, channel_id: int, channel_title: str, 
                                          added_by_id: Optional[int], added_by_name: Optional[str],
                                          username: Optional[str] = None):
        channel_link = await format_channel_link(bot, channel_id, channel_title, username)
        added_by_link = f'<a href="tg://user?id={added_by_id}">{added_by_name}</a>' if added_by_id and added_by_name else (added_by_name or 'غير معروف')
        
        message = f"""
➕ <b>تمت إضافة البوت كمشرف</b>

📢 <b>القناة:</b> {channel_link}
🆔 <b>معرف القناة:</b> <code>{channel_id}</code>
👤 <b>أضافه:</b> {added_by_link}
🆔 <b>معرف المضيف:</b> <code>{added_by_id or 'غير متوفر'}</code>
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "bot_added_to_channel", message, {
            "channel_id": channel_id,
            "channel_title": channel_title,
            "added_by_id": added_by_id,
            "added_by_name": added_by_name
        })
    
    async def notify_bot_restricted(self, bot: Bot, channel_id: int, channel_title: str, username: Optional[str] = None):
        channel_link = await format_channel_link(bot, channel_id, channel_title, username)
        message = f"""
⚠️ <b>تم تقييد صلاحيات البوت</b>

📢 <b>القناة:</b> {channel_link}
🆔 <b>معرف القناة:</b> <code>{channel_id}</code>
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "bot_restricted", message, {
            "channel_id": channel_id,
            "channel_title": channel_title
        })
    
    async def notify_bot_removed(self, bot: Bot, channel_id: int, channel_title: str, username: Optional[str] = None):
        # للقنوات المحذوفة، لا نحاول الوصول إلى معلومات القناة
        if username:
            channel_link = f'<a href="https://t.me/{username}">{channel_title}</a>'
        else:
            channel_link = channel_title
        
        message = f"""
❌ <b>تم حذف البوت من القناة</b>

📢 <b>القناة:</b> {channel_link}
🆔 <b>معرف القناة:</b> <code>{channel_id}</code>
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "bot_removed", message, {
            "channel_id": channel_id,
            "channel_title": channel_title
        })
    
    async def notify_task_created(self, bot: Bot, user_id: int, user_name: str, 
                                  task_name: str, source_channel: str, target_channel: str):
        user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        message = f"""
✅ <b>مهمة جديدة</b>

👤 <b>المستخدم:</b> {user_link} (<code>{user_id}</code>)
📰 <b>المهمة:</b> {source_channel} → {target_channel}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "task_created", message, {
            "user_id": user_id,
            "user_name": user_name,
            "task_name": task_name,
            "source_channel": source_channel,
            "target_channel": target_channel
        })
    
    async def notify_task_toggled(self, bot: Bot, user_id: int, user_name: str, 
                                  task_name: str, is_active: bool):
        status = "تفعيل" if is_active else "تعطيل"
        icon = "▶️" if is_active else "⏸️"
        user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        message = f"""
{icon} <b>تم {status} مهمة</b>

👤 <b>المستخدم:</b> {user_link} (<code>{user_id}</code>)
📰 <b>المهمة:</b> {task_name}
📊 <b>الحالة:</b> {'نشطة' if is_active else 'معطلة'}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "task_toggled", message, {
            "user_id": user_id,
            "user_name": user_name,
            "task_name": task_name,
            "is_active": is_active
        })
    
    async def notify_task_deleted(self, bot: Bot, user_id: int, user_name: str, task_name: str):
        user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        message = f"""
🗑️ <b>تم حذف مهمة</b>

👤 <b>المستخدم:</b> {user_link} (<code>{user_id}</code>)
📰 <b>المهمة:</b> {task_name}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "task_deleted", message, {
            "user_id": user_id,
            "user_name": user_name,
            "task_name": task_name
        })
    
    async def notify_forwarding_report(self, bot: Bot, task_name: str, success_count: int, fail_count: int):
        message = f"""
📊 <b>تقرير التوجيه</b>

📰 <b>المهمة:</b> {task_name}
✅ <b>نجح:</b> {success_count}
❌ <b>فشل:</b> {fail_count}
📈 <b>النسبة:</b> {(success_count / (success_count + fail_count) * 100) if (success_count + fail_count) > 0 else 0:.1f}%
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "forwarding_report", message, {
            "task_name": task_name,
            "success_count": success_count,
            "fail_count": fail_count
        })
    
    async def notify_subscription_upgraded(self, bot: Bot, user_id: int, user_name: str, 
                                          plan: str, duration_days: int):
        user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        message = f"""
⭐ <b>ترقية اشتراك</b>

👤 <b>المستخدم:</b> {user_link} (<code>{user_id}</code>)
📋 <b>الخطة:</b> {plan}
⏰ <b>المدة:</b> {duration_days} يوم
🕐 <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "subscription_upgraded", message, {
            "user_id": user_id,
            "user_name": user_name,
            "plan": plan,
            "duration_days": duration_days
        })
    
    async def notify_subscription_expired(self, bot: Bot, user_id: int, user_name: str):
        user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        message = f"""
⏱️ <b>انتهى اشتراك</b>

👤 <b>المستخدم:</b> {user_link} (<code>{user_id}</code>)
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.notify(bot, "subscription_expired", message, {
            "user_id": user_id,
            "user_name": user_name
        })

notification_manager = NotificationManager()
