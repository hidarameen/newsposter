
import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from config import ADMIN_DATA_DIR

logger = logging.getLogger(__name__)

class CustomSourceRequestManager:
    def __init__(self):
        self.requests_file = os.path.join(ADMIN_DATA_DIR, 'custom_source_requests.json')
        
    def load_requests(self) -> Dict:
        """تحميل طلبات المصادر المخصصة"""
        if os.path.exists(self.requests_file):
            try:
                with open(self.requests_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطأ في تحميل طلبات المصادر: {e}")
                return {}
        return {}
    
    def save_requests(self, requests: Dict):
        """حفظ طلبات المصادر"""
        try:
            with open(self.requests_file, 'w', encoding='utf-8') as f:
                json.dump(requests, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ طلبات المصادر: {e}")
    
    def create_request(self, user_id: int, user_name: str, source_link: str) -> str:
        """إنشاء طلب مصدر جديد"""
        requests = self.load_requests()
        
        # إنشاء معرف فريد للطلب
        request_id = f"req_{user_id}_{int(datetime.now().timestamp())}"
        
        requests[request_id] = {
            'user_id': user_id,
            'user_name': user_name,
            'source_link': source_link,
            'status': 'pending',  # pending, approved, rejected
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.save_requests(requests)
        logger.info(f"✅ تم إنشاء طلب مصدر جديد: {request_id} من المستخدم {user_id}")
        return request_id
    
    def get_request(self, request_id: str) -> Optional[Dict]:
        """الحصول على طلب محدد"""
        requests = self.load_requests()
        return requests.get(request_id)
    
    def get_user_requests(self, user_id: int) -> List[Dict]:
        """الحصول على طلبات المستخدم"""
        requests = self.load_requests()
        user_requests = []
        
        for req_id, req_data in requests.items():
            if req_data['user_id'] == user_id:
                user_requests.append({
                    'id': req_id,
                    **req_data
                })
        
        return user_requests
    
    def get_pending_requests(self) -> List[Dict]:
        """الحصول على الطلبات المعلقة"""
        requests = self.load_requests()
        pending = []
        
        for req_id, req_data in requests.items():
            if req_data['status'] == 'pending':
                pending.append({
                    'id': req_id,
                    **req_data
                })
        
        return pending
    
    def update_request_status(self, request_id: str, status: str):
        """تحديث حالة الطلب"""
        requests = self.load_requests()
        
        if request_id in requests:
            requests[request_id]['status'] = status
            requests[request_id]['updated_at'] = datetime.now().isoformat()
            self.save_requests(requests)
            logger.info(f"✅ تم تحديث حالة الطلب {request_id} إلى {status}")
    
    def delete_request(self, request_id: str):
        """حذف طلب"""
        requests = self.load_requests()
        
        if request_id in requests:
            del requests[request_id]
            self.save_requests(requests)
            logger.info(f"🗑️ تم حذف الطلب {request_id}")

# إنشاء instance عام
custom_source_manager = CustomSourceRequestManager()
