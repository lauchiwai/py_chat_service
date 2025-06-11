from qdrant_client import AsyncQdrantClient
import os
import httpx

class QdrantClient:
    def __init__(self):
        self.client = AsyncQdrantClient(
            url=os.getenv("QDRANT_CLOUD_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            limits=httpx.Limits(
                max_connections=100, 
                max_keepalive_connections=50 
            )
        )
        
qdrant_client = QdrantClient()
