import logging
from datetime import datetime
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class DayFilter:
    """فلتر الأيام للتحكم في أيام النشر"""
    
    # أسماء الأيام بالعربية
    DAYS_AR = {
        0: 'الاثنين',
        1: 'الثلاثاء',
        2: 'الأربعاء',
        3: 'الخميس',
        4: 'الجمعة',
        5: 'السبت',
        6: 'الأحد'
    }
    
    # أسماء الأيام بالإنجليزية
    DAYS_EN = {
        0: 'Monday',
        1: 'Tuesday',
        2: 'Wednesday',
        3: 'Thursday',
        4: 'Friday',
        5: 'Saturday',
        6: 'Sunday'
    }
    
    @staticmethod
    def check_day_allowed(settings: Dict, timezone: str = 'UTC') -> Tuple[bool, str]:
        """
        التحقق من أن اليوم الحالي مسموح به
        
        Args:
            settings: إعدادات فلتر الأيام
            timezone: المنطقة الزمنية
            
        Returns:
            (مسموح, سبب الرفض)
        """
        if not settings.get('enabled', False):
            return True, ""
        
        try:
            # الحصول على اليوم الحالي حسب المنطقة الزمنية
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            current_day = now.weekday()  # 0 = Monday, 6 = Sunday
            
            mode = settings.get('mode', 'allow')
            allowed_days = settings.get('days', [])
            
            day_name_ar = DayFilter.DAYS_AR.get(current_day, 'غير معروف')
            
            # وضع السماح: اليوم يجب أن يكون في القائمة
            if mode == 'allow':
                is_allowed = current_day in allowed_days
                
                if not is_allowed:
                    return False, f"اليوم ({day_name_ar}) غير مسموح بالنشر فيه"
                
                logger.info(f"✅ اليوم ({day_name_ar}) مسموح بالنشر")
                return True, ""
            
            # وضع الحظر: اليوم يجب ألا يكون في القائمة
            elif mode == 'block':
                is_blocked = current_day in allowed_days
                
                if is_blocked:
                    return False, f"اليوم ({day_name_ar}) محظور من النشر"
                
                logger.info(f"✅ اليوم ({day_name_ar}) غير محظور")
                return True, ""
            
            return True, ""
            
        except Exception as e:
            logger.error(f"❌ خطأ في فلتر الأيام: {e}")
            return True, ""
    
    @staticmethod
    def get_allowed_days_list(settings: Dict) -> List[str]:
        """
        الحصول على قائمة الأيام المسموحة/المحظورة
        
        Args:
            settings: إعدادات فلتر الأيام
            
        Returns:
            قائمة بأسماء الأيام
        """
        days = settings.get('days', [])
        mode = settings.get('mode', 'allow')
        
        day_names = [DayFilter.DAYS_AR.get(day, str(day)) for day in days]
        
        if mode == 'allow':
            return day_names
        else:
            # عكس القائمة للوضع block
            all_days = list(DayFilter.DAYS_AR.values())
            return [day for day in all_days if day not in day_names]
    
    @staticmethod
    def get_mode_description(mode: str) -> str:
        """الحصول على وصف الوضع"""
        modes = {
            'allow': '✅ السماح بالأيام المحددة فقط',
            'block': '🚫 حظر الأيام المحددة'
        }
        return modes.get(mode, mode)
    
    @staticmethod
    def toggle_day(settings: Dict, day: int) -> Dict:
        """
        تبديل حالة يوم معين
        
        Args:
            settings: إعدادات فلتر الأيام
            day: رقم اليوم (0-6)
            
        Returns:
            الإعدادات المحدثة
        """
        if 'days' not in settings:
            settings['days'] = []
        
        if day in settings['days']:
            settings['days'].remove(day)
        else:
            settings['days'].append(day)
        
        return settings
