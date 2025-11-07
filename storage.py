
import json
import os
from typing import Any, Dict
from config import USERS_DATA_DIR

class UserStorage:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.data_file = os.path.join(self.user_dir, 'data.json')
        
    def load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_data(self, data: Dict[str, Any]):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def update_data(self, key: str, value: Any):
        data = self.load_data()
        data[key] = value
        self.save_data(data)
    
    def get_data(self, key: str, default=None):
        data = self.load_data()
        return data.get(key, default)
