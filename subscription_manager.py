
import json
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from config import USERS_DATA_DIR

class SubscriptionManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.subscription_file = os.path.join(self.user_dir, 'subscription.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self.subscription_file):
            default_data = {
                'plan': 'free',
                'start_date': None,
                'end_date': None,
                'is_trial': False,
                'trial_used': False,
                'warnings_sent': []
            }
            with open(self.subscription_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
    
    def load_subscription(self) -> Dict:
        with open(self.subscription_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_subscription(self, data: Dict):
        with open(self.subscription_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def is_premium(self) -> bool:
        sub = self.load_subscription()
        if sub['plan'] == 'free':
            return False
        
        if not sub['end_date']:
            return False
        
        end_date = datetime.fromisoformat(sub['end_date'])
        return datetime.now() < end_date
    
    def get_plan_details(self) -> Dict:
        sub = self.load_subscription()
        is_active = self.is_premium()
        
        days_remaining = 0
        if sub['end_date'] and is_active:
            end_date = datetime.fromisoformat(sub['end_date'])
            days_remaining = (end_date - datetime.now()).days
        
        return {
            'plan': sub['plan'],
            'is_active': is_active,
            'is_trial': sub.get('is_trial', False),
            'start_date': sub.get('start_date'),
            'end_date': sub.get('end_date'),
            'days_remaining': days_remaining,
            'trial_used': sub.get('trial_used', False)
        }
    
    def activate_subscription(self, plan: str, duration_days: int, is_trial: bool = False):
        sub = self.load_subscription()
        now = datetime.now()
        
        sub['plan'] = plan
        sub['start_date'] = now.isoformat()
        sub['end_date'] = (now + timedelta(days=duration_days)).isoformat()
        sub['is_trial'] = is_trial
        sub['warnings_sent'] = []
        
        if is_trial:
            sub['trial_used'] = True
        
        self.save_subscription(sub)
    
    def deactivate_premium_features(self):
        sub = self.load_subscription()
        sub['plan'] = 'free'
        sub['is_trial'] = False
        self.save_subscription(sub)
    
    def disable_active_premium_features(self):
        """تعطيل جميع المميزات المدفوعة في كل المهام"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from task_settings_manager import TaskSettingsManager
            from user_task_manager import UserTaskManager
            
            task_manager = UserTaskManager(self.user_id)
            all_tasks = task_manager.get_all_tasks()
            
            if not all_tasks:
                logger.info(f"User {self.user_id} has no tasks to disable premium features")
                return
            
            premium_features = ['header', 'footer', 'inline_buttons', 'whitelist_words', 
                              'blacklist_words', 'replacements', 'link_management', 
                              'button_filter', 'forwarded_filter', 'language_filter', 'media_filters',
                              'auto_pin', 'link_preview', 'reply_preservation', 'auto_delete',
                              'day_filter', 'hour_filter', 'translation', 'character_limit']
            
            disabled_count = 0
            # all_tasks is a Dict[int, UserTask], so iterate over keys
            for task_id in all_tasks.keys():
                try:
                    
                    settings_manager = TaskSettingsManager(self.user_id, task_id)
                    settings = settings_manager.load_settings()
                    
                    for feature in premium_features:
                        if feature in settings and isinstance(settings[feature], dict):
                            if settings[feature].get('enabled', False):
                                settings[feature]['enabled'] = False
                                disabled_count += 1
                    
                    settings_manager.save_settings(settings)
                except Exception as e:
                    logger.error(f"Error disabling features for task {task_id}: {e}")
                    continue
            
            logger.info(f"Disabled {disabled_count} premium features for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error in disable_active_premium_features for user {self.user_id}: {e}", exc_info=True)
    
    def can_use_trial(self) -> bool:
        sub = self.load_subscription()
        return not sub.get('trial_used', False)
    
    def should_send_warning(self) -> Optional[int]:
        if not self.is_premium():
            return None
        
        sub = self.load_subscription()
        end_date = datetime.fromisoformat(sub['end_date'])
        days_remaining = (end_date - datetime.now()).days
        
        warnings_sent = sub.get('warnings_sent', [])
        
        if days_remaining <= 7 and '7' not in warnings_sent:
            return 7
        elif days_remaining <= 3 and '3' not in warnings_sent:
            return 3
        elif days_remaining <= 1 and '1' not in warnings_sent:
            return 1
        
        return None
    
    def mark_warning_sent(self, warning_type: str):
        sub = self.load_subscription()
        if 'warnings_sent' not in sub:
            sub['warnings_sent'] = []
        
        if warning_type not in sub['warnings_sent']:
            sub['warnings_sent'].append(warning_type)
            self.save_subscription(sub)
    
    def get_max_tasks(self) -> int:
        if self.is_premium():
            return -1
        return 1
    
    def can_add_task(self, current_task_count: int) -> bool:
        max_tasks = self.get_max_tasks()
        if max_tasks == -1:
            return True
        return current_task_count < max_tasks

PLAN_PRICES = {
    'monthly': {'duration_days': 30, 'price': 5, 'name': 'شهري'},
    '3months': {'duration_days': 90, 'price': 13, 'name': '3 شهور'},
    '6months': {'duration_days': 180, 'price': 24, 'name': '6 شهور'},
    'yearly': {'duration_days': 365, 'price': 45, 'name': 'سنوي'}
}

PREMIUM_FEATURES = {
    'header_footer': {
        'name': 'رأس وذيل الرسالة',
        'icon': '📝',
        'description': 'أضف رأساً وذيلاً مخصصاً لجميع الرسائل مع دعم التنسيقات المختلفة'
    },
    'inline_buttons': {
        'name': 'أزرار إنلاين مخصصة',
        'icon': '🔘',
        'description': 'أضف أزراراً تفاعلية مخصصة أسفل رسائلك مع روابط وأوامر'
    },
    'link_management': {
        'name': 'إدارة الروابط',
        'icon': '🔗',
        'description': 'تحكم في الروابط داخل الرسائل - حظر أو حذف الروابط بشكل تلقائي'
    },
    'button_filter': {
        'name': 'فلتر الأزرار الشفافة',
        'icon': '🚫',
        'description': 'امنع أو احذف الأزرار الموجودة في الرسائل المنشورة'
    },
    'language_filter': {
        'name': 'فلتر اللغة المتقدم',
        'icon': '🌐',
        'description': 'فلتر الرسائل حسب اللغة مع خيارات متقدمة للتحكم'
    },
    'whitelist': {
        'name': 'القائمة البيضاء',
        'icon': '✅',
        'description': 'اسمح فقط بالرسائل التي تحتوي على كلمات محددة من اختيارك'
    },
    'blacklist': {
        'name': 'القائمة السوداء',
        'icon': '🚫',
        'description': 'احظر الرسائل التي تحتوي على كلمات محددة من اختيارك'
    },
    'replacements': {
        'name': 'استبدال النصوص',
        'icon': '🔄',
        'description': 'استبدل كلمات أو جمل معينة بنصوص أخرى تلقائياً'
    },
    'forwarded_filter': {
        'name': 'فلتر الرسائل الموجهة',
        'icon': '↪️',
        'description': 'تحكم في قبول أو رفض الرسائل المعاد توجيهها'
    },
    'media_filters': {
        'name': 'فلاتر الوسائط المتقدمة',
        'icon': '🎬',
        'description': 'حدد أنواع الوسائط المسموح بنشرها بدقة'
    },
    'auto_pin': {
        'name': 'التثبيت التلقائي',
        'icon': '📌',
        'description': 'يثبت الرسائل الجديدة في القناة الهدف تلقائياً بعد النشر مع خيار حذف إشعار التثبيت'
    },
    'link_preview': {
        'name': 'معاينة الروابط',
        'icon': '🔗',
        'description': 'التحكم في عرض أو إخفاء معاينة الروابط داخل المنشورات'
    },
    'reply_preservation': {
        'name': 'الحفاظ على الردود',
        'icon': '💬',
        'description': 'يحافظ على تسلسل الردود إذا كانت الرسالة ردًا على منشور سابق'
    },
    'auto_delete': {
        'name': 'الحذف التلقائي',
        'icon': '🗑️',
        'description': 'يحذف الرسائل في القناة الهدف بعد وقت محدد من النشر'
    },
    'day_filter': {
        'name': 'فلتر الأيام',
        'icon': '📅',
        'description': 'تحديد أيام النشر المسموح بها أو المحظورة'
    },
    'hour_filter': {
        'name': 'فلتر الساعات',
        'icon': '🕒',
        'description': 'تحديد ساعات النشر المسموح بها مع دعم النطاقات الزمنية'
    },
    'translation': {
        'name': 'ترجمة النصوص',
        'icon': '🌍',
        'description': 'ترجمة النصوص من لغة إلى أخرى أو من جميع اللغات إلى لغة محددة'
    },
    'character_limit': {
        'name': 'فلتر حدود الأحرف',
        'icon': '📏',
        'description': 'نشر أو حظر الرسائل بناءً على الحد الأدنى أو الأقصى لعدد الأحرف'
    }
}
