"""
Middleware لتتبع تفاعل المستخدمين مع البوت
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from user_tracker import UserTracker

logger = logging.getLogger(__name__)

class UserInteractionMiddleware(BaseMiddleware):
    """تتبع آخر تفاعل للمستخدمين مع البوت"""
    
    def __init__(self):
        self.tracker = UserTracker()
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """معالجة الرسالة أو الاستعلام وتحديث آخر تفاعل"""
        
        # الحصول على معلومات المستخدم
        user = getattr(event, 'from_user', None)
        
        # تحديث آخر تفاعل
        if user and not user.is_bot:
            self.tracker.update_last_interaction(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name
            )
        
        # متابعة المعالجة
        return await handler(event, data)
