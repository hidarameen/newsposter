import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

class ExportImportManager:
    """مدير التصدير والاستيراد لبيانات البوت بالكامل"""
    
    @staticmethod
    def export_all_data() -> Dict[str, Any]:
        """تصدير جميع بيانات البوت إلى قاموس"""
        logger.info("بدء عملية تصدير البيانات...")
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "version": "1.0",
            "users": {},
            "admin_tasks": {},
            "notifications_config": {},
            "stats": {}
        }
        
        # تصدير بيانات المستخدمين
        try:
            users_dir = Path(USERS_DATA_DIR)
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if not user_dir.is_dir() or not user_dir.name.isdigit():
                        continue
                    
                    user_id = user_dir.name
                    user_data = ExportImportManager._export_user_data(user_id)
                    if user_data:
                        export_data["users"][user_id] = user_data
                        
            logger.info(f"تم تصدير {len(export_data['users'])} مستخدم")
        except Exception as e:
            logger.error(f"خطأ في تصدير بيانات المستخدمين: {e}")
        
        # تصدير مهام المشرف
        try:
            from forwarding_manager import ForwardingManager
            fm = ForwardingManager()
            admin_tasks = fm.get_all_tasks()
            for task_id, task in admin_tasks.items():
                export_data["admin_tasks"][str(task_id)] = {
                    "name": task.name,
                    "source_channels": task.source_channels,
                    "target_channels": task.target_channels,
                    "is_active": task.is_active,
                    "created_at": task.created_at
                }
            logger.info(f"تم تصدير {len(export_data['admin_tasks'])} مهمة مشرف")
        except Exception as e:
            logger.error(f"خطأ في تصدير مهام المشرف: {e}")
        
        # تصدير إعدادات الإشعارات
        try:
            notif_config_file = Path("notifications_config.json")
            if notif_config_file.exists():
                with open(notif_config_file, 'r', encoding='utf-8') as f:
                    export_data["notifications_config"] = json.load(f)
            logger.info("تم تصدير إعدادات الإشعارات")
        except Exception as e:
            logger.error(f"خطأ في تصدير إعدادات الإشعارات: {e}")
        
        # تصدير الإحصائيات
        try:
            stats_file = Path("stats_snapshot.json")
            if stats_file.exists():
                with open(stats_file, 'r', encoding='utf-8') as f:
                    export_data["stats"] = json.load(f)
            logger.info("تم تصدير الإحصائيات")
        except Exception as e:
            logger.error(f"خطأ في تصدير الإحصائيات: {e}")
        
        logger.info("اكتملت عملية التصدير بنجاح")
        return export_data
    
    @staticmethod
    def _export_user_data(user_id: str) -> Dict[str, Any]:
        """تصدير بيانات مستخدم واحد"""
        try:
            user_dir = Path(USERS_DATA_DIR) / user_id
            user_data = {
                "user_info": {},
                "tasks": {},
                "channels": {},
                "subscription": {},
                "task_settings": {}
            }
            
            # بيانات المستخدم الأساسية
            data_file = user_dir / "data.json"
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    user_data["user_info"] = json.load(f)
            
            # المهام
            tasks_file = user_dir / "tasks.json"
            if tasks_file.exists():
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                    for task_id, task in tasks.items():
                        user_data["tasks"][task_id] = task
            
            # القنوات
            channels_file = user_dir / "channels.json"
            if channels_file.exists():
                with open(channels_file, 'r', encoding='utf-8') as f:
                    user_data["channels"] = json.load(f)
            
            # الاشتراك
            subscription_file = user_dir / "subscription.json"
            if subscription_file.exists():
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    user_data["subscription"] = json.load(f)
            
            # إعدادات المهام
            for settings_file in user_dir.glob("task_*_settings.json"):
                task_id = settings_file.stem.split('_')[1]
                with open(settings_file, 'r', encoding='utf-8') as f:
                    user_data["task_settings"][task_id] = json.load(f)
            
            return user_data
            
        except Exception as e:
            logger.error(f"خطأ في تصدير بيانات المستخدم {user_id}: {e}")
            return None
    
    @staticmethod
    def export_to_file(filename: str = None) -> str:
        """تصدير البيانات إلى ملف JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_export_{timestamp}.json"
        
        export_data = ExportImportManager.export_all_data()
        
        filepath = Path(filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"تم حفظ البيانات في الملف: {filepath}")
        return str(filepath)
    
    @staticmethod
    def import_from_data(import_data: Dict[str, Any], overwrite: bool = False) -> Dict[str, int]:
        """استيراد البيانات من قاموس"""
        logger.info("بدء عملية الاستيراد...")
        
        stats = {
            "users_imported": 0,
            "admin_tasks_imported": 0,
            "errors": 0
        }
        
        # استيراد بيانات المستخدمين
        if "users" in import_data:
            for user_id, user_data in import_data["users"].items():
                try:
                    if ExportImportManager._import_user_data(user_id, user_data, overwrite):
                        stats["users_imported"] += 1
                except Exception as e:
                    logger.error(f"خطأ في استيراد المستخدم {user_id}: {e}")
                    stats["errors"] += 1
        
        # استيراد مهام المشرف
        if "admin_tasks" in import_data and overwrite:
            try:
                from forwarding_manager import ForwardingManager, ForwardingTask
                
                fm = ForwardingManager()
                
                # حذف جميع المهام القديمة
                old_tasks = fm.get_all_tasks()
                for old_task_id in old_tasks.keys():
                    fm.delete_task(old_task_id)
                
                # إضافة المهام الجديدة
                new_tasks = {}
                for task_id, task_data in import_data["admin_tasks"].items():
                    task = ForwardingTask(
                        task_id=int(task_id),
                        name=task_data["name"],
                        source_channels=task_data.get("source_channels", []),
                        target_channels=task_data.get("target_channels", []),
                        is_active=task_data.get("is_active", True),
                        created_at=task_data.get("created_at", datetime.now().isoformat())
                    )
                    new_tasks[int(task_id)] = task
                
                fm.save_tasks(new_tasks)
                stats["admin_tasks_imported"] = len(new_tasks)
                logger.info(f"تم استيراد {len(new_tasks)} مهمة مشرف")
            except Exception as e:
                logger.error(f"خطأ في استيراد مهام المشرف: {e}", exc_info=True)
                stats["errors"] += 1
        
        # استيراد إعدادات الإشعارات
        if "notifications_config" in import_data and overwrite:
            try:
                notif_config_file = Path("notifications_config.json")
                with open(notif_config_file, 'w', encoding='utf-8') as f:
                    json.dump(import_data["notifications_config"], f, ensure_ascii=False, indent=2)
                logger.info("تم استيراد إعدادات الإشعارات")
            except Exception as e:
                logger.error(f"خطأ في استيراد إعدادات الإشعارات: {e}")
        
        # استيراد الإحصائيات
        if "stats" in import_data and overwrite:
            try:
                stats_file = Path("stats_snapshot.json")
                with open(stats_file, 'w', encoding='utf-8') as f:
                    json.dump(import_data["stats"], f, ensure_ascii=False, indent=2)
                logger.info("تم استيراد الإحصائيات")
            except Exception as e:
                logger.error(f"خطأ في استيراد الإحصائيات: {e}")
        
        logger.info(f"اكتملت عملية الاستيراد: {stats}")
        return stats
    
    @staticmethod
    def _import_user_data(user_id: str, user_data: Dict[str, Any], overwrite: bool = False) -> bool:
        """استيراد بيانات مستخدم واحد"""
        try:
            user_dir = Path(USERS_DATA_DIR) / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # التحقق من وجود بيانات مسبقة
            if not overwrite and (user_dir / "data.json").exists():
                logger.info(f"تخطي المستخدم {user_id} - البيانات موجودة مسبقاً")
                return False
            
            # بيانات المستخدم الأساسية
            if "user_info" in user_data:
                with open(user_dir / "data.json", 'w', encoding='utf-8') as f:
                    json.dump(user_data["user_info"], f, ensure_ascii=False, indent=2)
            
            # المهام
            if "tasks" in user_data:
                with open(user_dir / "tasks.json", 'w', encoding='utf-8') as f:
                    json.dump(user_data["tasks"], f, ensure_ascii=False, indent=2)
            
            # القنوات
            if "channels" in user_data:
                with open(user_dir / "channels.json", 'w', encoding='utf-8') as f:
                    json.dump(user_data["channels"], f, ensure_ascii=False, indent=2)
            
            # الاشتراك
            if "subscription" in user_data:
                with open(user_dir / "subscription.json", 'w', encoding='utf-8') as f:
                    json.dump(user_data["subscription"], f, ensure_ascii=False, indent=2)
            
            # إعدادات المهام - دمج مع القيم الافتراضية
            if "task_settings" in user_data:
                from task_settings_manager import TaskSettingsManager
                
                for task_id, old_settings in user_data["task_settings"].items():
                    settings_file = user_dir / f"task_{task_id}_settings.json"
                    
                    # إنشاء إعدادات افتراضية
                    default_settings = {
                        'media_filters': {
                            'enabled': False,
                            'allowed_types': ['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note', 'animation', 'sticker']
                        },
                        'header': {
                            'enabled': False,
                            'text': '',
                            'entities': []
                        },
                        'footer': {
                            'enabled': False,
                            'text': '',
                            'entities': []
                        },
                        'inline_buttons': {
                            'enabled': False,
                            'buttons': []
                        },
                        'whitelist_words': {
                            'enabled': False,
                            'words': []
                        },
                        'blacklist_words': {
                            'enabled': False,
                            'words': []
                        },
                        'replacements': {
                            'enabled': False,
                            'pairs': []
                        },
                        'link_management': {
                            'enabled': False,
                            'mode': 'block'
                        },
                        'button_filter': {
                            'enabled': False,
                            'mode': 'block'
                        },
                        'forwarded_filter': {
                            'enabled': False,
                            'mode': 'allow'
                        },
                        'language_filter': {
                            'enabled': False,
                            'mode': 'allow',
                            'languages': [],
                            'sensitivity': 'full'
                        },
                        'text_format': {
                            'enabled': False,
                            'format_type': 'normal'
                        },
                        'auto_pin': {
                            'enabled': False,
                            'disable_notification': True,
                            'delete_notification_after': 5
                        },
                        'link_preview': {
                            'enabled': False,
                            'mode': 'show'
                        },
                        'reply_preservation': {
                            'enabled': False
                        },
                        'auto_delete': {
                            'enabled': False,
                            'delay_value': 60,
                            'delay_unit': 'minutes'
                        },
                        'day_filter': {
                            'enabled': False,
                            'mode': 'allow',
                            'days': []
                        },
                        'hour_filter': {
                            'enabled': False,
                            'mode': 'allow',
                            'hours': [],
                            'start_hour': 0,
                            'end_hour': 23
                        },
                        'translation': {
                            'enabled': False,
                            'mode': 'all_to_target',
                            'source_lang': 'auto',
                            'target_lang': 'ar'
                        },
                        'character_limit': {
                            'enabled': False,
                            'mode': 'max',
                            'min_chars': 10,
                            'max_chars': 4000,
                            'exact_chars': 100,
                            'tolerance': 0
                        }
                    }
                    
                    # دمج الإعدادات القديمة مع الافتراضية
                    # القيم القديمة تُستبدل بالقيم المستوردة، والقيم الناقصة تبقى افتراضية
                    merged_settings = default_settings.copy()
                    
                    for key, value in old_settings.items():
                        if key in merged_settings:
                            # إذا كان القيمة قاموس، دمج على مستوى العمق الثاني
                            if isinstance(value, dict) and isinstance(merged_settings[key], dict):
                                merged_settings[key].update(value)
                            else:
                                merged_settings[key] = value
                    
                    logger.info(f"✅ دمج إعدادات المهمة {task_id} للمستخدم {user_id}")
                    
                    with open(settings_file, 'w', encoding='utf-8') as f:
                        json.dump(merged_settings, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"خطأ في استيراد المستخدم {user_id}: {e}")
            raise
    
    @staticmethod
    def import_from_file(filepath: str, overwrite: bool = False) -> Dict[str, int]:
        """استيراد البيانات من ملف JSON"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"الملف غير موجود: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        return ExportImportManager.import_from_data(import_data, overwrite)

export_import_manager = ExportImportManager()
