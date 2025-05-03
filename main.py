from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
import os, asyncio, uvicorn, logging
from typing import AsyncGenerator, Any

# import custom modules
from controllers import vectorController, chatController, articleController
from common.core.mongodb_init import mongodb
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO
from services.messaging.consumer import RabbitMQConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# load .env
load_dotenv()

# app state        
class AppState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.consumer_task = None  
        self.shutdown_event = asyncio.Event() 

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value
        
# fast config
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[AppState, Any]:
    state = AppState()
    app.state = state 
    
    try:
        logger.info("Application starting up...")
        
        await mongodb.connect(app)
        logger.info("MongoDB connected")
        deepseek.initialize()
        logger.info("LLM initialized")
        
        logger.info("Starting RabbitMQ consumer thread...")
        consumer = RabbitMQConsumer()
        await consumer.initialize()
        await consumer.connect()  
        state.consumer_task = asyncio.create_task(consumer.start_consuming())
        
        yield dict(state)
        
    finally:
        logger.info("Application shutting down...")
        if state.consumer_task and not state.consumer_task.done():
            state.consumer_task.cancel()
            try:
                await state.consumer_task
            except asyncio.CancelledError:
                logger.info("Consumer task cancelled")
        await consumer.graceful_shutdown()

# fast api setting 
app = FastAPI(
    title="chat_service",
    version="1.0.0",
    lifespan=lifespan
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="chat_service",
        version="1.0.0",
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi 

# middleware
origins = [
    "https://api.oniind244.online/",
    "http://localhost:11115",
    "http://localhost:11119"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["*"]
)

app.include_router(vectorController.router)
app.include_router(chatController.router)
app.include_router(articleController.router)

# start function
if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        workers=4,                              
        limit_concurrency=1000,   
        timeout_keep_alive=30,
        host=os.getenv("CHAT_SERVICE_HOST"), 
        port=int(os.getenv("CHAT_SERVICE_PORT")), 
        reload=True
    )
    
# redirect
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# heart beat
@app.get("/health", dependencies=[])
def health_check():
    return ResultDTO.ok()
