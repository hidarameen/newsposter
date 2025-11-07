
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from config import USERS_DATA_DIR

class UserTask:
    def __init__(self, task_id: int, user_id: int, admin_task_id: int, admin_task_name: str, 
                 target_channel: Dict, is_active: bool = True):
        self.task_id = task_id
        self.user_id = user_id
        self.admin_task_id = admin_task_id
        self.admin_task_name = admin_task_name
        self.target_channel = target_channel
        self.is_active = is_active
        self.created_at = datetime.now().isoformat()
    
    @property
    def source_channel(self) -> Optional[Dict]:
        """الحصول على قناة المصدر من المهمة الإدارية ديناميكياً"""
        from forwarding_manager import ForwardingManager
        fm = ForwardingManager()
        admin_task = fm.get_task(self.admin_task_id)
        if admin_task and admin_task.source_channels:
            return admin_task.source_channels[0]
        return None
    
    def to_dict(self):
        return {
            'task_id': self.task_id,
            'user_id': self.user_id,
            'admin_task_id': self.admin_task_id,
            'admin_task_name': self.admin_task_name,
            'target_channel': self.target_channel,
            'is_active': self.is_active,
            'created_at': self.created_at
        }
    
    @staticmethod
    def from_dict(data: Dict):
        # دعم التوافق مع البيانات القديمة
        task = UserTask(
            task_id=data['task_id'],
            user_id=data['user_id'],
            admin_task_id=data['admin_task_id'],
            admin_task_name=data['admin_task_name'],
            target_channel=data['target_channel'],
            is_active=data.get('is_active', True)
        )
        task.created_at = data.get('created_at', datetime.now().isoformat())
        return task

class UserTaskManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.tasks_file = os.path.join(self.user_dir, 'tasks.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_tasks(self) -> Dict[int, UserTask]:
        with open(self.tasks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {int(k): UserTask.from_dict(v) for k, v in data.items()}
    
    def save_tasks(self, tasks: Dict[int, UserTask]):
        with open(self.tasks_file, 'w', encoding='utf-8') as f:
            data = {str(k): v.to_dict() for k, v in tasks.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_next_task_id(self) -> int:
        tasks = self.load_tasks()
        if not tasks:
            return 1
        return max(tasks.keys()) + 1
    
    def add_task(self, admin_task_id: int, admin_task_name: str, 
                 target_channel: Dict) -> int:
        tasks = self.load_tasks()
        task_id = self.get_next_task_id()
        
        task = UserTask(
            task_id=task_id,
            user_id=self.user_id,
            admin_task_id=admin_task_id,
            admin_task_name=admin_task_name,
            target_channel=target_channel,
            is_active=True
        )
        
        tasks[task_id] = task
        self.save_tasks(tasks)
        
        # إنشاء إعدادات افتراضية جديدة للمهمة
        from task_settings_manager import TaskSettingsManager
        TaskSettingsManager(self.user_id, task_id, force_new=True)
        
        return task_id
    
    def get_task(self, task_id: int) -> Optional[UserTask]:
        tasks = self.load_tasks()
        return tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[int, UserTask]:
        return self.load_tasks()
    
    def get_active_tasks(self) -> Dict[int, UserTask]:
        tasks = self.load_tasks()
        return {k: v for k, v in tasks.items() if v.is_active}
    
    def update_task_status(self, task_id: int, is_active: bool) -> Optional[bool]:
        """
        تحديث حالة المهمة مباشرة
        
        Args:
            task_id: معرف المهمة
            is_active: الحالة الجديدة (True = نشط, False = معطل)
            
        Returns:
            الحالة الجديدة إذا نجحت العملية، None إذا لم توجد المهمة
        """
        tasks = self.load_tasks()
        if task_id not in tasks:
            return None
        
        if tasks[task_id].is_active != is_active:
            tasks[task_id].is_active = is_active
            self.save_tasks(tasks)
        
        return tasks[task_id].is_active
    
    def toggle_task(self, task_id: int) -> Optional[bool]:
        """
        قلب حالة المهمة (نشط <-> معطل)
        
        Args:
            task_id: معرف المهمة
            
        Returns:
            الحالة الجديدة إذا نجحت العملية، None إذا لم توجد المهمة
        """
        tasks = self.load_tasks()
        if task_id not in tasks:
            return None
        
        new_status = not tasks[task_id].is_active
        return self.update_task_status(task_id, new_status)
    
    def delete_task(self, task_id: int) -> bool:
        tasks = self.load_tasks()
        if task_id in tasks:
            del tasks[task_id]
            self.save_tasks(tasks)
            return True
        return False
    
    def task_exists(self, admin_task_id: int, target_channel_id: int) -> bool:
        tasks = self.load_tasks()
        for task in tasks.values():
            if task.admin_task_id == admin_task_id and task.target_channel['id'] == target_channel_id:
                return True
        return False
