import logging
from typing import Optional, Dict
from aiogram.types import Message

logger = logging.getLogger(__name__)

class ReplyPreservationHandler:
    """معالج الحفاظ على تسلسل الردود"""
    
    def __init__(self):
        # تخزين mapping بين message_id في المصدر و message_id في الهدف
        # {source_chat_id: {source_msg_id: {target_chat_id: target_msg_id}}}
        self.message_mapping: Dict[int, Dict[int, Dict[int, int]]] = {}
    
    def store_message_mapping(
        self,
        source_chat_id: int,
        source_message_id: int,
        target_chat_id: int,
        target_message_id: int
    ):
        """
        تخزين mapping بين رسالة المصدر والهدف
        
        Args:
            source_chat_id: معرف قناة المصدر
            source_message_id: معرف الرسالة في المصدر
            target_chat_id: معرف قناة الهدف
            target_message_id: معرف الرسالة في الهدف
        """
        if source_chat_id not in self.message_mapping:
            self.message_mapping[source_chat_id] = {}
        
        if source_message_id not in self.message_mapping[source_chat_id]:
            self.message_mapping[source_chat_id][source_message_id] = {}
        
        self.message_mapping[source_chat_id][source_message_id][target_chat_id] = target_message_id
        
        logger.info(
            f"💾 تخزين mapping: المصدر[{source_chat_id}:{source_message_id}] "
            f"→ الهدف[{target_chat_id}:{target_message_id}]"
        )
    
    def get_target_message_id(
        self,
        source_chat_id: int,
        source_message_id: int,
        target_chat_id: int
    ) -> Optional[int]:
        """
        الحصول على معرف الرسالة في الهدف بناءً على معرف رسالة المصدر
        
        Args:
            source_chat_id: معرف قناة المصدر
            source_message_id: معرف الرسالة في المصدر
            target_chat_id: معرف قناة الهدف
            
        Returns:
            معرف الرسالة في الهدف أو None
        """
        try:
            target_id = self.message_mapping.get(source_chat_id, {}).get(
                source_message_id, {}
            ).get(target_chat_id)
            
            if target_id:
                logger.info(
                    f"✅ تم العثور على mapping: المصدر[{source_chat_id}:{source_message_id}] "
                    f"→ الهدف[{target_chat_id}:{target_id}]"
                )
            
            return target_id
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على target_message_id: {e}")
            return None
    
    def get_reply_to_message_id(
        self,
        message: Message,
        target_chat_id: int
    ) -> Optional[int]:
        """
        الحصول على معرف الرسالة المراد الرد عليها في القناة الهدف
        
        Args:
            message: الرسالة الأصلية
            target_chat_id: معرف قناة الهدف
            
        Returns:
            معرف الرسالة المراد الرد عليها أو None
        """
        if not message.reply_to_message:
            return None
        
        source_chat_id = message.chat.id
        source_reply_id = message.reply_to_message.message_id
        
        reply_to_id = self.get_target_message_id(
            source_chat_id,
            source_reply_id,
            target_chat_id
        )
        
        if reply_to_id:
            logger.info(
                f"🔗 سيتم الرد على الرسالة {reply_to_id} في القناة {target_chat_id}"
            )
        else:
            logger.warning(
                f"⚠️ لم يتم العثور على الرسالة الأصلية للرد عليها في القناة {target_chat_id}"
            )
        
        return reply_to_id
    
    def clear_old_mappings(self, max_size: int = 10000):
        """
        مسح الـ mappings القديمة لتجنب استهلاك الذاكرة
        
        Args:
            max_size: الحد الأقصى لعدد الرسائل المخزنة لكل قناة
        """
        for source_chat_id in list(self.message_mapping.keys()):
            if len(self.message_mapping[source_chat_id]) > max_size:
                # حذف أقدم 20% من الرسائل
                sorted_ids = sorted(self.message_mapping[source_chat_id].keys())
                to_remove = int(max_size * 0.2)
                
                for msg_id in sorted_ids[:to_remove]:
                    del self.message_mapping[source_chat_id][msg_id]
                
                logger.info(
                    f"🧹 تم مسح {to_remove} mapping قديم من القناة {source_chat_id}"
                )
    
    def clear_all_mappings(self):
        """مسح جميع الـ mappings"""
        self.message_mapping.clear()
        logger.info("🗑️ تم مسح جميع message mappings")

# مثيل عام
reply_preservation = ReplyPreservationHandler()
