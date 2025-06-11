import os, json, asyncio, aio_pika
from typing import Optional
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type, AsyncRetrying
from functools import partial

from common.models.request.vectorRequest import DeleteVectorDataRequest
from services.chatService import ChatService
from services.vectorService import VectorService
from services.articleService import ArticleService
from services.dependencies import get_chat_service_async, get_vector_service, get_article_service

class RabbitMQConsumer:
    def __init__(self):
        self.chat_service: Optional[ChatService] = None
        self.vector_service: Optional[VectorService] = None
        self.article_service: Optional[ArticleService] = None
        self.connection = None
        self.channel = None
        self._shutdown_flag = asyncio.Event()
        self._event_configs = {
            "ChatSessionDeleted": {
                "exchange_name": "chat_events",
                "routing_key": "chat.deleted",
                "queue_name": "chat_deleted_queue",
                "dl_exchange": "chat_dlx",
                "dl_routing_key": "chat.dead"
            },
            "ArticleDeleted": {
                "exchange_name": "article_events",
                "routing_key": "article.deleted",
                "queue_name": "article_deleted_queue",
                "dl_exchange": "article_dlx",
                "dl_routing_key": "article.dead"
            }
        }

    async def initialize(self):
        self.chat_service = await get_chat_service_async() 
        self.vector_service = get_vector_service() 
        self.article_service = get_article_service() 
        
    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(
                host=os.getenv("RBMQ_HOSTNAME"),
                login=os.getenv("RBMQ_USERNAME"),
                password=os.getenv("RBMQ_PASSWORD"),
                timeout=10  
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            await self.declare_infrastructure()
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            await self.safe_close()
            raise

    async def declare_infrastructure(self):
        try:
            exchanges = set()
            for cfg in self._event_configs.values():
                exchanges.add(cfg["exchange_name"])
                exchanges.add(cfg["dl_exchange"])

            for exchange in exchanges:
                await self.channel.declare_exchange(
                    name=exchange,
                    type=aio_pika.ExchangeType.DIRECT,
                    durable=True
                )
                print(f"Declared exchange: {exchange}")

            for config in self._event_configs.values():
                queue = await self.channel.declare_queue(
                    name=config["queue_name"],
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": config["dl_exchange"],
                        "x-dead-letter-routing-key": config["dl_routing_key"]
                    }
                )
                await queue.bind(config["exchange_name"], config["routing_key"])
                print(f"Bound queue {config['queue_name']} to {config['exchange_name']}")

                dlx_queue = await self.channel.declare_queue(
                    name=f"{config['dl_exchange']}_queue",
                    durable=True
                )
                await dlx_queue.bind(config["dl_exchange"], config["dl_routing_key"])

        except Exception as e:
            print(f"Infrastructure setup failed: {str(e)}")
            await self.safe_close()
            raise

    async def start_consuming(self):
        try:
            for config_name, config in self._event_configs.items():
                queue = await self.channel.get_queue(config["queue_name"])
                callback = partial(self.on_message, config_name=config_name, queue_name=config["queue_name"])
                await queue.consume(callback)
                print(f"Listening to queue: {config['queue_name']}")
            
            await self._shutdown_flag.wait()
        except Exception as e:
            print(f"Consuming failed: {str(e)}")
            await self.safe_close()

    async def on_message(self, message: aio_pika.IncomingMessage, config_name: str, queue_name: str):
        async with message.process(requeue=False):  
            try:
                config = self._event_configs.get(config_name)
                if not config:
                    print(f"Config {config_name} not found for queue: {queue_name}")
                    raise ValueError(f"Config {config_name} not found")

                if config_name == "ChatSessionDeleted":
                    await self.handle_chat_deletion(message)
                elif config_name == "ArticleDeleted":
                    await self.handle_article_deletion(message)
                else:
                    print(f"Unhandled event type: {config_name}")
                    raise ValueError(f"Unhandled event type: {config_name}")

            except Exception as e:
                print(f"Message processing error: {str(e)}")
    
    async def handle_article_deletion(self, message: aio_pika.IncomingMessage):
        data = json.loads(message.body.decode())
        article_id = data.get("ArticleId")
        collection_name =  data.get("CollectionName")
        
        if not article_id :
            print("Missing article_id  in message")
            raise ValueError("Missing article_id  in message")
        
        if not collection_name :
            print("Missing collection_name in message")
            raise ValueError("Missing collection_name in message")
        
        try:
            article_id = int(article_id)
        except (ValueError, TypeError):
            raise ValueError("ArticleID must be an integer")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception)
        ):
            with attempt:
                delete_vector_request = DeleteVectorDataRequest(
                    collection_name=collection_name,
                    id=article_id
                )
                print(f"Processing article deletion: {delete_vector_request}")
                
                result = await self.vector_service.delete_vector_data(delete_vector_request)
                
                if not result.success:
                    raise RuntimeError(result.message)
                
                print(f"Successfully processed article deletion: {article_id}")
                
    async def handle_chat_deletion(self, message: aio_pika.IncomingMessage):
        data = json.loads(message.body.decode())
        session_id = data.get("SessionId")
        
        if not session_id:
            print("Missing session_id in message")
            raise ValueError("Missing session_id in message")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception)
        ):
            with attempt:
                result = await self.chat_service.delete_chat_history_by_session_id(session_id)
                if not result.success:
                    raise RuntimeError(result.message)
                print(f"Deleted chat session: {session_id}")

    async def safe_close(self):
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            print("Connection closed")
        except Exception as e:
            print(f"Close error: {str(e)}")

    async def graceful_shutdown(self):
        self._shutdown_flag.set()
        print("Shutting down consumer...")