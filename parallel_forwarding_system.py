
import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import Message
from forwarding_manager import ForwardingManager

logger = logging.getLogger(__name__)

@dataclass
class QueuedMessage:
    """رسالة في قائمة الانتظار"""
    message: Message
    source_channel_id: int
    timestamp: float

class GlobalMessageQueue:
    """قائمة انتظار عامة لجميع الرسائل الواردة"""
    def __init__(self, max_size: int = 10000):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.is_running = False
        self.max_size = max_size
        self.dropped_messages = 0
        
    async def add_message(self, message: Message):
        """إضافة رسالة إلى القائمة العامة"""
        import time
        queued_msg = QueuedMessage(
            message=message,
            source_channel_id=message.chat.id,
            timestamp=time.time()
        )
        
        try:
            # محاولة إضافة الرسالة بدون انتظار
            self.queue.put_nowait(queued_msg)
            logger.info(f"📥 رسالة جديدة في القائمة العامة من القناة {message.chat.id}")
        except asyncio.QueueFull:
            self.dropped_messages += 1
            logger.error(f"🚨 القائمة العامة ممتلئة ({self.max_size})! تم تجاهل رسالة من {message.chat.id} - إجمالي الرسائل المتجاهلة: {self.dropped_messages}")
    
    async def get_message(self) -> Optional[QueuedMessage]:
        """استخراج رسالة من القائمة العامة"""
        return await self.queue.get()
    
    def queue_size(self) -> int:
        """حجم القائمة الحالي"""
        return self.queue.qsize()

class TaskQueue:
    """قائمة انتظار داخلية لكل مهمة"""
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.queue = asyncio.Queue()
        
    async def add_message(self, message: Message):
        """إضافة رسالة لقائمة المهمة"""
        await self.queue.put(message)
        
    async def get_message(self) -> Optional[Message]:
        """استخراج رسالة من قائمة المهمة"""
        return await self.queue.get()

