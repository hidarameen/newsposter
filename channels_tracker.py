
import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

class ChannelsTracker:
    """نظام تتبع شامل لجميع القنوات والمجموعات التي يُضاف إليها البوت"""
    
    def __init__(self):
        self.tracker_file = os.path.join(USERS_DATA_DIR, 'channels_tracker.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """التأكد من وجود ملف التتبع"""
        if not os.path.exists(self.tracker_file):
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_tracked_channels(self) -> Dict[int, Dict]:
        """تحميل جميع القنوات/المجموعات المتتبعة"""
        try:
            with open(self.tracker_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"خطأ في تحميل القنوات المتتبعة: {e}")
            return {}
    
    def save_tracked_channels(self, channels: Dict[int, Dict]):
        """حفظ القنوات/المجموعات المتتبعة"""
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                data = {str(k): v for k, v in channels.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ القنوات المتتبعة: {e}")
    
    def add_or_update_channel(self, chat_id: int, title: str, username: Optional[str], 
                             chat_type: str, added_by: int):
        """إضافة أو تحديث معلومات قناة/مجموعة"""
        channels = self.load_tracked_channels()
        
        if chat_id not in channels:
            # قناة/مجموعة جديدة
            channels[chat_id] = {
                'id': chat_id,
                'title': title,
                'username': username,
                'type': chat_type,
                'added_by': added_by,
                'added_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'status': 'active'  # active, restricted, removed
            }
            logger.info(f"✅ تم إضافة {chat_type} جديد: {title} (ID: {chat_id})")
        else:
            # تحديث معلومات موجودة
            channels[chat_id]['title'] = title
            channels[chat_id]['username'] = username
            channels[chat_id]['last_updated'] = datetime.now().isoformat()
            if channels[chat_id].get('status') == 'removed':
                channels[chat_id]['status'] = 'active'
            logger.info(f"🔄 تم تحديث معلومات {chat_type}: {title} (ID: {chat_id})")
        
        self.save_tracked_channels(channels)
    
    def mark_as_removed(self, chat_id: int):
        """تعليم قناة/مجموعة كمحذوفة"""
        channels = self.load_tracked_channels()
        if chat_id in channels:
            channels[chat_id]['status'] = 'removed'
            channels[chat_id]['removed_at'] = datetime.now().isoformat()
            self.save_tracked_channels(channels)
            logger.info(f"🗑️ تم تعليم القناة {chat_id} كمحذوفة")
    
    def mark_as_restricted(self, chat_id: int):
        """تعليم قناة/مجموعة كمقيدة"""
        channels = self.load_tracked_channels()
        if chat_id in channels:
            channels[chat_id]['status'] = 'restricted'
            channels[chat_id]['restricted_at'] = datetime.now().isoformat()
            self.save_tracked_channels(channels)
            logger.info(f"⚠️ تم تعليم القناة {chat_id} كمقيدة")
    
    def get_all_channels(self) -> Dict[int, Dict]:
        """الحصول على جميع القنوات والمجموعات"""
        return self.load_tracked_channels()
    
    def get_channels_by_type(self, chat_type: str) -> List[Dict]:
        """الحصول على القنوات حسب النوع (channel, group, supergroup)"""
        channels = self.load_tracked_channels()
        return [ch for ch in channels.values() if ch.get('type') == chat_type]
    
    def get_channels_by_status(self, status: str) -> List[Dict]:
        """الحصول على القنوات حسب الحالة (active, restricted, removed)"""
        channels = self.load_tracked_channels()
        return [ch for ch in channels.values() if ch.get('status') == status]

# إنشاء instance عام
channels_tracker = ChannelsTracker()
