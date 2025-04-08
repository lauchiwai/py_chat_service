from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
import os

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self, app: FastAPI):
        """ MongoDB connecting"""
        uri = f'mongodb://{os.getenv("MONGODB_USER")}:{os.getenv("MONGODB_PASSWORD")}@{os.getenv("MONGODB_HOST")}:{os.getenv("MONGODB_PORT")}/{os.getenv("MONGODB_Permission")}'
        db_name = os.getenv("MONGODB_DATABASE")
        
        try:
            self.client = AsyncIOMotorClient(uri)
            self.db = self.client[db_name]
            app.mongodb = self  
            print("MongoDB connected")
        except Exception as e:
            print(f"MongoDB connect fail: {e}")
            raise

    async def close(self):
        """close mongodb connect"""
        if self.client:
            self.client.close()
            print("MongoDB connect is closed")

mongodb = MongoDB()