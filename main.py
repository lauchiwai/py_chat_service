from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
import os
# load .env
load_dotenv()
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
