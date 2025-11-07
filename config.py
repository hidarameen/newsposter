
import os
from pathlib import Path

BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')  # إزالة / في النهاية
WEBHOOK_PATH = '/webhook'
WEB_SERVER_HOST = '0.0.0.0'
WEB_SERVER_PORT = 5000

# معالجة ADMIN_ID الفارغ أو غير الموجود
admin_id_str = os.getenv('ADMIN_ID', '0').strip()
ADMIN_ID = int(admin_id_str) if admin_id_str else 0

# مسار البيانات الموحد (يستخدم للـ Docker volume)
# في Replit نستخدم المجلد الحالي بدلاً من /app
# التأكد من استخدام مسار نسبي
data_dir_env = os.getenv('DATA_DIR', './data')
# إذا كان المسار مطلقاً، نحوله لمسار نسبي
if os.path.isabs(data_dir_env):
    DATA_DIR = './data'
else:
    DATA_DIR = data_dir_env

USERS_DATA_DIR = os.path.join(DATA_DIR, 'users_data')
ADMIN_DATA_DIR = os.path.join(DATA_DIR, 'admin_data')

# إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(USERS_DATA_DIR, exist_ok=True)
os.makedirs(ADMIN_DATA_DIR, exist_ok=True)

# مسارات ملفات المشرف
FORWARDING_TASKS_FILE = os.path.join(ADMIN_DATA_DIR, 'forwarding_tasks.json')
ADMIN_SETTINGS_FILE = os.path.join(ADMIN_DATA_DIR, 'admin_settings.json')
USERS_FILE = os.path.join(ADMIN_DATA_DIR, 'users.json')
NOTIFICATIONS_CONFIG_FILE = os.path.join(ADMIN_DATA_DIR, 'notifications_config.json')
EVENT_LOGS_FILE = os.path.join(ADMIN_DATA_DIR, 'event_logs.jsonl')
STATS_SNAPSHOT_FILE = os.path.join(ADMIN_DATA_DIR, 'stats_snapshot.json')
WELCOME_MESSAGE_FILE = os.path.join(ADMIN_DATA_DIR, 'welcome_message.json')
