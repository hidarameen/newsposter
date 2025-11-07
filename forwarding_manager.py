
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from config import FORWARDING_TASKS_FILE

@dataclass
class ForwardingTask:
    task_id: int
    name: str
    source_channels: List[Dict]  # [{"id": -100..., "title": "..."}]
    target_channels: List[Dict]  # [{"id": -100..., "title": "..."}]
    is_active: bool
    created_at: str
    
class ForwardingManager:
    def __init__(self):
        self.tasks_file = FORWARDING_TASKS_FILE
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_tasks(self) -> Dict[int, ForwardingTask]:
        # التأكد من وجود الملف قبل القراءة
        if not os.path.exists(self.tasks_file):
            self._ensure_file_exists()
        
        with open(self.tasks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                int(k): ForwardingTask(**v) 
                for k, v in data.items()
            }
    
    def save_tasks(self, tasks: Dict[int, ForwardingTask]):
        with open(self.tasks_file, 'w', encoding='utf-8') as f:
            data = {str(k): asdict(v) for k, v in tasks.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_next_task_id(self) -> int:
        tasks = self.load_tasks()
        if not tasks:
            return 1
        return max(tasks.keys()) + 1
    
    def add_task(self, name: str, source_channels: List[Dict], target_channels: List[Dict]) -> int:
        tasks = self.load_tasks()
        task_id = self.get_next_task_id()
        
        task = ForwardingTask(
            task_id=task_id,
            name=name,
            source_channels=source_channels,
            target_channels=target_channels,
            is_active=True,
            created_at=datetime.now().isoformat()
        )
        
        tasks[task_id] = task
        self.save_tasks(tasks)
        return task_id
    
    def get_task(self, task_id: int) -> Optional[ForwardingTask]:
        tasks = self.load_tasks()
        return tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[int, ForwardingTask]:
        return self.load_tasks()
    
    def toggle_task(self, task_id: int) -> bool:
        tasks = self.load_tasks()
        if task_id in tasks:
            tasks[task_id].is_active = not tasks[task_id].is_active
            self.save_tasks(tasks)
            return tasks[task_id].is_active
        return False
    
    def delete_task(self, task_id: int) -> bool:
        tasks = self.load_tasks()
        if task_id in tasks:
            del tasks[task_id]
            self.save_tasks(tasks)
            return True
        return False
    
    def get_active_tasks(self) -> Dict[int, ForwardingTask]:
        tasks = self.load_tasks()
        return {k: v for k, v in tasks.items() if v.is_active}
