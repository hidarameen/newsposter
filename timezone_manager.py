import logging
import json
import os
from typing import Dict, List
from zoneinfo import ZoneInfo, available_timezones
from datetime import datetime
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

class TimezoneManager:
    """مدير المنطقة الزمنية للمستخدمين"""
    
    # قائمة المناطق الزمنية الشائعة
    COMMON_TIMEZONES = {
        'Asia/Riyadh': '🇸🇦 الرياض (السعودية)',
        'Asia/Dubai': '🇦🇪 دبي (الإمارات)',
        'Asia/Kuwait': '🇰🇼 الكويت',
        'Asia/Qatar': '🇶🇦 قطر',
        'Asia/Bahrain': '🇧🇭 البحرين',
        'Asia/Muscat': '🇴🇲 مسقط (عمان)',
        'Asia/Baghdad': '🇮🇶 بغداد (العراق)',
        'Asia/Amman': '🇯🇴 عمان (الأردن)',
        'Asia/Beirut': '🇱🇧 بيروت (لبنان)',
        'Asia/Damascus': '🇸🇾 دمشق (سوريا)',
        'Africa/Cairo': '🇪🇬 القاهرة (مصر)',
        'Europe/Istanbul': '🇹🇷 إسطنبول (تركيا)',
        'UTC': '🌍 توقيت عالمي منسق (UTC)',
        'Europe/London': '🇬🇧 لندن',
        'Europe/Paris': '🇫🇷 باريس',
        'America/New_York': '🇺🇸 نيويورك',
        'America/Los_Angeles': '🇺🇸 لوس أنجلوس',
        'Asia/Tokyo': '🇯🇵 طوكيو',
    }
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.timezone_file = os.path.join(self.user_dir, 'timezone.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """إنشاء ملف المنطقة الزمنية إن لم يكن موجوداً"""
        if not os.path.exists(self.timezone_file):
            default_data = {
                'timezone': 'UTC',
                'updated_at': datetime.now().isoformat()
            }
            with open(self.timezone_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
    
    def get_timezone(self) -> str:
        """
        الحصول على المنطقة الزمنية للمستخدم
        
        Returns:
            اسم المنطقة الزمنية (مثل 'Asia/Riyadh')
        """
        try:
            with open(self.timezone_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('timezone', 'UTC')
        except Exception as e:
            logger.error(f"❌ خطأ في قراءة المنطقة الزمنية: {e}")
            return 'UTC'
    
    def set_timezone(self, timezone: str) -> bool:
        """
        تعيين المنطقة الزمنية للمستخدم
        
        Args:
            timezone: اسم المنطقة الزمنية
            
        Returns:
            نجاح العملية
        """
        try:
            # التحقق من صحة المنطقة الزمنية
            ZoneInfo(timezone)
            
            data = {
                'timezone': timezone,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.timezone_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ تم تعيين المنطقة الزمنية للمستخدم {self.user_id}: {timezone}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تعيين المنطقة الزمنية: {e}")
            return False
    
    def get_current_time(self) -> datetime:
        """
        الحصول على الوقت الحالي حسب منطقة المستخدم
        
        Returns:
            كائن datetime بالمنطقة الزمنية للمستخدم
        """
        timezone = self.get_timezone()
        tz = ZoneInfo(timezone)
        return datetime.now(tz)
    
    def get_timezone_info(self) -> Dict:
        """
        الحصول على معلومات المنطقة الزمنية
        
        Returns:
            قاموس بمعلومات المنطقة الزمنية
        """
        timezone = self.get_timezone()
        current_time = self.get_current_time()
        
        return {
            'timezone': timezone,
            'timezone_display': self.COMMON_TIMEZONES.get(timezone, timezone),
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'current_hour': current_time.hour,
            'current_day': current_time.weekday(),
            'utc_offset': current_time.strftime('%z')
        }
    
    @staticmethod
    def get_common_timezones() -> Dict[str, str]:
        """الحصول على قائمة المناطق الزمنية الشائعة"""
        return TimezoneManager.COMMON_TIMEZONES.copy()
    
    @staticmethod
    def search_timezone(query: str) -> List[str]:
        """
        البحث عن منطقة زمنية
        
        Args:
            query: نص البحث
            
        Returns:
            قائمة بالمناطق الزمنية المطابقة
        """
        query = query.lower()
        results = []
        
        for tz in available_timezones():
            if query in tz.lower():
                results.append(tz)
        
        return sorted(results)[:20]  # أول 20 نتيجة
    
    @staticmethod
    def validate_timezone(timezone: str) -> bool:
        """
        التحقق من صحة منطقة زمنية
        
        Args:
            timezone: اسم المنطقة الزمنية
            
        Returns:
            True إذا كانت صالحة
        """
        try:
            ZoneInfo(timezone)
            return True
        except Exception:
            return False
