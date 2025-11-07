
"""
نظام تتبع آخر تفاعل للمستخدمين مع البوت
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from config import USERS_FILE

logger = logging.getLogger(__name__)

class UserTracker:
    """تتبع آخر تفاعل للمستخدمين مع البوت"""
    
    def __init__(self, file_path: str = None):
        if file_path is None:
            file_path = USERS_FILE
        self.file_path = Path(file_path)
        self._ensure_file()
    
    def _ensure_file(self):
        """التأكد من وجود الملف"""
        if not self.file_path.exists():
            self.file_path.write_text("{}")
    
    def load_users(self) -> dict:
        """تحميل بيانات المستخدمين"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في تحميل ملف المستخدمين: {e}")
            return {}
    
    def save_users(self, users: dict):
        """حفظ بيانات المستخدمين"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ ملف المستخدمين: {e}")
    
    def update_last_interaction(self, user_id: int, username: str | None = None, first_name: str | None = None):
        """تحديث آخر تفاعل للمستخدم"""
        # تجاهل المعرفات الوهمية/التجريبية
        if user_id in [888888, 999999] or user_id < 10000:
            logger.warning(f"⚠️ تم تجاهل معرف مستخدم تجريبي: {user_id}")
            return
            
        users = self.load_users()
        user_key = str(user_id)
        
        users[user_key] = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_interaction': datetime.now().isoformat()
        }
        
        self.save_users(users)
        logger.info(f"✅ تم تحديث آخر تفاعل للمستخدم {user_id}")
    
    def get_user_last_interaction(self, user_id: int) -> str | None:
        """الحصول على آخر تفاعل للمستخدم"""
        users = self.load_users()
        user_key = str(user_id)
        
        if user_key in users:
            return users[user_key].get('last_interaction')
        return None
    
    def get_most_recent_user(self, user_ids: list) -> int | None:
        """
        الحصول على المستخدم الذي آخر تفاعل مع البوت من قائمة معينة
        
        Args:
            user_ids: قائمة معرفات المستخدمين
            
        Returns:
            معرف المستخدم الذي آخر تفاعل أو None
        """
        users = self.load_users()
        most_recent = None
        most_recent_time = None
        
        for user_id in user_ids:
            user_key = str(user_id)
            if user_key in users:
                last_interaction = users[user_key].get('last_interaction')
                if last_interaction:
                    interaction_time = datetime.fromisoformat(last_interaction)
                    if most_recent_time is None or interaction_time > most_recent_time:
                        most_recent_time = interaction_time
                        most_recent = user_id
        
        return most_recent
    
    def is_user_tracked(self, user_id: int) -> bool:
        """التحقق من وجود المستخدم في قائمة المتتبعين"""
        users = self.load_users()
        return str(user_id) in users
