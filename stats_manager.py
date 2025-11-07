import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from config import STATS_SNAPSHOT_FILE

logger = logging.getLogger(__name__)

class StatsManager:
    def __init__(self):
        self.stats_file = Path(STATS_SNAPSHOT_FILE)
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict:
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطأ في تحميل الإحصائيات: {e}")
        
        return {
            "total_users": 0,
            "total_tasks": 0,
            "active_tasks": 0,
            "inactive_tasks": 0,
            "premium_users": 0,
            "free_users": 0,
            "total_channels": 0,
            "total_subscribers": 0,
            "last_updated": None
        }
    
    def _save_stats(self):
        try:
            self.stats["last_updated"] = datetime.now().isoformat()
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ الإحصائيات: {e}")
    
    def increment_users(self, count: int = 1):
        self.stats["total_users"] += count
        self._save_stats()
    
    def increment_tasks(self, is_active: bool = True):
        self.stats["total_tasks"] += 1
        if is_active:
            self.stats["active_tasks"] += 1
        else:
            self.stats["inactive_tasks"] += 1
        self._save_stats()
    
    def decrement_tasks(self, was_active: bool):
        self.stats["total_tasks"] = max(0, self.stats["total_tasks"] - 1)
        if was_active:
            self.stats["active_tasks"] = max(0, self.stats["active_tasks"] - 1)
        else:
            self.stats["inactive_tasks"] = max(0, self.stats["inactive_tasks"] - 1)
        self._save_stats()
    
    def toggle_task(self, was_active: bool, now_active: bool):
        if was_active and not now_active:
            self.stats["active_tasks"] = max(0, self.stats["active_tasks"] - 1)
            self.stats["inactive_tasks"] += 1
        elif not was_active and now_active:
            self.stats["inactive_tasks"] = max(0, self.stats["inactive_tasks"] - 1)
            self.stats["active_tasks"] += 1
        self._save_stats()
    
    def update_premium_count(self, premium_count: int, free_count: int):
        self.stats["premium_users"] = premium_count
        self.stats["free_users"] = free_count
        self._save_stats()
    
    def update_channel_stats(self, channel_count: int, subscriber_count: int):
        self.stats["total_channels"] = channel_count
        self.stats["total_subscribers"] = subscriber_count
        self._save_stats()
    
    def get_stats(self) -> Dict:
        return self.stats.copy()
    
    def recompute_all_stats(self):
        from pathlib import Path
        from user_task_manager import UserTaskManager
        from subscription_manager import SubscriptionManager
        
        users_dir = Path("users_data")
        if not users_dir.exists():
            logger.warning("مجلد المستخدمين غير موجود")
            return
        
        total_users = 0
        total_tasks = 0
        active_tasks = 0
        inactive_tasks = 0
        premium_users = 0
        free_users = 0
        
        all_channels = set()
        total_subscribers = 0
        
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            try:
                user_id = int(user_dir.name)
                total_users += 1
                
                sub_manager = SubscriptionManager(user_id)
                if sub_manager.is_premium():
                    premium_users += 1
                else:
                    free_users += 1
                
                task_manager = UserTaskManager(user_id)
                tasks = task_manager.get_all_tasks()
                
                total_tasks += len(tasks)
                for task in tasks.values():
                    if task.is_active:
                        active_tasks += 1
                    else:
                        inactive_tasks += 1
                    
                    if task.target_channel:
                        all_channels.add(task.target_channel.get('id'))
                
            except Exception as e:
                logger.error(f"خطأ في معالجة المستخدم {user_dir.name}: {e}")
                continue
        
        self.stats = {
            "total_users": total_users,
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "inactive_tasks": inactive_tasks,
            "premium_users": premium_users,
            "free_users": free_users,
            "total_channels": len(all_channels),
            "total_subscribers": total_subscribers,
            "last_updated": datetime.now().isoformat()
        }
        self._save_stats()
        logger.info("تم إعادة حساب جميع الإحصائيات")
    
    def get_admin_task_stats(self, admin_tasks: Dict) -> Dict:
        from user_task_manager import UserTaskManager
        from pathlib import Path
        
        task_stats = {}
        
        for admin_task_id, admin_task in admin_tasks.items():
            # التعامل مع ForwardingTask كـ dataclass
            task_name = admin_task.name if hasattr(admin_task, 'name') else admin_task.get('name', 'غير محدد')
            
            # الحصول على اسم القناة المصدر
            source_channel_name = "غير محدد"
            if hasattr(admin_task, 'source_channels'):
                if admin_task.source_channels and len(admin_task.source_channels) > 0:
                    source_channel_name = admin_task.source_channels[0].get('title', 'غير محدد')
            elif isinstance(admin_task, dict) and 'source_channel' in admin_task:
                source_channel_name = admin_task.get('source_channel', {}).get('title', 'غير محدد')
            
            task_stats[admin_task_id] = {
                "task_name": task_name,
                "source_channel": source_channel_name,
                "active_targets": 0,
                "inactive_targets": 0,
                "total_targets": 0,
                "total_subscribers": 0
            }
        
        users_dir = Path("users_data")
        if not users_dir.exists():
            return task_stats
        
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            try:
                user_id = int(user_dir.name)
                task_manager = UserTaskManager(user_id)
                tasks = task_manager.get_all_tasks()
                
                for task in tasks.values():
                    admin_task_id = task.admin_task_id
                    if admin_task_id in task_stats:
                        task_stats[admin_task_id]["total_targets"] += 1
                        if task.is_active:
                            task_stats[admin_task_id]["active_targets"] += 1
                        else:
                            task_stats[admin_task_id]["inactive_targets"] += 1
                
            except Exception as e:
                logger.error(f"خطأ في معالجة المستخدم {user_dir.name}: {e}")
                continue
        
        return task_stats
    
    def get_user_stats(self, user_id: int) -> Dict:
        from user_task_manager import UserTaskManager
        from subscription_manager import SubscriptionManager
        
        try:
            task_manager = UserTaskManager(user_id)
            tasks = task_manager.get_all_tasks()
            
            sub_manager = SubscriptionManager(user_id)
            
            active_tasks = sum(1 for t in tasks.values() if t.is_active)
            inactive_tasks = len(tasks) - active_tasks
            
            plan_details = sub_manager.get_plan_details()
            return {
                "total_tasks": len(tasks),
                "active_tasks": active_tasks,
                "inactive_tasks": inactive_tasks,
                "is_premium": sub_manager.is_premium(),
                "subscription_expires": plan_details.get('end_date')
            }
        except Exception as e:
            logger.error(f"خطأ في الحصول على إحصائيات المستخدم {user_id}: {e}")
            return {
                "total_tasks": 0,
                "active_tasks": 0,
                "inactive_tasks": 0,
                "is_premium": False,
                "subscription_expires": None
            }

stats_manager = StatsManager()
