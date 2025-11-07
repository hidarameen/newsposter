import logging
import json
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

class TaskStatistics:
    """إحصائيات مهمة التوجيه"""
    
    def __init__(self, user_id: int, task_id: int):
        self.user_id = user_id
        self.task_id = task_id
        self.user_dir = os.path.join(USERS_DATA_DIR, str(user_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.stats_file = os.path.join(self.user_dir, f'task_{task_id}_stats.json')
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """إنشاء ملف الإحصائيات إن لم يكن موجوداً"""
        if not os.path.exists(self.stats_file):
            default_stats = {
                'total_messages': 0,
                'successful_forwards': 0,
                'failed_forwards': 0,
                'filtered_messages': 0,
                'total_characters': 0,
                'media_types': {
                    'text': 0,
                    'photo': 0,
                    'video': 0,
                    'document': 0,
                    'audio': 0,
                    'voice': 0,
                    'video_note': 0,
                    'animation': 0,
                    'sticker': 0
                },
                'filter_blocks': {
                    'media_filter': 0,
                    'whitelist': 0,
                    'blacklist': 0,
                    'link_filter': 0,
                    'button_filter': 0,
                    'forwarded_filter': 0,
                    'language_filter': 0,
                    'day_filter': 0,
                    'hour_filter': 0,
                    'character_limit': 0
                },
                'translations': 0,
                'auto_pins': 0,
                'auto_deletes': 0,
                'preserved_replies': 0,
                'first_message_date': None,
                'last_message_date': None,
                'created_at': datetime.now().isoformat()
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(default_stats, f, ensure_ascii=False, indent=2)
    
    def load_stats(self) -> Dict:
        """تحميل الإحصائيات"""
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الإحصائيات: {e}")
            self._ensure_file_exists()
            return self.load_stats()
    
    def save_stats(self, stats: Dict):
        """حفظ الإحصائيات"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الإحصائيات: {e}")
    
    def increment_total_messages(self):
        """زيادة عداد إجمالي الرسائل"""
        stats = self.load_stats()
        stats['total_messages'] += 1
        
        # تحديث تاريخ أول وآخر رسالة
        now = datetime.now().isoformat()
        if not stats.get('first_message_date'):
            stats['first_message_date'] = now
        stats['last_message_date'] = now
        
        self.save_stats(stats)
    
    def increment_successful_forward(self, media_type: str = 'text', text_length: int = 0):
        """
        زيادة عداد التوجيه الناجح
        
        Args:
            media_type: نوع الوسائط
            text_length: طول النص
        """
        stats = self.load_stats()
        stats['successful_forwards'] += 1
        stats['total_characters'] += text_length
        
        if media_type in stats['media_types']:
            stats['media_types'][media_type] += 1
        
        self.save_stats(stats)
    
    def increment_failed_forward(self):
        """زيادة عداد التوجيه الفاشل"""
        stats = self.load_stats()
        stats['failed_forwards'] += 1
        self.save_stats(stats)
    
    def increment_filtered_message(self, filter_name: str):
        """
        زيادة عداد الرسائل المفلترة
        
        Args:
            filter_name: اسم الفلتر الذي حظر الرسالة
        """
        stats = self.load_stats()
        stats['filtered_messages'] += 1
        
        if filter_name in stats['filter_blocks']:
            stats['filter_blocks'][filter_name] += 1
        
        self.save_stats(stats)
    
    def increment_translation(self):
        """زيادة عداد الترجمات"""
        stats = self.load_stats()
        stats['translations'] += 1
        self.save_stats(stats)
    
    def increment_auto_pin(self):
        """زيادة عداد التثبيت التلقائي"""
        stats = self.load_stats()
        stats['auto_pins'] += 1
        self.save_stats(stats)
    
    def increment_auto_delete(self):
        """زيادة عداد الحذف التلقائي"""
        stats = self.load_stats()
        stats['auto_deletes'] += 1
        self.save_stats(stats)
    
    def increment_preserved_reply(self):
        """زيادة عداد الردود المحفوظة"""
        stats = self.load_stats()
        stats['preserved_replies'] += 1
        self.save_stats(stats)
    
    def get_summary(self) -> Dict:
        """الحصول على ملخص الإحصائيات"""
        stats = self.load_stats()
        
        # حساب نسبة النجاح
        total_attempts = stats['successful_forwards'] + stats['failed_forwards']
        success_rate = (
            (stats['successful_forwards'] / total_attempts * 100)
            if total_attempts > 0 else 0
        )
        
        # حساب متوسط طول الرسائل
        avg_chars = (
            stats['total_characters'] / stats['successful_forwards']
            if stats['successful_forwards'] > 0 else 0
        )
        
        return {
            'total_messages': stats['total_messages'],
            'successful_forwards': stats['successful_forwards'],
            'failed_forwards': stats['failed_forwards'],
            'filtered_messages': stats['filtered_messages'],
            'success_rate': round(success_rate, 2),
            'avg_characters': round(avg_chars, 2),
            'translations': stats['translations'],
            'auto_pins': stats['auto_pins'],
            'auto_deletes': stats['auto_deletes'],
            'preserved_replies': stats['preserved_replies'],
            'first_message_date': stats.get('first_message_date'),
            'last_message_date': stats.get('last_message_date')
        }
    
    def get_formatted_summary(self) -> str:
        """الحصول على ملخص منسق للإحصائيات"""
        summary = self.get_summary()
        stats = self.load_stats()
        
        text = "📊 <b>إحصائيات المهمة</b>\n\n"
        
        text += f"📨 إجمالي الرسائل: {summary['total_messages']}\n"
        text += f"✅ توجيه ناجح: {summary['successful_forwards']}\n"
        text += f"❌ توجيه فاشل: {summary['failed_forwards']}\n"
        text += f"🚫 رسائل مفلترة: {summary['filtered_messages']}\n"
        text += f"📈 نسبة النجاح: {summary['success_rate']}%\n\n"
        
        if summary['translations'] > 0:
            text += f"🌍 ترجمات: {summary['translations']}\n"
        if summary['auto_pins'] > 0:
            text += f"📌 تثبيت تلقائي: {summary['auto_pins']}\n"
        if summary['auto_deletes'] > 0:
            text += f"🗑️ حذف تلقائي: {summary['auto_deletes']}\n"
        if summary['preserved_replies'] > 0:
            text += f"💬 ردود محفوظة: {summary['preserved_replies']}\n"
        
        # أنواع الوسائط
        text += "\n📁 <b>أنواع الوسائط:</b>\n"
        media_types = stats['media_types']
        type_names = {
            'text': '📝 نص',
            'photo': '🖼️ صور',
            'video': '🎥 فيديو',
            'document': '📄 مستندات',
            'audio': '🎵 صوت',
            'voice': '🎤 تسجيل',
            'video_note': '⭕ فيديو دائري',
            'animation': '🎞️ GIF',
            'sticker': '🎭 ملصقات'
        }
        
        for media_type, count in media_types.items():
            if count > 0:
                name = type_names.get(media_type, media_type)
                text += f"  {name}: {count}\n"
        
        # الفلاتر النشطة
        filter_blocks = stats['filter_blocks']
        total_blocks = sum(filter_blocks.values())
        
        if total_blocks > 0:
            text += "\n🚫 <b>الحظر بالفلاتر:</b>\n"
            filter_names = {
                'media_filter': 'فلتر الوسائط',
                'whitelist': 'القائمة البيضاء',
                'blacklist': 'القائمة السوداء',
                'link_filter': 'فلتر الروابط',
                'button_filter': 'فلتر الأزرار',
                'forwarded_filter': 'فلتر المُعاد توجيهها',
                'language_filter': 'فلتر اللغة',
                'day_filter': 'فلتر الأيام',
                'hour_filter': 'فلتر الساعات',
                'character_limit': 'حدود الأحرف'
            }
            
            for filter_name, count in filter_blocks.items():
                if count > 0:
                    name = filter_names.get(filter_name, filter_name)
                    text += f"  • {name}: {count}\n"
        
        # التواريخ
        if summary.get('first_message_date'):
            first_date = datetime.fromisoformat(summary['first_message_date'])
            text += f"\n📅 أول رسالة: {first_date.strftime('%Y-%m-%d %H:%M')}\n"
        
        if summary.get('last_message_date'):
            last_date = datetime.fromisoformat(summary['last_message_date'])
            text += f"📅 آخر رسالة: {last_date.strftime('%Y-%m-%d %H:%M')}\n"
        
        return text
    
    def reset_stats(self):
        """إعادة تعيين الإحصائيات"""
        if os.path.exists(self.stats_file):
            os.remove(self.stats_file)
        self._ensure_file_exists()
        logger.info(f"🔄 تم إعادة تعيين إحصائيات المهمة {self.task_id}")
