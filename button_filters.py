
from typing import Optional, Tuple
from aiogram.types import InlineKeyboardMarkup

class ButtonFilters:
    @staticmethod
    def has_inline_buttons(reply_markup) -> bool:
        if reply_markup and isinstance(reply_markup, InlineKeyboardMarkup):
            return len(reply_markup.inline_keyboard) > 0
        return False
    
    @staticmethod
    def apply_button_filter(reply_markup, mode: str) -> Tuple[bool, Optional[InlineKeyboardMarkup]]:
        has_buttons = ButtonFilters.has_inline_buttons(reply_markup)
        
        if not has_buttons:
            return True, reply_markup
        
        if mode == 'block':
            return False, None
        
        elif mode == 'remove':
            return True, None
        
        return True, reply_markup
