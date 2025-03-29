from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
import os
import uvicorn

# import custom modules
from controllers import vectorController, chatController
from common.core.mongodb_init import mongodb
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO

# load .env
load_dotenv()

# fast config
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongodb_client
    print("app is starting...")
    await mongodb.connect(app) 
    deepseek.initialize()

    yield 
    print("app is closing...")
    await mongodb.close() 

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["*"]
)

app.include_router(vectorController.router)
app.include_router(chatController.router)

# start function
if __name__ == "__main__":
    uvicorn.run("main:app", host=os.getenv("CHAT_SERVICE_HOST"), port=int(os.getenv("CHAT_SERVICE_PORT")), reload=True)

# redirect
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# heart beat
@app.get("/health", dependencies=[])
def health_check():
    return ResultDTO.ok()
