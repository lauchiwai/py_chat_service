from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
import os

# import custom modules
from mongodb_init import mongodb
from llm_init import deepseek
from dependencies import get_db, verify_api_key
from llm_init.modal_config import ChatRequest, ChatResponse

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

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# start function
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("CHAT_SERVICE_HOST"), port=int(os.getenv("CHAT_SERVICE_PORT")), reload=True)

# redirect
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# heart beat
@app.get("/health")
def health_check():
    return {"status": "ok"}

# get chat history by sessionId 
@app.get("/getChatHistoryBySessionId/{chat_session_id}")
async def get_chat_history_by_session_id(
    chat_session_id: str,
    db=Depends(get_db)
):
    """ get chat histoty by session_id from mongodb """
    try:
        chat_history = await db.chat_historys.find_one({"chat_session_id": chat_session_id})
        if not chat_history:
            raise HTTPException(status_code=404, detail="chat history from session_id is not found")
        
        return {
            "response": chat_history["messages"],
            "chat_session_id": chat_history["chat_session_id"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# chat reseful api
@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    chat_session_id: str,
    x_user_id: str = Header(...),
    db=Depends(get_db),
):
    """process chat request"""
    try:
        chat_history = await db.chat_historys.find_one({"chat_session_id": chat_session_id})
        # check chat history exist
        if not chat_history:
            chat_history = {
                "chat_session_id": chat_session_id,
                "user_id": x_user_id,
                "messages": [
                    {
                        "role": "system",
                        "content": request.system_prompt,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    {
                        "role": "user",
                        "content": request.message,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                ],
                "metadata": {
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens
                }
            }
        else:
            chat_history["messages"].append({
                "role": "user",
                "content": request.message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        response = deepseek.client.chat.completions.create(
            model="deepseek-chat",
            messages=chat_history["messages"],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=False
        )

        assistant_msg = response.choices[0].message.content

        chat_history["messages"].append({
            "role": "assistant",
            "content": assistant_msg,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        if chat_history.get("_id"):  
            await db.chat_historys.replace_one({"_id": chat_history["_id"]}, chat_history)
        else:  
            result = await db.chat_historys.insert_one(chat_history)

        return {
            "response": assistant_msg,
            "chat_session_id": chat_session_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))