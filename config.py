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

# مسار البيانات الموحد (يدعم Docker وNorthflank)
# استخدم متغير البيئة DATA_DIR إن وجد، وإلا استخدم ./data
data_dir_env = os.getenv('DATA_DIR', './data')

# إذا كان المسار مطلقاً (مثل /data)، استخدمه كما هو
if os.path.isabs(data_dir_env):
    DATA_DIR = data_dir_env
else:
    # نحوله لمسار مطلق داخل المشروع
    DATA_DIR = os.path.abspath(data_dir_env)

# إنشاء المجلدات المطلوبة
USERS_DATA_DIR = os.path.join(DATA_DIR, 'users_data')
ADMIN_DATA_DIR = os.path.join(DATA_DIR, 'admin_data')

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

# فحص المسار للتأكد أثناء التشغيل (اختياري)
print(f"📂 DATA_DIR in use: {DATA_DIR}")
print(f"🔍 Exists: {os.path.exists(DATA_DIR)} | Contents: {os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else 'Not Found'}")
