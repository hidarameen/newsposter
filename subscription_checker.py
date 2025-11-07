import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot
from subscription_manager import SubscriptionManager
from config import USERS_DATA_DIR

logger = logging.getLogger(__name__)

class SubscriptionChecker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False
        self.check_task = None

    async def start(self):
        if self.is_running:
            return

        self.is_running = True
        self.check_task = asyncio.create_task(self._check_loop())
        logger.info("✅ تم تشغيل نظام فحص الاشتراكات")

    async def stop(self):
        self.is_running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 تم إيقاف نظام فحص الاشتراكات")

    async def _check_loop(self):
        while self.is_running:
            try:
                await self._check_all_subscriptions()
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"خطأ في فحص الاشتراكات: {e}")
                await asyncio.sleep(3600)

    async def _check_all_subscriptions(self):
        if not os.path.exists(USERS_DATA_DIR):
            return

        for user_dir in os.listdir(USERS_DATA_DIR):
            if not user_dir.isdigit():
                continue

            user_id = int(user_dir)
            await self._check_user_subscription(user_id)

    async def _check_user_subscription(self, user_id: int):
        try:
            sub_manager = SubscriptionManager(user_id)

            warning_days = sub_manager.should_send_warning()
            if warning_days:
                await self._send_warning(user_id, warning_days, sub_manager)
                sub_manager.mark_warning_sent(str(warning_days))

            if not sub_manager.is_premium():
                sub = sub_manager.load_subscription()
                if sub['plan'] != 'free' and sub.get('end_date'):
                    end_date = datetime.fromisoformat(sub['end_date'])
                    if datetime.now() >= end_date:
                        await self._handle_expired_subscription(user_id, sub_manager)

        except Exception as e:
            logger.error(f"خطأ في فحص اشتراك المستخدم {user_id}: {e}")

    async def _send_warning(self, user_id: int, days_remaining: int, sub_manager: SubscriptionManager):
        plan_details = sub_manager.get_plan_details()

        if days_remaining == 7:
            icon = "⚠️"
            message = "تنبيه: اشتراكك سينتهي خلال 7 أيام"
        elif days_remaining == 3:
            icon = "⏰"
            message = "تحذير: اشتراكك سينتهي خلال 3 أيام"
        else:
            icon = "🚨"
            message = "عاجل: اشتراكك سينتهي غداً!"

        plan_name = "التجربة المجانية" if plan_details['is_trial'] else plan_details['plan']

        text = f"""{icon} <b>{message}</b>

📋 <b>تفاصيل الاشتراك:</b>
• الخطة: {plan_name}
• الأيام المتبقية: {days_remaining} يوم
• تاريخ الانتهاء: {plan_details['end_date'][:10]}

💡 <b>لا تفقد المميزات المدفوعة!</b>
قم بتجديد اشتراكك الآن للاستمرار في الاستفادة من جميع المميزات.

🔒 بعد انتهاء الاشتراك:
• سيتم تعطيل جميع المميزات المدفوعة تلقائياً
• ستتمكن من استخدام مهمة نشر واحدة فقط
• يمكنك تجديد الاشتراك في أي وقت"""

        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 تجديد الاشتراك", callback_data="upgrade_account")],
                [InlineKeyboardButton(text="📊 اشتراكي", callback_data="my_subscription")]
            ])

            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            logger.info(f"✅ تم إرسال تحذير {days_remaining} أيام للمستخدم {user_id}")
        except Exception as e:
            logger.error(f"خطأ في إرسال تحذير للمستخدم {user_id}: {e}")

    async def _handle_expired_subscription(self, user_id: int, sub_manager: SubscriptionManager):
        plan_details = sub_manager.get_plan_details()
        was_trial = plan_details['is_trial']
        plan_name = "التجربة المجانية" if was_trial else plan_details['plan']

        sub_manager.disable_active_premium_features()
        sub_manager.deactivate_premium_features()

        text = f"""🔒 <b>انتهى اشتراكك</b>

📋 تم انتهاء {plan_name}

⚠️ <b>التغييرات التي تمت:</b>
• تم تعطيل جميع المميزات المدفوعة
• تم إيقاف الفلاتر والإعدادات المتقدمة
• يمكنك الآن استخدام مهمة نشر واحدة فقط

💡 <b>للعودة إلى المميزات المدفوعة:</b>
قم بترقية حسابك الآن واستمتع بجميع المميزات مرة أخرى!

✨ يمكنك تجديد الاشتراك في أي وقت"""

        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔒 ترقية الحساب", callback_data="upgrade_account")]
            ])

            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            logger.info(f"✅ تم تحويل المستخدم {user_id} إلى النسخة المجانية")
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة انتهاء الاشتراك للمستخدم {user_id}: {e}")

_subscription_checker = None

async def initialize_subscription_checker(bot: Bot):
    global _subscription_checker
    _subscription_checker = SubscriptionChecker(bot)
    await _subscription_checker.start()

async def shutdown_subscription_checker():
    global _subscription_checker
    if _subscription_checker:
        await _subscription_checker.stop()

async def check_subscriptions_task():
    """مهمة دورية للتحقق من انتهاء الاشتراكات"""
    global subscription_checker_running

    while subscription_checker_running:
        try:
            logger.info("🔍 بدء فحص الاشتراكات...")

            # تنظيف المهام المعلقة المنتهية
            from pending_tasks_manager import PendingTasksManager
            pending_manager = PendingTasksManager()
            cleaned_count = pending_manager.cleanup_expired_tasks()
            if cleaned_count > 0:
                logger.info(f"🧹 تم تنظيف {cleaned_count} مهمة معلقة منتهية")

            # الحصول على جميع المستخدمين
            users_dir = USERS_DATA_DIR
            if not os.path.exists(users_dir):
                await asyncio.sleep(3600)
                continue
        except Exception as e:
            logger.error(f"خطأ في مهمة فحص الاشتراكات: {e}")
            await asyncio.sleep(3600)