from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient 
from fastapi import FastAPI
import os

class MongoDB:
    def __init__(self):
        self.async_client = None
        self.sync_client = None
        self.db = None
        self.sync_db = None

    async def connect(self, app: FastAPI):
        """ MongoDB connecting"""
        uri = f'mongodb://{os.getenv("MONGODB_USER")}:{os.getenv("MONGODB_PASSWORD")}@{os.getenv("MONGODB_HOST")}:{os.getenv("MONGODB_PORT")}/{os.getenv("MONGODB_Permission")}'
        db_name = os.getenv("MONGODB_DATABASE")
        
        try:
            self.async_client = AsyncIOMotorClient(uri)
            self.db = self.async_client[db_name]
            
            self.sync_client = MongoClient(uri)
            self.sync_db = self.sync_client[db_name]
            
            app.mongodb = self  
            print("MongoDB connected")
        except Exception as e:
            print(f"MongoDB connect fail: {e}")
            raise

    async def close(self):
        """close mongodb connect"""
        if self.async_client:
            self.async_client.close()
        if self.sync_client:
            self.sync_client.close()
            print("MongoDB connect is closed")

mongodb = MongoDB()