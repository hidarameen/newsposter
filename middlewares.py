

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable
from config import ADMIN_ID

class AdminPrivateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type != 'private':
                return
            
            if ADMIN_ID != 0 and event.from_user.id != ADMIN_ID:
                return
        
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type != 'private':
                await event.answer("❌ هذا الأمر يعمل فقط في المحادثات الخاصة!", show_alert=True)
                return
            
            if ADMIN_ID != 0 and event.from_user.id != ADMIN_ID:
                await event.answer("❌ غير مصرح لك!", show_alert=True)
                return
        
        return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type == 'private':
                return await handler(event, data)
        
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type == 'private':
                return await handler(event, data)
            else:
                await event.answer("❌ هذا الأمر يعمل فقط في المحادثات الخاصة!", show_alert=True)
                return
        
        return await handler(event, data)

