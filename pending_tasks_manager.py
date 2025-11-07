
import json
import os
import secrets
import string
import fcntl
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from config import USERS_DATA_DIR

# إعداد نظام السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PendingTasksManager:
    """إدارة المهام المعلقة في انتظار إضافة البوت للقناة"""
    
    def __init__(self):
        self.pending_file = os.path.join(USERS_DATA_DIR, 'pending_tasks.json')
        try:
            self._ensure_file_exists()
            logger.info("تم تهيئة مدير المهام المعلقة بنجاح")
        except Exception as e:
            logger.error(f"خطأ في تهيئة مدير المهام المعلقة: {e}")
            raise
    
    def _ensure_file_exists(self):
        """التأكد من وجود ملف المهام المعلقة"""
        try:
            os.makedirs(USERS_DATA_DIR, exist_ok=True)
            if not os.path.exists(self.pending_file):
                with open(self.pending_file, 'w', encoding='utf-8') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump({}, f)
                        logger.info("تم إنشاء ملف المهام المعلقة")
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logger.error(f"خطأ في إنشاء مجلد أو ملف المهام المعلقة: {e}")
            raise
        except Exception as e:
            logger.error(f"خطأ غير متوقع في _ensure_file_exists: {e}")
            raise
    
    def _load_pending(self) -> Dict:
        """تحميل المهام المعلقة من الملف مع قفل آمن"""
        try:
            with open(self.pending_file, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # قفل مشترك للقراءة
                try:
                    data = json.load(f)
                    return data
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except FileNotFoundError:
            logger.warning("ملف المهام المعلقة غير موجود، سيتم إنشاؤه")
            self._ensure_file_exists()
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"خطأ في تحليل JSON من ملف المهام المعلقة: {e}")
            return {}
        except Exception as e:
            logger.error(f"خطأ في تحميل المهام المعلقة: {e}")
            return {}
    
    def _save_pending(self, data: Dict):
        """حفظ المهام المعلقة في الملف مع قفل حصري"""
        try:
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # قفل حصري للكتابة
                try:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logger.error(f"خطأ في حفظ ملف المهام المعلقة: {e}")
            raise
        except Exception as e:
            logger.error(f"خطأ غير متوقع في حفظ المهام المعلقة: {e}")
            raise
    
    def generate_code(self) -> str:
        """توليد كود عشوائي من 6 أحرف كبيرة وأرقام"""
        try:
            return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        except Exception as e:
            logger.error(f"خطأ في توليد الكود: {e}")
            raise
    
    def create_pending_task(self, user_id: int, channel_id: int, admin_task_id: int, admin_task_name: str) -> Optional[str]:
        """إنشاء مهمة معلقة وإرجاع الكود"""
        try:
            pending = self._load_pending()
            
            # توليد كود فريد
            code = self.generate_code()
            max_attempts = 100
            attempts = 0
            while code in pending and attempts < max_attempts:
                code = self.generate_code()
                attempts += 1
            
            if attempts >= max_attempts:
                logger.error("فشل توليد كود فريد بعد 100 محاولة")
                return None
            
            # إنشاء المهمة المعلقة
            pending[code] = {
                'user_id': user_id,
                'channel_id': channel_id,
                'admin_task_id': admin_task_id,
                'admin_task_name': admin_task_name,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            self._save_pending(pending)
            logger.info(f"تم إنشاء مهمة معلقة: user_id={user_id}, channel_id={channel_id}, code={code}")
            return code
        except Exception as e:
            logger.error(f"خطأ في إنشاء مهمة معلقة: {e}")
            return None
    
    def get_pending_task(self, code: str) -> Optional[Dict]:
        """الحصول على مهمة معلقة بالكود"""
        try:
            pending = self._load_pending()
            task = pending.get(code)
            
            if not task:
                logger.debug(f"لم يتم العثور على مهمة معلقة بالكود: {code}")
                return None
            
            # التحقق من انتهاء الصلاحية
            expires_at = datetime.fromisoformat(task['expires_at'])
            if datetime.now() > expires_at:
                logger.info(f"انتهت صلاحية المهمة المعلقة: {code}")
                self.delete_pending_task(code)
                return None
            
            logger.debug(f"تم العثور على مهمة معلقة: {code}")
            return task
        except Exception as e:
            logger.error(f"خطأ في الحصول على مهمة معلقة: {e}")
            return None
    
    def get_pending_by_channel(self, channel_id: int, user_id: int) -> Optional[tuple]:
        """البحث عن مهمة معلقة بمعرف القناة والمستخدم"""
        try:
            pending = self._load_pending()
            
            for code, task in pending.items():
                if task['channel_id'] == channel_id and task['user_id'] == user_id:
                    expires_at = datetime.fromisoformat(task['expires_at'])
                    if datetime.now() <= expires_at:
                        logger.debug(f"تم العثور على مهمة معلقة للقناة {channel_id} والمستخدم {user_id}")
                        return code, task
                    else:
                        logger.info(f"انتهت صلاحية المهمة المعلقة للقناة {channel_id}")
                        self.delete_pending_task(code)
            
            logger.debug(f"لم يتم العثور على مهمة معلقة للقناة {channel_id} والمستخدم {user_id}")
            return None
        except Exception as e:
            logger.error(f"خطأ في البحث عن مهمة معلقة بالقناة: {e}")
            return None
    
    def get_user_pending_tasks(self, user_id: int) -> List[Dict]:
        """الحصول على جميع المهام المعلقة لمستخدم معين"""
        try:
            pending = self._load_pending()
            now = datetime.now()
            user_tasks = []
            expired_codes = []
            
            for code, task in pending.items():
                if task['user_id'] == user_id:
                    expires_at = datetime.fromisoformat(task['expires_at'])
                    if now <= expires_at:
                        # إضافة الكود للمهمة
                        task_with_code = task.copy()
                        task_with_code['code'] = code
                        user_tasks.append(task_with_code)
                    else:
                        expired_codes.append(code)
            
            # حذف المهام المنتهية الصلاحية
            if expired_codes:
                for code in expired_codes:
                    self.delete_pending_task(code)
                logger.info(f"تم حذف {len(expired_codes)} مهمة منتهية الصلاحية للمستخدم {user_id}")
            
            logger.info(f"تم العثور على {len(user_tasks)} مهمة معلقة للمستخدم {user_id}")
            return user_tasks
        except Exception as e:
            logger.error(f"خطأ في الحصول على مهام المستخدم المعلقة: {e}")
            return []
    
    def cleanup_expired_tasks(self) -> int:
        """تنظيف جميع المهام المنتهية الصلاحية"""
        try:
            pending = self._load_pending()
            now = datetime.now()
            expired_codes = []
            
            for code, task in pending.items():
                expires_at = datetime.fromisoformat(task['expires_at'])
                if now > expires_at:
                    expired_codes.append(code)
            
            for code in expired_codes:
                del pending[code]
            
            if expired_codes:
                self._save_pending(pending)
                logger.info(f"🧹 تم تنظيف {len(expired_codes)} مهمة منتهية الصلاحية")
            
            return len(expired_codes)
        except Exception as e:
            logger.error(f"خطأ في تنظيف المهام المنتهية: {e}")
            return 0
    
    def count_user_pending(self, user_id: int) -> int:
        """حساب عدد المهام المعلقة لمستخدم معين"""
        try:
            pending = self._load_pending()
            now = datetime.now()
            count = 0
            expired_codes = []
            
            for code, task in pending.items():
                if task['user_id'] == user_id:
                    expires_at = datetime.fromisoformat(task['expires_at'])
                    if now <= expires_at:
                        count += 1
                    else:
                        expired_codes.append(code)
            
            # حذف المهام المنتهية الصلاحية
            if expired_codes:
                for code in expired_codes:
                    self.delete_pending_task(code)
            
            logger.debug(f"عدد المهام المعلقة للمستخدم {user_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"خطأ في حساب مهام المستخدم المعلقة: {e}")
            return 0
    
    def delete_pending_task(self, code: str) -> bool:
        """حذف مهمة معلقة"""
        try:
            pending = self._load_pending()
            if code in pending:
                del pending[code]
                self._save_pending(pending)
                logger.info(f"تم حذف المهمة المعلقة: {code}")
                return True
            else:
                logger.warning(f"محاولة حذف مهمة معلقة غير موجودة: {code}")
                return False
        except Exception as e:
            logger.error(f"خطأ في حذف مهمة معلقة: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """تنظيف المهام المنتهية الصلاحية"""
        try:
            pending = self._load_pending()
            now = datetime.now()
            
            expired_codes = []
            for code, task in pending.items():
                try:
                    expires_at = datetime.fromisoformat(task['expires_at'])
                    if now > expires_at:
                        expired_codes.append(code)
                except (KeyError, ValueError) as e:
                    logger.warning(f"مهمة معلقة بدون تاريخ صلاحية صحيح: {code} - {e}")
                    expired_codes.append(code)
            
            for code in expired_codes:
                del pending[code]
            
            if expired_codes:
                self._save_pending(pending)
                logger.info(f"تم تنظيف {len(expired_codes)} مهمة منتهية الصلاحية")
            
            return len(expired_codes)
        except Exception as e:
            logger.error(f"خطأ في تنظيف المهام المنتهية: {e}")
            return 0
