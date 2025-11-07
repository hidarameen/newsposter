import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage
import os

from handlers import register_handlers
from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEB_SERVER_HOST, WEB_SERVER_PORT
from web_console import console_handler, setup_console_routes
from parallel_forwarding_system import initialize_parallel_system, shutdown_parallel_system
from user_interaction_middleware import UserInteractionMiddleware
from subscription_checker import initialize_subscription_checker, shutdown_subscription_checker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger().addHandler(console_handler)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# إضافة middleware لتتبع تفاعل المستخدمين
dp.message.middleware(UserInteractionMiddleware())
dp.callback_query.middleware(UserInteractionMiddleware())

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    
    # محاولة تعيين webhook مع معالجة Flood control
    try:
        await bot.set_webhook(
            webhook_url,
            allowed_updates=["message", "channel_post", "my_chat_member", "callback_query"]
        )
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        if "Flood control" in str(e) or "Too Many Requests" in str(e):
            logger.warning(f"⚠️ Flood control - الانتظار قليلاً قبل إعادة المحاولة...")
            import asyncio
            await asyncio.sleep(3)
            try:
                await bot.set_webhook(
                    webhook_url,
                    allowed_updates=["message", "channel_post", "my_chat_member", "callback_query"]
                )
                logger.info(f"✅ Webhook set successfully after retry")
            except Exception as retry_error:
                logger.error(f"❌ فشل تعيين webhook بعد إعادة المحاولة: {retry_error}")
                raise
        else:
            logger.error(f"❌ خطأ في تعيين webhook: {e}")
            raise

    # التحقق من الـ webhook
    webhook_info = await bot.get_webhook_info()
    logger.info(f"📡 Webhook Info:")
    logger.info(f"  URL: {webhook_info.url}")
    logger.info(f"  Pending updates: {webhook_info.pending_update_count}")
    logger.info(f"  Last error: {webhook_info.last_error_message if webhook_info.last_error_message else 'None'}")

    # التحقق من معلومات البوت
    bot_info = await bot.get_me()
    logger.info(f"🤖 Bot Info:")
    logger.info(f"  Username: @{bot_info.username}")
    logger.info(f"  ID: {bot_info.id}")

    # تشغيل النظام المتوازي
    await initialize_parallel_system(bot)
    logger.info("✅ تم تشغيل النظام المتوازي للتوجيه")

    # تشغيل نظام فحص الاشتراكات
    await initialize_subscription_checker(bot)
    logger.info("✅ تم تشغيل نظام فحص الاشتراكات")

async def on_shutdown(bot: Bot):
    # إيقاف نظام فحص الاشتراكات
    await shutdown_subscription_checker()
    logger.info("🛑 تم إيقاف نظام فحص الاشتراكات")

    # إيقاف النظام المتوازي
    await shutdown_parallel_system()
    logger.info("🛑 تم إيقاف النظام المتوازي")

    await bot.delete_webhook()
    logger.info("Webhook deleted")

def main():
    register_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # إضافة صفحة رئيسية
    async def home(request):
        return web.Response(text="""
        <html dir="rtl">
        <head><title>البوت يعمل</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>✅ البوت يعمل بنجاح</h1>
            <p>للوصول إلى لوحة التحكم: <a href="/console">/console</a></p>
        </body>
        </html>
        """, content_type='text/html')

    app.router.add_get('/', home)
    setup_console_routes(app)

    setup_application(app, dp, bot=bot)

    logger.info(f"🌐 Web Console متاح على: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/console")

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == '__main__':
    main()