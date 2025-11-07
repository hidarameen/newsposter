
import logging
from aiogram import Bot
from typing import Dict, List, Tuple, Optional
from channels_tracker import channels_tracker
from user_task_manager import UserTaskManager
from forwarding_manager import ForwardingManager

logger = logging.getLogger(__name__)

def format_number(num: int) -> str:
    """تنسيق الأرقام بصيغة مختصرة (K للآلاف، M للملايين)"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)

class ChannelsChecker:
    """نظام فحص شامل للقنوات والمجموعات"""
    
    @staticmethod
    async def check_all_channels(bot: Bot) -> Dict:
        """
        فحص جميع القنوات والمجموعات
        
        Returns:
            dict مع تصنيفات مختلفة للقنوات والمجموعات
        """
        all_channels = channels_tracker.get_all_channels()
        
        result = {
            'channels': {
                'admin_with_permissions': [],
                'admin_without_post': [],
                'restricted': [],
                'removed': [],
                'not_linked_to_tasks': []
            },
            'groups': {
                'admin': [],
                'member': [],
                'restricted': [],
                'removed': [],
                'not_linked_to_tasks': []
            },
            'stats': {
                'total_channels': 0,
                'total_groups': 0,
                'total_active': 0,
                'total_restricted': 0,
                'total_removed': 0
            }
        }
        
        # الحصول على جميع المهام المرتبطة
        fm = ForwardingManager()
        admin_tasks = fm.get_all_tasks()
        linked_channel_ids = set()
        
        # جمع جميع القنوات المرتبطة بمهام
        for task in admin_tasks.values():
            for target in task.target_channels:
                linked_channel_ids.add(target['id'])
        
        logger.info(f"🔍 بدء فحص {len(all_channels)} قناة/مجموعة")
        
        for chat_id, channel_info in all_channels.items():
            chat_type = channel_info.get('type', 'unknown')
            status = channel_info.get('status', 'active')
            
            # تحديث الإحصائيات
            if chat_type == 'channel':
                result['stats']['total_channels'] += 1
            elif chat_type in ['group', 'supergroup']:
                result['stats']['total_groups'] += 1
            
            if status == 'active':
                result['stats']['total_active'] += 1
            elif status == 'restricted':
                result['stats']['total_restricted'] += 1
            elif status == 'removed':
                result['stats']['total_removed'] += 1
            
            # معالجة القنوات المحذوفة أو المقيدة بشكل خاص
            if status == 'removed':
                if chat_type == 'channel':
                    result['channels']['removed'].append(channel_info)
                else:
                    result['groups']['removed'].append(channel_info)
                continue
            
            if status == 'restricted':
                if chat_type == 'channel':
                    result['channels']['restricted'].append(channel_info)
                else:
                    result['groups']['restricted'].append(channel_info)
                continue
            
            # فحص الحالة الحالية للبوت
            try:
                bot_info = await bot.get_me()
                member = await bot.get_chat_member(chat_id, bot_info.id)
                
                channel_data = {
                    **channel_info,
                    'bot_status': member.status,
                    'can_post': getattr(member, 'can_post_messages', None),
                    'can_edit': getattr(member, 'can_edit_messages', None),
                    'is_linked': chat_id in linked_channel_ids
                }
                
                if chat_type == 'channel':
                    # تصنيف القنوات
                    if member.status in ['administrator', 'creator']:
                        can_post = getattr(member, 'can_post_messages', None)
                        if can_post or can_post is None:
                            result['channels']['admin_with_permissions'].append(channel_data)
                        else:
                            result['channels']['admin_without_post'].append(channel_data)
                        
                        # التحقق من الارتباط بالمهام
                        if chat_id not in linked_channel_ids:
                            result['channels']['not_linked_to_tasks'].append(channel_data)
                    
                elif chat_type in ['group', 'supergroup']:
                    # تصنيف المجموعات
                    if member.status in ['administrator', 'creator']:
                        result['groups']['admin'].append(channel_data)
                        
                        # التحقق من الارتباط بالمهام
                        if chat_id not in linked_channel_ids:
                            result['groups']['not_linked_to_tasks'].append(channel_data)
                    elif member.status == 'member':
                        result['groups']['member'].append(channel_data)
                    elif member.status == 'restricted':
                        result['groups']['restricted'].append(channel_data)
                    elif member.status in ['left', 'kicked']:
                        result['groups']['removed'].append(channel_data)
                        # تحديث الحالة في التتبع
                        channels_tracker.mark_as_removed(chat_id)
                
            except Exception as e:
                logger.error(f"❌ خطأ في فحص القناة {chat_id}: {e}")
                # في حالة الخطأ، نفترض أن البوت محذوف
                if chat_type == 'channel':
                    result['channels']['removed'].append({**channel_info, 'error': str(e)})
                else:
                    result['groups']['removed'].append({**channel_info, 'error': str(e)})
                channels_tracker.mark_as_removed(chat_id)
        
        logger.info(f"✅ اكتمل الفحص - القنوات: {result['stats']['total_channels']}, المجموعات: {result['stats']['total_groups']}")
        return result
    
    @staticmethod
    async def format_channel_link_with_count(bot: Bot, channel_info: Dict) -> str:
        """تنسيق رابط القناة/المجموعة كـ text link مع عدد المشتركين"""
        title = channel_info.get('title', 'غير معروف')
        chat_id = channel_info.get('id')
        username = channel_info.get('username')
        
        try:
            # الحصول على الرابط
            if username:
                # قناة عامة
                link_url = f"https://t.me/{username}"
            else:
                # قناة خاصة - محاولة الحصول على رابط دعوة
                try:
                    invite_link = await bot.export_chat_invite_link(chat_id)
                    link_url = invite_link
                except:
                    # إذا فشل، استخدم رابط افتراضي
                    chat_id_str = str(chat_id).replace('-100', '')
                    link_url = f"https://t.me/c/{chat_id_str}/1"
            
            # الحصول على عدد المشتركين
            members_text = ""
            try:
                member_count = await bot.get_chat_member_count(chat_id)
                members_text = f" ({format_number(member_count)})"
            except:
                pass
            
            return f'<a href="{link_url}">{title}</a>{members_text}'
        
        except Exception as e:
            logger.error(f"خطأ في تنسيق رابط القناة {chat_id}: {e}")
            return title
    
    @staticmethod
    def format_channel_link(channel_info: Dict) -> str:
        """تنسيق رابط القناة/المجموعة كـ text link (بدون عدد المشتركين - للتوافق مع الكود القديم)"""
        title = channel_info.get('title', 'غير معروف')
        chat_id = channel_info.get('id')
        username = channel_info.get('username')
        
        if username:
            return f'<a href="https://t.me/{username}">{title}</a>'
        else:
            # للقنوات الخاصة
            chat_id_str = str(chat_id).replace('-100', '')
            return f'<a href="https://t.me/c/{chat_id_str}/1">{title}</a>'
    
    @staticmethod
    async def generate_report(bot: Bot, check_results: Dict) -> str:
        """إنشاء تقرير مفصل لنتائج الفحص"""
        report = "📊 <b>تقرير فحص القنوات والمجموعات</b>\n\n"
        
        # الإحصائيات العامة
        stats = check_results['stats']
        report += f"📈 <b>الإحصائيات العامة:</b>\n"
        report += f"  📺 القنوات: {stats['total_channels']}\n"
        report += f"  👥 المجموعات: {stats['total_groups']}\n"
        report += f"  ✅ نشطة: {stats['total_active']}\n"
        report += f"  ⚠️ مقيدة: {stats['total_restricted']}\n"
        report += f"  ❌ محذوفة: {stats['total_removed']}\n\n"
        
        channels = check_results['channels']
        groups = check_results['groups']
        
        # القنوات
        report += "━━━━━━━━━━━━━━━━━━━━\n"
        report += "📺 <b>القنوات (Channels)</b>\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # قنوات - مشرف مع صلاحيات
        if channels['admin_with_permissions']:
            report += f"✅ <b>مشرف مع صلاحيات ({len(channels['admin_with_permissions'])}):</b>\n"
            for ch in channels['admin_with_permissions'][:10]:
                link = await ChannelsChecker.format_channel_link_with_count(bot, ch)
                linked = "🔗" if ch.get('is_linked') else ""
                report += f"  • {link} {linked}\n"
            if len(channels['admin_with_permissions']) > 10:
                report += f"  ... و {len(channels['admin_with_permissions']) - 10} أخرى\n"
            report += "\n"
        
        # قنوات - مشرف بدون صلاحية نشر
        if channels['admin_without_post']:
            report += f"⚠️ <b>مشرف بدون صلاحية نشر ({len(channels['admin_without_post'])}):</b>\n"
            for ch in channels['admin_without_post'][:10]:
                link = await ChannelsChecker.format_channel_link_with_count(bot, ch)
                report += f"  • {link}\n"
            if len(channels['admin_without_post']) > 10:
                report += f"  ... و {len(channels['admin_without_post']) - 10} أخرى\n"
            report += "\n"
        
        # قنوات - مقيدة
        if channels['restricted']:
            report += f"🚫 <b>مقيدة ({len(channels['restricted'])}):</b>\n"
            for ch in channels['restricted'][:10]:
                link = ChannelsChecker.format_channel_link(ch)
                report += f"  • {link}\n"
            if len(channels['restricted']) > 10:
                report += f"  ... و {len(channels['restricted']) - 10} أخرى\n"
            report += "\n"
        
        # قنوات - محذوفة
        if channels['removed']:
            report += f"❌ <b>محذوف البوت منها ({len(channels['removed'])}):</b>\n"
            for ch in channels['removed'][:10]:
                link = ChannelsChecker.format_channel_link(ch)
                report += f"  • {link}\n"
            if len(channels['removed']) > 10:
                report += f"  ... و {len(channels['removed']) - 10} أخرى\n"
            report += "\n"
        
        # قنوات - غير مرتبطة بمهام
        if channels['not_linked_to_tasks']:
            report += f"📌 <b>مشرف لكن غير مرتبطة بمهام ({len(channels['not_linked_to_tasks'])}):</b>\n"
            for ch in channels['not_linked_to_tasks'][:10]:
                link = await ChannelsChecker.format_channel_link_with_count(bot, ch)
                report += f"  • {link}\n"
            if len(channels['not_linked_to_tasks']) > 10:
                report += f"  ... و {len(channels['not_linked_to_tasks']) - 10} أخرى\n"
            report += "\n"
        
        # المجموعات
        report += "━━━━━━━━━━━━━━━━━━━━\n"
        report += "👥 <b>المجموعات (Groups)</b>\n"
        report += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # مجموعات - مشرف
        if groups['admin']:
            report += f"✅ <b>مشرف ({len(groups['admin'])}):</b>\n"
            for gr in groups['admin'][:10]:
                link = await ChannelsChecker.format_channel_link_with_count(bot, gr)
                linked = "🔗" if gr.get('is_linked') else ""
                report += f"  • {link} {linked}\n"
            if len(groups['admin']) > 10:
                report += f"  ... و {len(groups['admin']) - 10} أخرى\n"
            report += "\n"
        
        # مجموعات - عضو
        if groups['member']:
            report += f"👤 <b>عضو عادي ({len(groups['member'])}):</b>\n"
            for gr in groups['member'][:10]:
                link = ChannelsChecker.format_channel_link(gr)
                report += f"  • {link}\n"
            if len(groups['member']) > 10:
                report += f"  ... و {len(groups['member']) - 10} أخرى\n"
            report += "\n"
        
        # مجموعات - مقيدة
        if groups['restricted']:
            report += f"🚫 <b>مقيدة ({len(groups['restricted'])}):</b>\n"
            for gr in groups['restricted'][:10]:
                link = ChannelsChecker.format_channel_link(gr)
                report += f"  • {link}\n"
            if len(groups['restricted']) > 10:
                report += f"  ... و {len(groups['restricted']) - 10} أخرى\n"
            report += "\n"
        
        # مجموعات - محذوفة
        if groups['removed']:
            report += f"❌ <b>مطرود/خرج منها ({len(groups['removed'])}):</b>\n"
            for gr in groups['removed'][:10]:
                link = ChannelsChecker.format_channel_link(gr)
                report += f"  • {link}\n"
            if len(groups['removed']) > 10:
                report += f"  ... و {len(groups['removed']) - 10} أخرى\n"
            report += "\n"
        
        # مجموعات - غير مرتبطة بمهام
        if groups['not_linked_to_tasks']:
            report += f"📌 <b>مشرف لكن غير مرتبطة بمهام ({len(groups['not_linked_to_tasks'])}):</b>\n"
            for gr in groups['not_linked_to_tasks'][:10]:
                link = await ChannelsChecker.format_channel_link_with_count(bot, gr)
                report += f"  • {link}\n"
            if len(groups['not_linked_to_tasks']) > 10:
                report += f"  ... و {len(groups['not_linked_to_tasks']) - 10} أخرى\n"
            report += "\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━\n"
        report += "💡 <b>ملاحظة:</b> 🔗 = مرتبطة بمهمة نشطة"
        
        return report

# إنشاء instance عام
channels_checker = ChannelsChecker()
