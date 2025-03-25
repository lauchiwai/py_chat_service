from common.core.mongodb_init import mongodb
from fastapi import HTTPException, Header, Depends
import os

async def get_db():
    """get db dependencies"""
    return mongodb.db

async def verify_api_key(x_api_key: str = Header(...)):
    """api key vaildate"""
    if x_api_key != os.getenv("DEEPSEEK_API_KEY"):
        raise HTTPException(status_code=401, detail="vaildate llm api key fail ")
    return True
