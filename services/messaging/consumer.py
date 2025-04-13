import os
import json
import asyncio
import logging
from typing import Optional

import aio_pika 
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, AsyncRetrying
from common.models.dto.resultdto import ResultDTO
from services.chatService import ChatService
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

class RabbitMQConsumer:
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self._shutdown_flag = asyncio.Event()  # Using async event instead of threading.Event

    async def connect(self):
        """Initialize RabbitMQ connection"""
        try:
            self.connection = await aio_pika.connect_robust(
                host=os.getenv("RBMQ_HOSTNAME"),
                login=os.getenv("RBMQ_USERNAME"),
                password=os.getenv("RBMQ_PASSWORD"),
                timeout=10  
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)  # Control concurrency
            await self._declare_infrastructure()
        except Exception as e:
            logging.error(f"Failed to connect to RabbitMQ: {str(e)}")
            await self._safe_close()
            raise

    async def _declare_infrastructure(self):
        try:
            exchange = await self.channel.declare_exchange(
                name="chat_events",
                type=aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            dlx_exchange = await self.channel.declare_exchange(
                name="chat_dlx",
                type=aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            queue = await self.channel.declare_queue(
                name="chat_deleted_queue",
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "chat_dlx",
                    "x-dead-letter-routing-key": "chat.dead"
                }
            )
            await queue.bind(exchange, routing_key="chat.deleted")
            
            dlx_queue = await self.channel.declare_queue(
                name="chat_dead_letter_queue",
                durable=True
            )
            await dlx_queue.bind(dlx_exchange, routing_key="chat.dead")
            
        except aio_pika.exceptions.ChannelClosed as e:
            logging.error(f"Failed to declare RabbitMQ resources: {str(e)}")
            await self._safe_close()
            raise

    async def _on_message(self, message: aio_pika.IncomingMessage):
        """Asynchronous message processing"""
        async with message.process(ignore_processed=True):  # Automatic acknowledgment control
            try:
                data = json.loads(message.body.decode())
                session_id = data.get("session_id") or data.get("sessionId") or data.get("SessionId")
                
                if not session_id:
                    logging.error("Message missing session_id")
                    await message.reject(requeue=False)  # Send to DLQ directly
                    return
                
                # Async retry logic
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type(Exception)
                ):
                    with attempt:
                        result = await self._process_deletion(session_id)
                        
                        if result.success:
                            logging.info(f"Session deleted successfully: {session_id}")
                        else:
                            logging.error(f"Deletion failed: {result.message}")
                            raise RuntimeError(result.message)  # Trigger retry
                            
            except Exception as e:
                logging.error(f"Error processing message: {str(e)}", exc_info=True)
                await message.reject(requeue=False)  # Finally sent to DLQ

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _process_deletion(self, session_id: str) -> ResultDTO:
        """Business logic with retry"""
        try:
            return await self.chat_service.delete_chat_history_by_session_id(session_id)
        except Exception as e:
            logging.error(f"Service layer error: {str(e)}")
            return ResultDTO.fail(code=500, message="Internal server error")

    async def start_consuming(self):
        """Start async consumer"""
        queue = await self.channel.get_queue("chat_deleted_queue")
        await queue.consume(self._on_message)
        logging.info("Consumer started successfully")
        
        # Keep running until shutdown
        await self._shutdown_flag.wait()
        await self._safe_close()

    async def _safe_close(self):
        """Safely close connections"""
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            logging.info("RabbitMQ connection closed safely")
        except Exception as e:
            logging.warning(f"Error closing connection: {str(e)}")

    async def graceful_shutdown(self):
        """Graceful shutdown entrypoint"""
        self._shutdown_flag.set()
        logging.info("Shutdown signal received, stopping consumer...")