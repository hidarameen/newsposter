
import logging
import re
from typing import Optional, Dict, Tuple
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

class ChannelVerification:
    """التحقق من القنوات والصلاحيات"""
    
    @staticmethod
    def is_invite_link(channel_input: str) -> bool:
        """
        التحقق من كون الرابط هو رابط دعوة خاص
        
        Args:
            channel_input: الرابط أو المدخل المراد التحقق منه
            
        Returns:
            True إذا كان رابط دعوة خاص، False بخلاف ذلك
        """
        channel_input = channel_input.strip()
        
        # أنماط روابط الدعوة الخاصة
        invite_patterns = [
            r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/\+([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/joinchat/([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in invite_patterns:
            if re.match(pattern, channel_input):
                logger.info(f"تم اكتشاف رابط دعوة خاص: {channel_input[:50]}...")
                return True
        
        return False
    
    @staticmethod
    async def extract_channel_id(bot: Bot, channel_input: str) -> Optional[int]:
        """
        استخراج معرف القناة من مختلف أنواع الروابط أو username
        
        يدعم الأشكال التالية:
        - معرف رقمي مباشر: -1001234567890
        - username: @channelname أو channelname
        - رابط عام: t.me/channelname
        - رابط خاص: t.me/c/1234567890/123
        - روابط telegram.me و telegram.dog
        
        Args:
            bot: كائن البوت
            channel_input: المدخل (رابط أو username أو معرف)
            
        Returns:
            معرف القناة (int) أو None إذا فشل الاستخراج
        """
        logger.info(f"بدء استخراج معرف القناة من المدخل: {channel_input[:100]}")
        
        channel_input = channel_input.strip()
        
        # 1. التحقق من روابط الدعوة الخاصة أولاً
        if ChannelVerification.is_invite_link(channel_input):
            logger.warning(f"المدخل هو رابط دعوة خاص ولا يمكن استخراج المعرف منه مباشرة")
            return None
        
        # 2. إذا كان معرف رقمي مباشر
        if channel_input.lstrip('-').isdigit():
            channel_id = int(channel_input)
            logger.info(f"تم التعرف على معرف رقمي مباشر: {channel_id}")
            return channel_id
        
        # 3. روابط القنوات الخاصة (t.me/c/CHANNEL_ID/MESSAGE_ID)
        private_link_match = re.match(
            r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/c/(\d+)(?:/\d+)?',
            channel_input
        )
        if private_link_match:
            channel_id = int('-100' + private_link_match.group(1))
            logger.info(f"تم استخراج معرف القناة من رابط خاص: {channel_id}")
            return channel_id
        
        # 4. إذا كان username (مع أو بدون @)
        username_match = re.match(r'^@?([a-zA-Z0-9_]{5,})$', channel_input)
        if username_match:
            username = username_match.group(1)
            logger.info(f"محاولة الحصول على القناة من username: @{username}")
            try:
                chat = await bot.get_chat(f"@{username}")
                logger.info(f"تم الحصول على القناة بنجاح - ID: {chat.id}, العنوان: {chat.title}")
                return chat.id
            except TelegramBadRequest as e:
                logger.error(f"القناة @{username} غير موجودة أو البوت ليس عضواً فيها: {e}")
                return None
            except TelegramForbiddenError as e:
                logger.error(f"تم حظر الوصول للقناة @{username}: {e}")
                return None
            except Exception as e:
                logger.error(f"خطأ غير متوقع في الحصول على القناة من username @{username}: {e}")
                return None
        
        # 5. روابط عامة (t.me/username أو telegram.me/username)
        public_link_patterns = [
            r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]{5,})(?:\?.*)?$',
            r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/s/([a-zA-Z0-9_]{5,})(?:\?.*)?$',
        ]
        
        for pattern in public_link_patterns:
            public_link_match = re.match(pattern, channel_input)
            if public_link_match:
                username = public_link_match.group(1)
                logger.info(f"محاولة الحصول على القناة من رابط عام: t.me/{username}")
                try:
                    chat = await bot.get_chat(f"@{username}")
                    logger.info(f"تم الحصول على القناة بنجاح - ID: {chat.id}, العنوان: {chat.title}")
                    return chat.id
                except TelegramBadRequest as e:
                    logger.error(f"القناة t.me/{username} غير موجودة أو البوت ليس عضواً فيها: {e}")
                    return None
                except TelegramForbiddenError as e:
                    logger.error(f"تم حظر الوصول للقناة t.me/{username}: {e}")
                    return None
                except Exception as e:
                    logger.error(f"خطأ غير متوقع في الحصول على القناة من رابط t.me/{username}: {e}")
                    return None
        
        logger.error(f"لم يتم التعرف على صيغة المدخل: {channel_input[:100]}")
        return None
    
    @staticmethod
    async def check_bot_permissions(bot: Bot, channel_id: int) -> Tuple[bool, str]:
        """
        التحقق من صلاحيات البوت في القناة أو المجموعة
        
        Args:
            bot: كائن البوت
            channel_id: معرف القناة أو المجموعة
            
        Returns:
            (is_admin, error_message) - نجاح التحقق ورسالة الخطأ إن وجدت
        """
        logger.info(f"بدء التحقق من صلاحيات البوت في القناة/المجموعة: {channel_id}")
        
        try:
            bot_info = await bot.get_me()
            logger.debug(f"معلومات البوت: ID={bot_info.id}, Username=@{bot_info.username}")
            
            # الحصول على معلومات الدردشة أولاً لمعرفة النوع
            chat = await bot.get_chat(channel_id)
            chat_type = chat.type
            logger.debug(f"نوع الدردشة: {chat_type}")
            
            member = await bot.get_chat_member(channel_id, bot_info.id)
            logger.debug(f"حالة البوت في الدردشة: {member.status}")
            
            if member.status not in ['administrator', 'creator']:
                error_msg = f"⚠️ البوت ليس مشرفاً في {'المجموعة' if chat_type in ['group', 'supergroup'] else 'القناة'}\n\nيجب إضافة البوت (@{bot_info.username}) كمشرف أولاً"
                logger.warning(f"البوت ليس مشرفاً في {channel_id}: {member.status}")
                return False, error_msg
            
            # التحقق من الصلاحيات حسب نوع الدردشة
            if chat_type == 'channel':
                # في القنوات: يجب أن يكون لديه صلاحية النشر
                if not member.can_post_messages:
                    error_msg = f"⚠️ البوت لا يملك صلاحية النشر في القناة\n\nيرجى منح البوت (@{bot_info.username}) صلاحية 'نشر الرسائل' في إعدادات المشرفين"
                    logger.warning(f"البوت لا يملك صلاحية النشر في القناة {channel_id}")
                    return False, error_msg
            elif chat_type in ['group', 'supergroup']:
                # في المجموعات: يكفي أن يكون مشرفاً، لكن يفضل صلاحية الحذف
                # التحقق من وجود صلاحية الحذف (اختياري)
                if hasattr(member, 'can_delete_messages') and member.can_delete_messages:
                    logger.debug(f"البوت لديه صلاحية حذف الرسائل في المجموعة")
                else:
                    logger.debug(f"البوت ليس لديه صلاحية حذف الرسائل (اختياري)")
            
            logger.info(f"✅ البوت لديه جميع الصلاحيات المطلوبة في {'المجموعة' if chat_type in ['group', 'supergroup'] else 'القناة'} {channel_id}")
            return True, ""
            
        except TelegramForbiddenError as e:
            error_msg = f"🚫 البوت غير موجود أو تم حظره\n\nيرجى التأكد من:\n1. إضافة البوت\n2. عدم حظر البوت من قبل المشرفين"
            logger.error(f"تم حظر الوصول لـ {channel_id}: {e}")
            return False, error_msg
            
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "chat not found" in error_str:
                error_msg = "❌ القناة/المجموعة غير موجودة أو البوت غير موجود فيها\n\nيرجى التحقق من:\n1. صحة الرابط/المعرف\n2. إضافة البوت"
                logger.error(f"{channel_id} غير موجودة أو البوت ليس عضواً فيها")
            elif "user not found" in error_str:
                error_msg = "❌ لم يتم العثور على البوت\n\nيرجى إضافة البوت أولاً"
                logger.error(f"لم يتم العثور على البوت في {channel_id}")
            else:
                error_msg = f"❌ خطأ في الوصول:\n{str(e)}"
                logger.error(f"خطأ في الوصول لـ {channel_id}: {e}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع في التحقق من الصلاحيات:\n{str(e)}\n\nيرجى المحاولة مرة أخرى"
            logger.error(f"خطأ غير متوقع في التحقق من صلاحيات البوت في {channel_id}: {e}", exc_info=True)
            return False, error_msg
    
    @staticmethod
    async def check_user_permissions(bot: Bot, channel_id: int, user_id: int) -> Tuple[bool, str]:
        """
        التحقق من صلاحيات المستخدم في القناة
        
        Args:
            bot: كائن البوت
            channel_id: معرف القناة
            user_id: معرف المستخدم
            
        Returns:
            (is_admin, error_message) - نجاح التحقق ورسالة الخطأ إن وجدت
        """
        logger.info(f"بدء التحقق من صلاحيات المستخدم {user_id} في القناة {channel_id}")
        
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            logger.debug(f"حالة المستخدم {user_id} في القناة: {member.status}")
            
            if member.status not in ['administrator', 'creator']:
                error_msg = "⚠️ يجب أن تكون مشرفاً في القناة لإضافتها\n\nلا يمكن إضافة القناة إلا من قبل مشرفيها"
                logger.warning(f"المستخدم {user_id} ليس مشرفاً في القناة {channel_id}: {member.status}")
                return False, error_msg
            
            logger.info(f"✅ المستخدم {user_id} لديه صلاحيات المشرف في القناة {channel_id}")
            return True, ""
            
        except TelegramForbiddenError as e:
            error_msg = "🚫 لا يمكن التحقق من صلاحياتك في القناة\n\nتأكد من أنك عضو في القناة وأن القناة لم تحظر البوت"
            logger.error(f"تم حظر التحقق من صلاحيات المستخدم {user_id} في القناة {channel_id}: {e}")
            return False, error_msg
            
        except TelegramBadRequest as e:
            error_str = str(e).lower()
            if "user not found" in error_str:
                error_msg = "❌ لم يتم العثور على حسابك في القناة\n\nتأكد من أنك عضو في القناة"
                logger.error(f"المستخدم {user_id} غير موجود في القناة {channel_id}")
            elif "chat not found" in error_str:
                error_msg = "❌ القناة غير موجودة\n\nتحقق من صحة رابط/معرف القناة"
                logger.error(f"القناة {channel_id} غير موجودة")
            else:
                error_msg = f"❌ خطأ في التحقق من صلاحياتك:\n{str(e)}"
                logger.error(f"خطأ في التحقق من صلاحيات المستخدم {user_id} في القناة {channel_id}: {e}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع في التحقق من الصلاحيات:\n{str(e)}\n\nيرجى المحاولة مرة أخرى"
            logger.error(f"خطأ غير متوقع في التحقق من صلاحيات المستخدم {user_id} في {channel_id}: {e}", exc_info=True)
            return False, error_msg
    
    @staticmethod
    async def get_channel_info(bot: Bot, channel_id: int) -> Optional[Dict]:
        """
        الحصول على معلومات القناة
        
        Args:
            bot: كائن البوت
            channel_id: معرف القناة
            
        Returns:
            معلومات القناة أو None في حالة الفشل
        """
        logger.info(f"جلب معلومات القناة {channel_id}")
        
        try:
            chat = await bot.get_chat(channel_id)
            
            channel_info = {
                'id': chat.id,
                'title': chat.title or "قناة بدون اسم",
                'username': chat.username,
                'type': chat.type
            }
            
            logger.info(f"✅ تم الحصول على معلومات القناة بنجاح: {channel_info['title']} (@{channel_info['username'] or 'خاص'})")
            logger.debug(f"تفاصيل القناة الكاملة: {channel_info}")
            
            return channel_info
            
        except TelegramBadRequest as e:
            logger.error(f"فشل الحصول على معلومات القناة {channel_id}: {e}")
            return None
        except TelegramForbiddenError as e:
            logger.error(f"تم حظر الوصول لمعلومات القناة {channel_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"خطأ غير متوقع في الحصول على معلومات القناة {channel_id}: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def verify_channel_for_task(bot: Bot, channel_id: int, user_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """
        التحقق الشامل من القناة أو المجموعة لإضافتها كمهمة
        
        يتضمن التحقق من:
        1. صلاحيات البوت في القناة/المجموعة
        2. صلاحيات المستخدم في القناة/المجموعة
        3. الحصول على معلومات القناة/المجموعة
        4. التحقق من الحد الأدنى لعدد المشتركين
        
        Args:
            bot: كائن البوت
            channel_id: معرف القناة أو المجموعة
            user_id: معرف المستخدم
            
        Returns:
            (success, error_message, channel_info)
        """
        logger.info(f"═══════════════════════════════════════")
        logger.info(f"بدء التحقق الشامل من القناة/المجموعة {channel_id} للمستخدم {user_id}")
        logger.info(f"═══════════════════════════════════════")
        
        # 1. التحقق من صلاحيات البوت
        logger.info("الخطوة 1: التحقق من صلاحيات البوت...")
        bot_has_perms, bot_error = await ChannelVerification.check_bot_permissions(bot, channel_id)
        if not bot_has_perms:
            logger.error(f"❌ فشل التحقق من صلاحيات البوت: {bot_error}")
            return False, bot_error, None
        logger.info("✅ تم التحقق من صلاحيات البوت بنجاح")
        
        # 2. التحقق من صلاحيات المستخدم
        logger.info("الخطوة 2: التحقق من صلاحيات المستخدم...")
        user_has_perms, user_error = await ChannelVerification.check_user_permissions(bot, channel_id, user_id)
        if not user_has_perms:
            logger.error(f"❌ فشل التحقق من صلاحيات المستخدم: {user_error}")
            return False, user_error, None
        logger.info("✅ تم التحقق من صلاحيات المستخدم بنجاح")
        
        # 3. الحصول على معلومات القناة/المجموعة
        logger.info("الخطوة 3: جلب معلومات القناة/المجموعة...")
        channel_info = await ChannelVerification.get_channel_info(bot, channel_id)
        if not channel_info:
            error_msg = "❌ فشل في الحصول على المعلومات\n\nيرجى المحاولة مرة أخرى أو التحقق من صحة المعرف"
            logger.error("❌ فشل في الحصول على معلومات القناة/المجموعة")
            return False, error_msg, None
        logger.info("✅ تم الحصول على المعلومات بنجاح")
        
        # 4. التحقق من الحد الأدنى لعدد المشتركين
        logger.info("الخطوة 4: التحقق من عدد المشتركين...")
        from admin_settings_manager import admin_settings
        
        if admin_settings.is_enforcement_enabled():
            min_subscribers = admin_settings.get_min_subscribers()
            
            if min_subscribers > 0:
                try:
                    members_count = await bot.get_chat_member_count(channel_id)
                    logger.info(f"عدد المشتركين في القناة/المجموعة: {members_count}")
                    
                    if members_count < min_subscribers:
                        channel_type = "المجموعة" if channel_info.get('type') in ['group', 'supergroup'] else "القناة"
                        error_msg = (
                            f"❌ عدد المشتركين غير كافٍ\n\n"
                            f"📊 عدد المشتركين الحالي: {members_count:,}\n"
                            f"📈 الحد الأدنى المطلوب: {min_subscribers:,}\n\n"
                            f"⚠️ لا يمكن إضافة {channel_type} التي تحتوي على أقل من {min_subscribers:,} مشترك.\n\n"
                            f"يرجى اختيار {channel_type} أكبر أو التواصل مع المشرف."
                        )
                        logger.warning(f"❌ القناة/المجموعة مرفوضة - عدد المشتركين ({members_count}) أقل من الحد الأدنى ({min_subscribers})")
                        return False, error_msg, None
                    
                    logger.info(f"✅ عدد المشتركين ({members_count}) يفي بالحد الأدنى ({min_subscribers})")
                except Exception as e:
                    logger.error(f"خطأ في الحصول على عدد المشتركين: {e}")
        else:
            logger.info("⏭️ تم تجاوز التحقق من عدد المشتركين (معطل)")
        
        logger.info(f"═══════════════════════════════════════")
        logger.info(f"✅ اكتمل التحقق الشامل بنجاح - {channel_info.get('type', 'قناة')}: {channel_info['title']}")
        logger.info(f"═══════════════════════════════════════")
        
        return True, "", channel_info
