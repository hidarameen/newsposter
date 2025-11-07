
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from config import USERS_DATA_DIR

class UserChannelManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.channels_file = os.path.join(self.user_dir, 'channels.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self.channels_file):
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_channels(self) -> Dict[int, Dict]:
        with open(self.channels_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    
    def save_channels(self, channels: Dict[int, Dict]):
        with open(self.channels_file, 'w', encoding='utf-8') as f:
            data = {str(k): v for k, v in channels.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_channel(self, channel_id: int, title: str, username: Optional[str] = None, chat_type: str = 'channel') -> bool:
        channels = self.load_channels()
        
        if channel_id not in channels:
            channels[channel_id] = {
                'id': channel_id,
                'title': title,
                'username': username,
                'type': chat_type,
                'added_at': datetime.now().isoformat()
            }
            self.save_channels(channels)
            return True
        return False
    
    def get_channel(self, channel_id: int) -> Optional[Dict]:
        channels = self.load_channels()
        return channels.get(channel_id)
    
    def get_all_channels(self) -> Dict[int, Dict]:
        return self.load_channels()
    
    def remove_channel(self, channel_id: int) -> bool:
        channels = self.load_channels()
        if channel_id in channels:
            del channels[channel_id]
            self.save_channels(channels)
            return True
        return False
    
    def channel_exists(self, channel_id: int) -> bool:
        channels = self.load_channels()
        return channel_id in channels
