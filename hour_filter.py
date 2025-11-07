import logging
from datetime import datetime
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class HourFilter:
    """فلتر الساعات للتحكم في ساعات النشر"""
    
    @staticmethod
    def check_hour_allowed(settings: Dict, timezone: str = 'UTC') -> Tuple[bool, str]:
        """
        التحقق من أن الساعة الحالية مسموحة
        
        Args:
            settings: إعدادات فلتر الساعات
            timezone: المنطقة الزمنية
            
        Returns:
            (مسموح, سبب الرفض)
        """
        if not settings.get('enabled', False):
            return True, ""
        
        try:
            # الحصول على الساعة الحالية حسب المنطقة الزمنية
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            current_hour = now.hour  # 0-23
            
            mode = settings.get('mode', 'allow')
            allowed_hours = settings.get('hours', [])
            
            # وضع السماح: الساعة يجب أن تكون في القائمة
            if mode == 'allow':
                is_allowed = current_hour in allowed_hours
                
                if not is_allowed:
                    return False, f"الساعة الحالية ({current_hour}:00) غير مسموح بالنشر فيها"
                
                logger.info(f"✅ الساعة ({current_hour}:00) مسموحة للنشر")
                return True, ""
            
            # وضع الحظر: الساعة يجب ألا تكون في القائمة
            elif mode == 'block':
                is_blocked = current_hour in allowed_hours
                
                if is_blocked:
                    return False, f"الساعة الحالية ({current_hour}:00) محظورة من النشر"
                
                logger.info(f"✅ الساعة ({current_hour}:00) غير محظورة")
                return True, ""
            
            # وضع النطاق الزمني
            elif mode == 'range':
                start_hour = settings.get('start_hour', 0)
                end_hour = settings.get('end_hour', 23)
                
                # التعامل مع النطاق الذي يمر بمنتصف الليل
                if start_hour <= end_hour:
                    is_allowed = start_hour <= current_hour <= end_hour
                else:
                    is_allowed = current_hour >= start_hour or current_hour <= end_hour
                
                if not is_allowed:
                    return False, f"الساعة الحالية ({current_hour}:00) خارج النطاق المسموح ({start_hour}:00 - {end_hour}:00)"
                
                logger.info(f"✅ الساعة ({current_hour}:00) ضمن النطاق المسموح")
                return True, ""
            
            return True, ""
            
        except Exception as e:
            logger.error(f"❌ خطأ في فلتر الساعات: {e}")
            return True, ""
    
    @staticmethod
    def get_allowed_hours_display(settings: Dict) -> str:
        """
        الحصول على نص يعرض الساعات المسموحة
        
        Args:
            settings: إعدادات فلتر الساعات
            
        Returns:
            نص وصفي
        """
        mode = settings.get('mode', 'allow')
        
        if mode == 'range':
            start = settings.get('start_hour', 0)
            end = settings.get('end_hour', 23)
            return f"من {start}:00 إلى {end}:00"
        
        hours = settings.get('hours', [])
        if not hours:
            return "لا توجد ساعات محددة"
        
        # ترتيب الساعات
        sorted_hours = sorted(hours)
        
        # تجميع الساعات المتتالية
        ranges = []
        start = sorted_hours[0]
        end = sorted_hours[0]
        
        for hour in sorted_hours[1:]:
            if hour == end + 1:
                end = hour
            else:
                if start == end:
                    ranges.append(f"{start}:00")
                else:
                    ranges.append(f"{start}:00-{end}:00")
                start = hour
                end = hour
        
        # إضافة آخر نطاق
        if start == end:
            ranges.append(f"{start}:00")
        else:
            ranges.append(f"{start}:00-{end}:00")
        
        prefix = "السماح:" if mode == 'allow' else "الحظر:"
        return f"{prefix} {', '.join(ranges)}"
    
    @staticmethod
    def get_mode_description(mode: str) -> str:
        """الحصول على وصف الوضع"""
        modes = {
            'allow': '✅ السماح بالساعات المحددة فقط',
            'block': '🚫 حظر الساعات المحددة',
            'range': '⏰ نطاق زمني محدد'
        }
        return modes.get(mode, mode)
    
    @staticmethod
    def toggle_hour(settings: Dict, hour: int) -> Dict:
        """
        تبديل حالة ساعة معينة
        
        Args:
            settings: إعدادات فلتر الساعات
            hour: رقم الساعة (0-23)
            
        Returns:
            الإعدادات المحدثة
        """
        if 'hours' not in settings:
            settings['hours'] = []
        
        if hour in settings['hours']:
            settings['hours'].remove(hour)
        else:
            settings['hours'].append(hour)
        
        return settings
    
    @staticmethod
    def set_time_range(settings: Dict, start_hour: int, end_hour: int) -> Dict:
        """
        تعيين نطاق زمني
        
        Args:
            settings: إعدادات فلتر الساعات
            start_hour: ساعة البداية (0-23)
            end_hour: ساعة النهاية (0-23)
            
        Returns:
            الإعدادات المحدثة
        """
        settings['mode'] = 'range'
        settings['start_hour'] = max(0, min(23, start_hour))
        settings['end_hour'] = max(0, min(23, end_hour))
        
        return settings
