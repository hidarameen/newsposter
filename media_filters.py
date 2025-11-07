
from typing import Optional
from aiogram.types import Message

class MediaFilters:
    @staticmethod
    def get_message_media_type(message: Message) -> Optional[str]:
        if message.photo:
            return 'photo'
        elif message.video:
            return 'video'
        elif message.document:
            return 'document'
        elif message.audio:
            return 'audio'
        elif message.voice:
            return 'voice'
        elif message.video_note:
            return 'video_note'
        elif message.animation:
            return 'animation'
        elif message.sticker:
            return 'sticker'
        elif message.text:
            return 'text'
        return None
    
    @staticmethod
    def is_media_allowed(message: Message, allowed_types: list) -> bool:
        media_type = MediaFilters.get_message_media_type(message)
        
        if media_type is None:
            return True
        
        return media_type in allowed_types
