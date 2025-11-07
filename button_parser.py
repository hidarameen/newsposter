
from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class ButtonParser:
    @staticmethod
    def parse_buttons_from_text(text: str) -> List[List[Dict]]:
        lines = text.strip().split('\n')
        buttons = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '|' in line:
                row = []
                parts = line.split('|')
                for part in parts:
                    part = part.strip()
                    if ' - ' in part:
                        button_data = ButtonParser._parse_single_button(part)
                        if button_data:
                            row.append(button_data)
                if row:
                    buttons.append(row)
            else:
                button_data = ButtonParser._parse_single_button(line)
                if button_data:
                    buttons.append([button_data])
        
        return buttons
    
    @staticmethod
    def _parse_single_button(text: str) -> Dict:
        if ' - ' not in text:
            return None
        
        parts = text.split(' - ', 1)
        if len(parts) != 2:
            return None
        
        button_text = parts[0].strip()
        button_action = parts[1].strip()
        
        if button_action.lower() == 'facebook':
            return {
                'text': button_text,
                'type': 'share',
                'platform': 'facebook'
            }
        elif button_action.lower() == 'twitter':
            return {
                'text': button_text,
                'type': 'share',
                'platform': 'twitter'
            }
        elif button_action.lower() == 'whatsapp':
            return {
                'text': button_text,
                'type': 'share',
                'platform': 'whatsapp'
            }
        elif button_action.lower() == 'instagram':
            return {
                'text': button_text,
                'type': 'share',
                'platform': 'instagram'
            }
        elif button_action.lower() == 'telegram':
            return {
                'text': button_text,
                'type': 'share',
                'platform': 'telegram'
            }
        elif button_action.lower().startswith('popup'):
            popup_text = button_action.replace('popup', '').strip().lstrip('-').strip()
            return {
                'text': button_text,
                'type': 'popup',
                'popup_text': popup_text
            }
        else:
            return {
                'text': button_text,
                'type': 'url',
                'url': button_action
            }
    
    @staticmethod
    def buttons_to_markup(buttons: List[List[Dict]], post_url: str = None, message_text: str = None) -> InlineKeyboardMarkup:
        keyboard = []
        
        for row in buttons:
            keyboard_row = []
            for button in row:
                if button['type'] == 'url':
                    keyboard_row.append(InlineKeyboardButton(
                        text=button['text'],
                        url=button['url']
                    ))
                elif button['type'] == 'share':
                    share_url = ButtonParser._get_share_url(button['platform'], post_url or '', message_text or '')
                    keyboard_row.append(InlineKeyboardButton(
                        text=button['text'],
                        url=share_url
                    ))
                elif button['type'] == 'popup':
                    keyboard_row.append(InlineKeyboardButton(
                        text=button['text'],
                        callback_data=f"popup:{button['popup_text'][:60]}"
                    ))
            
            if keyboard_row:
                keyboard.append(keyboard_row)
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def _get_share_url(platform: str, post_url: str, message_text: str = '') -> str:
        import urllib.parse
        
        # تنظيف النص وإزالة الـ HTML tags
        clean_text = message_text.strip() if message_text else ''
        
        # تجهيز النص للمشاركة
        if clean_text and post_url:
            share_content = f"{clean_text}\n\n{post_url}"
        elif clean_text:
            share_content = clean_text
        else:
            share_content = post_url
        
        encoded_content = urllib.parse.quote(share_content)
        encoded_url = urllib.parse.quote(post_url) if post_url else ''
        
        if platform == 'facebook':
            # Facebook يفضل URL فقط في sharer
            return f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}&quote={urllib.parse.quote(clean_text)}" if clean_text else f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}"
        elif platform == 'twitter':
            # Twitter يدعم النص مع الرابط
            return f"https://twitter.com/intent/tweet?text={encoded_content}"
        elif platform == 'whatsapp':
            # WhatsApp يدعم النص مع الرابط
            return f"https://wa.me/?text={encoded_content}"
        elif platform == 'telegram':
            # Telegram يدعم النص مع الرابط
            if clean_text:
                return f"https://t.me/share/url?url={encoded_url}&text={urllib.parse.quote(clean_text)}"
            else:
                return f"https://t.me/share/url?url={encoded_url}"
        elif platform == 'instagram':
            # Instagram لا يدعم مشاركة مباشرة عبر URL
            return post_url if post_url else share_content
        
        return share_content
    
    @staticmethod
    def create_preview_markup(buttons: List[List[Dict]]) -> InlineKeyboardMarkup:
        return ButtonParser.buttons_to_markup(buttons, "https://t.me/example/123")