class TaskWorker:
    """Worker مخصص لمهمة توجيه واحدة"""
    def __init__(self, task_id: int, bot: Bot, num_target_workers: int = 30):
        self.task_id = task_id
        self.bot = bot
        self.task_queue = TaskQueue(task_id)
        self.num_target_workers = num_target_workers
        self.is_running = False
        self.workers = []
        self.manager = None  # سيتم تعيينه في start()
        self.album_buffers_timestamps = {}  # تتبع وقت إنشاء كل buffer
        
    async def process_message(self, message: Message, target_channel: Dict, retry_count: int = 0):
        """نسخ رسالة واحدة لقناة هدف واحدة مع الحفاظ على entities وتطبيق الفلاتر"""
        target_name = target_channel.get('title', 'Unknown')
        target_id = target_channel.get('id', 0)
        max_retries = 3
        
        logger.info(f"🔄 [المهمة #{self.task_id}] بدء توجيه رسالة إلى: {target_name} (ID: {target_id}) - محاولة {retry_count + 1}/{max_retries + 1}")
        
        try:
            from media_handler import MediaHandler
            
            user_id = target_channel.get('user_id', 0)
            user_task_id = target_channel.get('user_task_id', 0)
            
            if message.media_group_id:
                logger.info(f"📦 [المهمة #{self.task_id}] معالجة ألبوم وسائط (ID: {message.media_group_id}) للهدف: {target_name}")
                
                # إنشاء album buffer منفصل لكل قناة هدف
                buffer_key = f"{message.media_group_id}_{target_channel['id']}"
                
                if not hasattr(self, 'album_buffers'):
                    self.album_buffers = {}
                
                if buffer_key not in self.album_buffers:
                    from album_processor import AlbumBuffer
                    import time
                    self.album_buffers[buffer_key] = AlbumBuffer()
                    self.album_buffers_timestamps[buffer_key] = time.time()
                
                async def album_callback(msgs):
                    try:
                        await self._process_album(msgs, target_channel, user_id, user_task_id)
                    finally:
                        # تنظيف buffer حتى في حالة الفشل
                        if buffer_key in self.album_buffers:
                            del self.album_buffers[buffer_key]
                            logger.info(f"🧹 [المهمة #{self.task_id}] تم تنظيف album buffer: {buffer_key}")
                
                await self.album_buffers[buffer_key].add_message(
                    message,
                    message.media_group_id,
                    album_callback
                )
            else:
                logger.info(f"📝 [المهمة #{self.task_id}] نسخ رسالة فردية للهدف: {target_name}")
                await MediaHandler.copy_message_with_entities(
                    self.bot, message, target_channel['id'], user_id, user_task_id
                )
                logger.info(f"✅ [المهمة #{self.task_id}] نجح التوجيه إلى: {target_name} (ID: {target_id})")
                
                # تأخير صغير لتجنب Flood Control (50ms)
                await asyncio.sleep(0.05)
        except Exception as e:
            # إعادة المحاولة في حالات معينة
            if retry_count < max_retries:
                # التحقق من نوع الخطأ
                error_str = str(e).lower()
                retriable_errors = ['timeout', 'network', 'flood', 'too many requests', 'connection']
                
                if any(err in error_str for err in retriable_errors):
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** retry_count
                    logger.warning(f"⚠️ [المهمة #{self.task_id}] خطأ قابل للإعادة في {target_name} - إعادة المحاولة بعد {wait_time}s")
                    await asyncio.sleep(wait_time)
                    return await self.process_message(message, target_channel, retry_count + 1)
            
            logger.error(f"❌ [المهمة #{self.task_id}] فشل التوجيه إلى: {target_name} (ID: {target_id}) - الخطأ: {e}")
    
    async def _process_album(self, album_messages, target_channel, user_id, user_task_id):
        """معالجة ألبوم الوسائط - إرسال لقناة واحدة فقط"""
        target_name = target_channel.get('title', 'Unknown')
        target_id = target_channel.get('id', 0)
        
        logger.info(f"📦 [المهمة #{self.task_id}] بدء إرسال ألبوم ({len(album_messages)} وسائط) إلى: {target_name} (ID: {target_id})")
        
        try:
            if user_id and user_task_id:
                logger.info(f"🔧 [المهمة #{self.task_id}] استخدام AlbumProcessor مع فلاتر المستخدم (User: {user_id}, Task: {user_task_id})")
                from album_processor import AlbumProcessor
                processor = AlbumProcessor(user_id, user_task_id)
                await processor.process_and_send_album(
                    self.bot, album_messages, target_channel['id']
                )
            else:
                logger.info(f"🔧 [المهمة #{self.task_id}] استخدام album_buffer بدون فلاتر")
                from media_handler import album_buffer
                await album_buffer.copy_album(self.bot, album_messages, target_channel['id'])
            
            logger.info(f"✅ [المهمة #{self.task_id}] نجح إرسال الألبوم ({len(album_messages)} وسائط) إلى: {target_name} (ID: {target_id})")
            
            # تأخير صغير لتجنب Flood Control (50ms)
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"❌ [المهمة #{self.task_id}] فشل إرسال الألبوم إلى: {target_name} (ID: {target_id}) - الخطأ: {e}")
    
    async def target_worker(self, worker_id: int):
        """Worker لتوجيه الرسائل للأهداف بالتوازي مع نظام Batching"""
        logger.info(f"🚀 بدء Target Worker #{worker_id} للمهمة #{self.task_id}")
        
        # حجم كل دفعة من الأهداف
        BATCH_SIZE = 20
        
        while self.is_running:
            try:
                # انتظار رسالة من قائمة المهمة
                message = await asyncio.wait_for(
                    self.task_queue.get_message(),
                    timeout=1.0
                )
                
                # التحقق من أن الرسالة ليست None
                if message is None:
                    continue
                
                # الحصول على معلومات المهمة من الـ manager المُحدَّث
                if not self.manager:
                    logger.error(f"❌ Manager غير موجود للمهمة #{self.task_id}")
                    continue
                    
                task = self.manager.get_task(self.task_id)
                if not task or not task.is_active:
                    continue
                
                targets = task.target_channels
                total_targets = len(targets)
                
                logger.info(f"📊 [المهمة #{self.task_id}] بدء توزيع رسالة على {total_targets} أهداف بنظام Batching (كل دفعة {BATCH_SIZE} قناة)")
                
                total_success = 0
                total_failure = 0
                
                # تقسيم الأهداف إلى دفعات
                for batch_num, i in enumerate(range(0, total_targets, BATCH_SIZE), 1):
                    batch = targets[i:i + BATCH_SIZE]
                    batch_size = len(batch)
                    
                    logger.info(f"📦 [المهمة #{self.task_id}] معالجة الدفعة #{batch_num} ({batch_size} قناة)")
                    
                    # توجيه الرسالة لجميع الأهداف في الدفعة بالتوازي مع timeout
                    forward_tasks = [
                        asyncio.wait_for(
                            self.process_message(message, target),
                            timeout=30.0  # 30 ثانية لكل رسالة
                        )
                        for target in batch
                    ]
                    
                    results = await asyncio.gather(*forward_tasks, return_exceptions=True)
                    
                    # تحليل نتائج الدفعة
                    batch_success = sum(1 for r in results if not isinstance(r, Exception))
                    batch_failure = sum(1 for r in results if isinstance(r, Exception))
                    
                    total_success += batch_success
                    total_failure += batch_failure
                    
                    logger.info(f"✅ [المهمة #{self.task_id}] الدفعة #{batch_num}: نجح {batch_success}/{batch_size}")
                    
                    # تسجيل الأخطاء في الدفعة إن وجدت
                    for idx, result in enumerate(results):
                        if isinstance(result, Exception):
                            target = batch[idx] if idx < len(batch) else {'title': 'Unknown', 'id': 0}
                            logger.error(f"⚠️ [المهمة #{self.task_id}] استثناء في الدفعة #{batch_num} عند التوجيه إلى {target['title']}: {result}")
                    
                    # تأخير كافٍ بين الدفعات لتجنب Rate Limiting
                    # Telegram: حد 20 رسالة/ثانية، مع 30 قناة/دفعة نحتاج 1.5s
                    if i + BATCH_SIZE < total_targets:
                        await asyncio.sleep(1.5)
                
                logger.info(f"📈 [المهمة #{self.task_id}] ملخص التوجيه النهائي: ✅ نجح: {total_success} | ❌ فشل: {total_failure} | 📊 إجمالي: {total_targets}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ خطأ في Target Worker #{worker_id} للمهمة #{self.task_id}: {e}")
                await asyncio.sleep(1)
    
    async def cleanup_old_album_buffers(self):
        """تنظيف album buffers التي مر عليها أكثر من 5 دقائق أو تجاوز العدد الأقصى"""
        if not hasattr(self, 'album_buffers'):
            return
        
        import time
        current_time = time.time()
        max_age = 300  # 5 دقائق
        max_buffers = 100  # حد أقصى 100 buffer
        
        old_buffers = []
        
        # حذف buffers القديمة
        for buffer_key, timestamp in list(self.album_buffers_timestamps.items()):
            if current_time - timestamp > max_age:
                old_buffers.append(buffer_key)
        
        # إذا تجاوز عدد الـ buffers الحد الأقصى، احذف الأقدم
        if len(self.album_buffers) > max_buffers:
            sorted_buffers = sorted(
                self.album_buffers_timestamps.items(),
                key=lambda x: x[1]
            )
            excess_count = len(self.album_buffers) - max_buffers
            for buffer_key, _ in sorted_buffers[:excess_count]:
                if buffer_key not in old_buffers:
                    old_buffers.append(buffer_key)
            logger.warning(f"⚠️ [المهمة #{self.task_id}] تجاوز عدد buffers الحد الأقصى ({max_buffers})")
        
        for buffer_key in old_buffers:
            if buffer_key in self.album_buffers:
                del self.album_buffers[buffer_key]
            if buffer_key in self.album_buffers_timestamps:
                del self.album_buffers_timestamps[buffer_key]
            logger.info(f"🧹 [المهمة #{self.task_id}] تم حذف album buffer: {buffer_key}")
        
        if old_buffers:
            logger.info(f"🧹 [المهمة #{self.task_id}] تم تنظيف {len(old_buffers)} album buffers")
    
    async def target_worker_old(self, worker_id: int):
        """Worker قديم - تم استبداله بنظام أفضل"""
        BATCH_SIZE = 20
        
        while self.is_running:
            try:
                # انتظار رسالة من قائمة المهمة
                message = await asyncio.wait_for(
                    self.task_queue.get_message(),
                    timeout=1.0
                )
                
                # التحقق من أن الرسالة ليست None
                if message is None:
                    continue
                
                # الحصول على معلومات المهمة من الـ manager المُحدَّث
                if not self.manager:
                    logger.error(f"❌ Manager غير موجود للمهمة #{self.task_id}")
                    continue
                    
                task = self.manager.get_task(self.task_id)
                if not task or not task.is_active:
                    continue
                
                targets = task.target_channels
                total_targets = len(targets)
                
                logger.info(f"📊 [المهمة #{self.task_id}] بدء توزيع رسالة على {total_targets} أهداف بنظام Batching (كل دفعة {BATCH_SIZE} قناة)")
                
                total_success = 0
                total_failure = 0
                
                # تقسيم الأهداف إلى دفعات
                for batch_num, i in enumerate(range(0, total_targets, BATCH_SIZE), 1):
                    batch = targets[i:i + BATCH_SIZE]
                    batch_size = len(batch)
                    
                    logger.info(f"📦 [المهمة #{self.task_id}] معالجة الدفعة #{batch_num} ({batch_size} قناة)")
                    
                    # توجيه الرسالة لجميع الأهداف في الدفعة بالتوازي مع timeout
                    forward_tasks = [
                        asyncio.wait_for(
                            self.process_message(message, target),
                            timeout=30.0  # 30 ثانية لكل رسالة
                        )
                        for target in batch
                    ]
                    
                    results = await asyncio.gather(*forward_tasks, return_exceptions=True)
                    
                    # تحليل نتائج الدفعة
                    batch_success = sum(1 for r in results if not isinstance(r, Exception))
                    batch_failure = sum(1 for r in results if isinstance(r, Exception))
                    
                    total_success += batch_success
                    total_failure += batch_failure
                    
                    logger.info(f"✅ [المهمة #{self.task_id}] الدفعة #{batch_num}: نجح {batch_success}/{batch_size}")
                    
                    # تسجيل الأخطاء في الدفعة إن وجدت
                    for idx, result in enumerate(results):
                        if isinstance(result, Exception):
                            target = batch[idx] if idx < len(batch) else {'title': 'Unknown', 'id': 0}
                            logger.error(f"⚠️ [المهمة #{self.task_id}] استثناء في الدفعة #{batch_num} عند التوجيه إلى {target['title']}: {result}")
                    
                    # تأخير كافٍ بين الدفعات لتجنب Rate Limiting
                    # Telegram: حد 20 رسالة/ثانية، مع 30 قناة/دفعة نحتاج 1.5s
                    if i + BATCH_SIZE < total_targets:
                        await asyncio.sleep(1.5)
                
                logger.info(f"📈 [المهمة #{self.task_id}] ملخص التوجيه النهائي: ✅ نجح: {total_success} | ❌ فشل: {total_failure} | 📊 إجمالي: {total_targets}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ خطأ في Target Worker #{worker_id} للمهمة #{self.task_id}: {e}")
                await asyncio.sleep(1)
    
    async def start(self, manager: ForwardingManager):
        """تشغيل جميع workers للمهمة"""
        self.is_running = True
        self.manager = manager  # حفظ المرجع
        
        # إنشاء workers متعددة لتوجيه الرسائل
        for i in range(self.num_target_workers):
            worker = asyncio.create_task(self.target_worker(i))
            self.workers.append(worker)
        
        # إضافة worker للتنظيف الدوري
        cleanup_worker = asyncio.create_task(self._cleanup_worker())
        self.workers.append(cleanup_worker)
        
        logger.info(f"✅ تم تشغيل {self.num_target_workers} Target Workers + Cleanup Worker للمهمة #{self.task_id}")
    
    async def _cleanup_worker(self):
        """Worker للتنظيف الدوري لـ album buffers"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # تنظيف كل دقيقة
                await self.cleanup_old_album_buffers()
            except Exception as e:
                logger.error(f"❌ خطأ في cleanup worker للمهمة #{self.task_id}: {e}")
    
    def update_manager(self, manager: ForwardingManager):
        """تحديث المرجع للـ manager (يستخدم عند إعادة التحميل)"""
        self.manager = manager
        logger.info(f"🔄 تم تحديث manager للمهمة #{self.task_id}")
    
    async def stop(self):
        """إيقاف جميع workers مع حفظ الرسائل المعلقة"""
        self.is_running = False
        
        # محاولة معالجة الرسائل المعلقة قبل الإيقاف
        pending_messages = []
        try:
            while not self.task_queue.queue.empty():
                try:
                    message = self.task_queue.queue.get_nowait()
                    pending_messages.append(message)
                except asyncio.QueueEmpty:
                    break
            
            if pending_messages:
                logger.warning(f"⚠️ [المهمة #{self.task_id}] توجد {len(pending_messages)} رسالة معلقة عند الإيقاف")
                
                # محاولة معالجة الرسائل المعلقة بسرعة
                if self.manager:
                    task = self.manager.get_task(self.task_id)
                    if task and task.is_active:
                        logger.info(f"🔄 [المهمة #{self.task_id}] محاولة معالجة الرسائل المعلقة...")
                        for message in pending_messages[:10]:  # معالجة أول 10 رسائل فقط
                            try:
                                for target in task.target_channels:
                                    await asyncio.wait_for(
                                        self.process_message(message, target),
                                        timeout=2.0
                                    )
                            except asyncio.TimeoutError:
                                logger.warning(f"⏱️ انتهى وقت معالجة رسالة معلقة")
                            except Exception as e:
                                logger.error(f"❌ خطأ في معالجة رسالة معلقة: {e}")
        except Exception as e:
            logger.error(f"❌ خطأ أثناء حفظ الرسائل المعلقة: {e}")
        
        # إيقاف Workers
        for worker in self.workers:
            worker.cancel()
        self.workers.clear()

class ParallelForwardingSystem:
    """النظام الرئيسي للتوجيه المتوازي"""
    def __init__(self, bot: Bot, num_global_workers: int = 30):
        self.bot = bot
        self.manager = ForwardingManager()
        self.global_queue = GlobalMessageQueue()
        self.task_workers: Dict[int, TaskWorker] = {}
        self.num_global_workers = num_global_workers
        self.global_workers = []
        self.is_running = False
        self._reload_lock = asyncio.Lock()  # حماية من race conditions
        
    async def global_message_distributor(self, worker_id: int):
        """Worker عام لتوزيع الرسائل على المهام المناسبة"""
        logger.info(f"🚀 بدء Global Worker #{worker_id}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running:
            try:
                # انتظار رسالة من القائمة العامة
                queued_msg = await asyncio.wait_for(
                    self.global_queue.get_message(),
                    timeout=1.0
                )
                
                # التحقق من أن الرسالة ليست None
                if queued_msg is None:
                    continue
                
                message = queued_msg.message
                source_channel_id = queued_msg.source_channel_id
                
                # البحث عن المهام المناسبة
                active_tasks = self.manager.get_active_tasks()
                
                message_distributed = False
                for task_id, task in active_tasks.items():
                    # التحقق من أن القناة المصدر موجودة في المهمة
                    source_ids = [ch['id'] for ch in task.source_channels]
                    if source_channel_id in source_ids:
                        # إضافة الرسالة لقائمة المهمة
                        if task_id in self.task_workers:
                            try:
                                await self.task_workers[task_id].task_queue.add_message(message)
                                logger.info(f"📤 تم توزيع الرسالة للمهمة #{task_id}")
                                message_distributed = True
                            except Exception as e:
                                logger.error(f"❌ فشل توزيع الرسالة للمهمة #{task_id}: {e}")
                
                if not message_distributed:
                    logger.warning(f"⚠️ لم يتم توزيع الرسالة من القناة {source_channel_id} - لا توجد مهام نشطة")
                
                # إعادة تعيين عداد الأخطاء عند النجاح
                consecutive_errors = 0
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info(f"🛑 تم إلغاء Global Worker #{worker_id}")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ خطأ في Global Worker #{worker_id} (خطأ {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"🚨 Global Worker #{worker_id} توقف بعد {consecutive_errors} أخطاء متتالية")
                    break
                
                await asyncio.sleep(min(consecutive_errors, 5))  # Exponential backoff
    
    async def reload_tasks(self):
        """إعادة تحميل المهام وتحديث Workers"""
        async with self._reload_lock:
            try:
                # إعادة إنشاء manager للتأكد من قراءة أحدث البيانات
                new_manager = ForwardingManager()
                all_tasks = new_manager.get_all_tasks()
                
                # إيقاف workers للمهام المحذوفة
                tasks_to_delete = []
                for task_id in list(self.task_workers.keys()):
                    if task_id not in all_tasks:
                        tasks_to_delete.append(task_id)
                
                # إيقاف Workers بالتوازي
                if tasks_to_delete:
                    stop_tasks = [self.task_workers[tid].stop() for tid in tasks_to_delete]
                    await asyncio.gather(*stop_tasks, return_exceptions=True)
                    for task_id in tasks_to_delete:
                        del self.task_workers[task_id]
                        logger.info(f"🛑 تم إيقاف Workers للمهمة #{task_id}")
                
                # إنشاء workers للمهام الجديدة
                new_workers = []
                for task_id in all_tasks:
                    if task_id not in self.task_workers:
                        worker = TaskWorker(task_id, self.bot)
                        new_workers.append((task_id, worker))
                
                # تشغيل Workers الجديدة بالتوازي
                if new_workers:
                    start_tasks = [worker.start(new_manager) for _, worker in new_workers]
                    await asyncio.gather(*start_tasks, return_exceptions=True)
                    for task_id, worker in new_workers:
                        self.task_workers[task_id] = worker
                        logger.info(f"✅ تم إنشاء Workers للمهمة #{task_id}")
                
                # تحديث manager للـ workers الموجودة
                for task_id in all_tasks:
                    if task_id in self.task_workers and task_id not in [tid for tid, _ in new_workers]:
                        self.task_workers[task_id].update_manager(new_manager)
                
                # تحديث المرجع العام بعد الانتهاء من جميع التحديثات
                self.manager = new_manager
                
                logger.info(f"🔄 تم إعادة تحميل {len(all_tasks)} مهمة بنجاح")
            except Exception as e:
                logger.error(f"❌ خطأ خطير في reload_tasks: {e}")
                raise
    
    async def start(self):
        """تشغيل النظام الكامل"""
        self.is_running = True
        
        # تحميل وتشغيل workers المهام
        await self.reload_tasks()
        
        # تشغيل Global Workers
        for i in range(self.num_global_workers):
            worker = asyncio.create_task(self.global_message_distributor(i))
            self.global_workers.append(worker)
        
        logger.info(f"🎯 تم تشغيل النظام المتوازي بـ {self.num_global_workers} Global Workers")
    
    async def stop(self):
        """إيقاف النظام"""
        self.is_running = False
        
        # إيقاف Global Workers
        for worker in self.global_workers:
            worker.cancel()
        self.global_workers.clear()
        
        # إيقاف جميع Task Workers
        for worker in self.task_workers.values():
            await worker.stop()
        self.task_workers.clear()
        
        logger.info("🛑 تم إيقاف النظام المتوازي")
    
    async def add_message_from_webhook(self, message: Message):
        """إضافة رسالة من webhook للقائمة العامة"""
        await self.global_queue.add_message(message)
    
    def get_stats(self) -> Dict:
        """إحصائيات النظام"""
        total_album_buffers = sum(
            len(getattr(worker, 'album_buffers', {}))
            for worker in self.task_workers.values()
        )
        
        return {
            "global_queue_size": self.global_queue.queue_size(),
            "global_queue_max_size": self.global_queue.max_size,
            "dropped_messages": self.global_queue.dropped_messages,
            "num_global_workers": len(self.global_workers),
            "num_active_tasks": len(self.task_workers),
            "total_album_buffers": total_album_buffers,
            "tasks": {
                task_id: {
                    "queue_size": worker.task_queue.queue.qsize(),
                    "num_workers": len(worker.workers),
                    "album_buffers": len(getattr(worker, 'album_buffers', {}))
                }
                for task_id, worker in self.task_workers.items()
            }
        }

# متغير عام للنظام
parallel_system: Optional[ParallelForwardingSystem] = None

async def initialize_parallel_system(bot: Bot):
    """تهيئة النظام المتوازي"""
    global parallel_system
    parallel_system = ParallelForwardingSystem(bot, num_global_workers=30)
    await parallel_system.start()
    return parallel_system

async def shutdown_parallel_system():
    """إيقاف النظام المتوازي"""
    global parallel_system
    if parallel_system:
        await parallel_system.stop()
